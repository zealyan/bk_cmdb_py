"""
integrated_bff.py —— bk-cmdb「Python 后端 + prod_bin UI」集成网关（BFF）

定位：
  作为单一入口（端口 8083）前置在 prod_bin 的 Go webserver 之前，
  实现 L2 联邦架构中的「Backend for Frontend」角色：

    prod_bin UI (8083)
        │  所有请求先到本 BFF
        ├── /api/v3/hosts/search*  → 本地处理（hzdz 视图：跨库读 CMDB Mongo `cmdb`，
        │                            把全部主机投影为「统一归属」视图，无需修改 Go/前端）
        ├── 其它 /api/v3/*         → 反向代理给 Go webserver (GO_WEB_PORT=8084) → apiserver
        │                            （即 123 业务，沿用 CMDB 原生 REST）
        └── / 及静态资源 /login/*  → 反向代理给 Go webserver (8084)
                                     （Go webserver 负责渲染 index.html 模板 + 提供静态资源 + 登录）

设计要点：
  - 不改动 cmdb_server_py 的 app.py，也不改动 Go 前端/后端代码。
  - hzdz 数据源自 CMDB 同一 Mongo 实例的独立库 `cmdb`（逻辑隔离：独立 DB），
    通过只读投影实现「hzdz 视角下所有 host 都归属 home biz」。
  - 对 123 的读写完全走 CMDB 原生 API（经 Go webserver），满足 schema 解耦与凭证最小化。

环境变量：
  BFF_PORT          本服务监听端口，默认 8083
  GO_WEB_PORT       Go webserver 实际端口，默认 8084
  CMDB_MONGO_URI    CMDB Mongo 连接串（需 cc 账号），默认见下方
  HZ_VIEW_BIZ_ID    投影视图中统一归属的业务 ID，默认 1（资源池/home biz）
"""
import os
import json
from flask import Flask, request, Response
import requests
from pymongo import MongoClient
from bson import ObjectId, Int64
from datetime import datetime, date


def _clean(o):
    """递归清洗 Mongo 文档中的非 JSON 原生类型。"""
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, datetime):
        return o.isoformat()
    if isinstance(o, date):
        return o.isoformat()
    if isinstance(o, ObjectId):
        return str(o)
    if isinstance(o, Int64):
        return int(o)
    return o

BFF_PORT = int(os.environ.get("BFF_PORT", "8083"))
GO_WEB_PORT = int(os.environ.get("GO_WEB_PORT", "8084"))
GO_WEB = f"http://127.0.0.1:{GO_WEB_PORT}"
CMDB_MONGO_URI = os.environ.get(
    "CMDB_MONGO_URI",
    "mongodb://cc:cc@127.0.0.1:27017/cmdb?authSource=cmdb",
)
HZ_VIEW_BIZ_ID = int(os.environ.get("HZ_VIEW_BIZ_ID", "1"))

app = Flask(__name__, static_folder=None)  # 禁用内置 /static 路由，交由 proxy_ui 反代给 Go webserver
_mongo = None


def cmdb_db():
    """延迟连接 CMDB Mongo（只读投影数据源）。"""
    global _mongo
    if _mongo is None:
        client = MongoClient(CMDB_MONGO_URI, serverSelectionTimeoutMS=5000)
        _mongo = client.get_default_database()
    return _mongo


# ------------------------------------------------------------------ #
# 1) hzdz 本地端点：主机统一视图（跨库读 CMDB `cmdb`）
# ------------------------------------------------------------------ #
def _hzdz_hosts_search(req_data):
    db = cmdb_db()
    page = req_data.get("page", {}) or {}
    start = int(page.get("start", 0) or 0)
    limit = int(page.get("limit", 20) or 20)
    sort = page.get("sort", "bk_host_id") or "bk_host_id"

    sort_dir = 1
    s = sort
    if s.startswith("-"):
        sort_dir = -1
        s = s[1:]

    host_coll = db["cc_HostBase"]
    total = host_coll.count_documents({})
    cursor = host_coll.find({}).sort(s or "bk_host_id", sort_dir).skip(start).limit(limit)

    host_ids = [h.get("bk_host_id") for h in cursor]
    if not host_ids:
        return {"info": [], "count": total}

    mh = list(db["cc_ModuleHostConfig"].find({"bk_host_id": {"$in": host_ids}}))
    module_ids = list({r.get("bk_module_id") for r in mh if r.get("bk_module_id") is not None})
    set_ids = list({r.get("bk_set_id") for r in mh if r.get("bk_set_id") is not None})
    # 关键：hzdz 视图下，所有主机统一归属到 HZ_VIEW_BIZ_ID（home biz）
    biz_ids = [HZ_VIEW_BIZ_ID]

    module_map = {m.get("bk_module_id"): m for m in db["cc_ModuleBase"].find({"bk_module_id": {"$in": module_ids}})}
    set_map = {s.get("bk_set_id"): s for s in db["cc_SetBase"].find({"bk_set_id": {"$in": set_ids}})}
    biz_map = {b.get("bk_biz_id"): b for b in db["cc_ApplicationBase"].find({"bk_biz_id": {"$in": biz_ids}})}

    host_module_map, host_set_map = {}, {}
    for r in mh:
        hid = r.get("bk_host_id")
        host_module_map.setdefault(hid, [])
        host_set_map.setdefault(hid, [])
        if r.get("bk_module_id") not in host_module_map[hid]:
            host_module_map[hid].append(r.get("bk_module_id"))
        if r.get("bk_set_id") not in host_set_map[hid]:
            host_set_map[hid].append(r.get("bk_set_id"))

    info = []
    for doc in host_coll.find({"bk_host_id": {"$in": host_ids}}):
        doc.pop("_id", None)
        hid = doc.get("bk_host_id")
        modules = [module_map[mid] for mid in host_module_map.get(hid, []) if mid in module_map]
        sets = [set_map[sid] for sid in host_set_map.get(hid, []) if sid in set_map]
        biz = [biz_map[b] for b in biz_ids if b in biz_map]
        for m in modules:
            m.pop("_id", None)
        for s in sets:
            s.pop("_id", None)
        for b in biz:
            b.pop("_id", None)
        info.append({"host": doc, "module": modules, "set": sets, "biz": biz})

    return {"info": info, "count": total}


@app.route("/api/v3/hosts/search", methods=["POST"])
@app.route("/api/v3/hosts/search/web", methods=["POST"])
@app.route("/hosts/search", methods=["POST"])
@app.route("/hosts/search/web", methods=["POST"])
def hzdz_hosts_search():
    req_data = request.get_json(silent=True) or {}
    data = _hzdz_hosts_search(req_data)
    return Response(
        json.dumps(_clean({"result": True, "bk_error_code": 0, "bk_err_code": 0,
                           "message": "success", "code": 0, "permission": None, "data": data}),
                   ensure_ascii=False),
        mimetype="application/json",
    )


# ------------------------------------------------------------------ #
# 2) 反向代理：其它 /api/v3 与 UI 资源 → Go webserver (8084)
# ------------------------------------------------------------------ #
def _proxy(path, is_api):
    target = f"{GO_WEB}/{path}"
    # 透传浏览器请求头，但去掉 Host（由 requests 重设）
    headers = {k: v for k, v in request.headers if k.lower() not in ("host", "content-length")}
    body = request.get_data() if request.method in ("POST", "PUT", "PATCH") else None
    try:
        resp = requests.request(
            method=request.method,
            url=target,
            params=request.args,
            data=body,
            headers=headers,
            cookies=request.cookies,
            allow_redirects=False,
            timeout=30,
        )
    except requests.exceptions.RequestException as e:
        return Response(json.dumps({"result": False, "code": 502,
                                     "message": f"BFF upstream error: {e}"}),
                        status=502, mimetype="application/json")

    # 重写 Location 中的 8084 -> 8083，避免浏览器直连 Go webserver
    resp_headers = {}
    for k, v in resp.headers.items():
        if k.lower() in ("content-length", "transfer-encoding", "connection"):
            continue
        if k.lower() == "location":
            v = v.replace(f"127.0.0.1:{GO_WEB_PORT}", f"127.0.0.1:{BFF_PORT}")
            v = v.replace(f":{GO_WEB_PORT}", f":{BFF_PORT}")
        resp_headers[k] = v

    return Response(resp.content, status=resp.status_code, headers=resp_headers)


@app.route("/api/v3/<path:subpath>", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
def proxy_api(subpath):
    return _proxy(f"api/v3/{subpath}", is_api=True)


@app.route("/", defaults={"p": ""})
@app.route("/<path:p>", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
def proxy_ui(p):
    return _proxy(p, is_api=False)


@app.route("/healthz")
def healthz():
    return Response(json.dumps({"result": True, "code": 0, "message": "bff healthy",
                                "go_web": GO_WEB}), mimetype="application/json")


if __name__ == "__main__":
    print(f"[BFF] listen :{BFF_PORT}  upstream Go webserver -> {GO_WEB}")
    app.run(host="0.0.0.0", port=BFF_PORT, debug=False, use_reloader=False)
