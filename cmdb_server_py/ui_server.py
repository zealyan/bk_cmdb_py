"""UI 服务（prod_bin 前端 + 登录 + /api/v3 反向代理）

一个独立的 Flask 服务，作为「完整的 CMDB 系统」的前端入口（与 BFF 无关）：

  - 托管 prod_bin/ui 静态资源（/static/*）
  - 渲染 index.html / login.html 两个 Go 模板（注入 window.Site/User/Supplier/ESB）
  - 处理原生表单登录（POST /login）：转发到 app.py 的 /api/v3/user/auth，
    成功后下发 bk_token Cookie 并跳转首页
  - 反向代理 /api/v3/* 到 cmdb_server_py（app.py :3000），透传 Cookie/头/方法

端口：UI_PORT（默认 8085）
后端：BACKEND_URL（默认 http://127.0.0.1:3000）
前端根目录：PROD_UI_DIR（默认 ../prod_bin/ui）
"""

import os
import sys
import json
import requests
from flask import Flask, request, redirect, Response, make_response, jsonify

# 让本文件在任意工作目录下都能 import app 包
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.config import Config  # noqa: E402
from app.models.db import get_db_connection, list_collections, get_collection_count  # noqa: E402

UI_PORT = int(os.environ.get("UI_PORT", "8085"))
BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:3000").rstrip("/")
PROD_UI_DIR = os.environ.get(
    "PROD_UI_DIR",
    os.path.normpath(os.path.join(BASE_DIR, "..", "prod_bin", "ui")),
)
INDEX_HTML = os.path.join(PROD_UI_DIR, "index.html")
LOGIN_HTML = os.path.join(PROD_UI_DIR, "login.html")
# prod_bin/ui 下的 css/js/img/svg 等直接挂载到 /static
STATIC_DIR = PROD_UI_DIR

CC_VERSION = os.environ.get("CC_VERSION", "v3.10.50")

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")
app.config.from_object(Config)


# ---------------------------------------------------------------------------
# 模板渲染：Go 模板只有简单 {{.key}} 占位符，直接字符串替换即可
# ---------------------------------------------------------------------------
def _render_index(user_name):
    """渲染 index.html，注入 window.Site / User / Supplier / ESB 全局变量。

    API_HOST 在 ccversion 不含 'dev' 时取 window.location.origin，
    因此前端所有 /api/v3 调用都会落到本 UI 服务，再由代理转发到 app.py。
    """
    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        html = f.read()

    ctx = {
        "{{.site}}": '"/"',
        "{{.version}}": '"v3"',
        "{{.curl}}": '"/login"',
        "{{.agentAppUrl}}": '""',
        "{{.authscheme}}": '"internal"',
        "{{.ccversion}}": CC_VERSION,               # 模板已用单引号包裹
        "{{.fullTextSearch}}": "false",
        "{{.helpDocUrl}}": '""',
        "{{.disableOperationStatistic}}": "false",
        "{{.role}}": "true",                        # 仅向已登录管理员渲染首页
        "{{.userName}}": json.dumps(user_name),     # 已是合法 JS 字符串字面量
        "{{.userManage}}": '""',                    # ESB 用户管理 API 前缀（未配置时为空）
    }
    for k, v in ctx.items():
        html = html.replace(k, v)
    return html


def _render_login(error=""):
    """渲染 login.html，error 注入到 window.LOGIN_ERROR。"""
    with open(LOGIN_HTML, "r", encoding="utf-8") as f:
        html = f.read()
    # 模板为 window.LOGIN_ERROR = '{{.error}}'，error 不需要外引号，转义单引号即可
    safe = error.replace("\\", "\\\\").replace("'", "\\'")
    html = html.replace("{{.error}}", safe)
    return html


def _call_backend(method, path, **kwargs):
    """以服务端身份调用 app.py，并返回 requests.Response。"""
    url = f"{BACKEND_URL}{path}"
    return requests.request(method, url, timeout=30, **kwargs)


def _is_authenticated(bk_token):
    """通过 app.py /api/v3/user/info 校验 bk_token 是否有效，返回 (ok, username)。"""
    if not bk_token:
        return False, None
    try:
        resp = _call_backend(
            "GET", "/api/v3/user/info",
            cookies={"bk_token": bk_token},
        )
        data = resp.json()
        if data.get("result") and data.get("code") == 0:
            return True, (data.get("data") or {}).get("username")
    except Exception as e:
        print(f"[UI] 校验会话失败: {e}")
    return False, None


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------
@app.route("/healthz")
def healthz():
    return make_response(jsonify_ok("healthy"))


def jsonify_ok(message):
    return {"result": True, "code": 0, "message": message, "data": "ok"}


@app.route("/")
def index():
    bk_token = request.cookies.get("bk_token")
    ok, username = _is_authenticated(bk_token)
    if not ok:
        return redirect("/login", code=302)
    html = _render_index(username or Config.ADMIN_USERNAME)
    return Response(html, mimetype="text/html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        # 已登录则直接进入首页
        bk_token = request.cookies.get("bk_token")
        ok, _ = _is_authenticated(bk_token)
        if ok:
            return redirect("/", code=302)
        return Response(_render_login(""), mimetype="text/html")

    # POST：原生表单提交（username/password）或 JSON（bk_username/bk_password）
    username = (request.form.get("username") or request.form.get("bk_username")
                or (request.get_json(silent=True) or {}).get("bk_username")
                or (request.get_json(silent=True) or {}).get("username") or "").strip()
    password = (request.form.get("password") or request.form.get("bk_password")
                or (request.get_json(silent=True) or {}).get("bk_password")
                or (request.get_json(silent=True) or {}).get("password") or "")

    try:
        resp = _call_backend(
            "POST", "/api/v3/user/auth",
            json={"bk_username": username, "bk_password": password},
        )
        payload = resp.json()
    except Exception as e:
        print(f"[UI] 登录后端调用失败: {e}")
        return Response(_render_login("登录服务不可用，请稍后重试"), mimetype="text/html")

    if payload.get("result") and payload.get("code") == 0:
        data = payload.get("data") or {}
        token = data.get("bk_token")
        if not token:
            return Response(_render_login("登录失败：未获取到令牌"), mimetype="text/html")
        uname = data.get("username") or username
        out = redirect("/", code=302)
        out.set_cookie(
            "bk_token", token,
            max_age=86400, httponly=True, samesite="Lax", path="/",
        )
        return out

    msg = payload.get("message") or "用户名或密码错误"
    return Response(_render_login(msg), mimetype="text/html")


@app.route("/logout", methods=["GET", "POST"])
def logout():
    bk_token = request.cookies.get("bk_token")
    if bk_token:
        try:
            _call_backend("POST", "/api/v3/user/logout", cookies={"bk_token": bk_token})
        except Exception:
            pass
    out = redirect("/login", code=302)
    out.delete_cookie("bk_token", path="/")
    return out


@app.route("/api/v3/<path:subpath>", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
def proxy_api(subpath):
    """反向代理 /api/v3/* 到 app.py，透传方法/头/Cookie/查询/Body。"""
    target = f"{BACKEND_URL}/api/v3/{subpath}"
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length", "cookie")
    }
    cookies = {k: v for k, v in request.cookies.items()}
    data = request.get_data()  # 原始 Body，保留 JSON / form

    try:
        resp = requests.request(
            method=request.method,
            url=target,
            headers=headers,
            cookies=cookies,
            params=request.args,
            data=data,
            allow_redirects=False,
            timeout=30,
        )
    except Exception as e:
        return make_response(
            jsonify_error(f"后端代理错误: {e}"), 502
        )

    # 构造响应，剔除由 requests 自动处理的逐跳头
    excluded = ("content-length", "transfer-encoding", "connection", "content-encoding", "set-cookie")
    out_headers = [(k, v) for k, v in resp.headers.items() if k.lower() not in excluded]
    out = Response(resp.content, status=resp.status_code, headers=out_headers)
    # 转发后端可能下发的 Cookie（如登录态续期）
    for name, value in resp.cookies.items():
        out.set_cookie(name, value, httponly=True, samesite="Lax", path="/")
    return out


def jsonify_error(message):
    return {"result": False, "code": 502, "message": message}


# ---------------------------------------------------------------------------
# 资源目录「各模型实例数」统计：对应 bk-cmdb web_server 的 GetObjectInstanceCount
#
# 前端 object-common-inst store 的 searchInstanceCount 用 window.API_HOST 拼接，
# 因此请求落在 http://<ui>:<port>/object/count（不带 /api/v3 前缀），由本 UI 服务直接处理，
# 而非转发到 /api/v3/object/count。响应 contract 与 bk-cmdb 一致：
#   - 请求体： {"condition": {"obj_ids": ["biz", "set", ...]}}
#   - 响应 data：数组 [{bk_obj_id, inst_count, error}]，前端取 data[i].inst_count 渲染计数
#   - 必须携带 bk_error_code=0，否则前端拦截器会 reject 导致计数不显示
# ---------------------------------------------------------------------------
# bk-cmdb 内置对象的实例集合（特例）；通用对象统一为 cc_<obj_id>Base
BUILTIN_INST_TABLE = {
    "biz": "cc_ApplicationBase",
    "set": "cc_SetBase",
    "module": "cc_ModuleBase",
    "host": "cc_HostBase",
    "process": "cc_Process",
    "bk_biz_set_obj": "cc_BizSetBase",
    "plat": "cc_PlatBase",
}


def _resolve_inst_table(obj_id, cols):
    """根据 bk_obj_id 解析实例集合名（bk-cmdb GetInstTableName 的等价实现）。

    内置对象用独立集合；通用/网络对象（bk_switch/bk_router/...）使用分片集合
    cc_ObjectBase_0_pub_<obj_id>（initdb 默认 supplier=0）。
    """
    # 内置对象特例优先
    if obj_id in BUILTIN_INST_TABLE:
        return BUILTIN_INST_TABLE.get(obj_id)
    # 通用（自定义）对象：cc_ObjectBase_0_pub_<obj_id>
    cand = f"cc_ObjectBase_0_pub_{obj_id}"
    if cand in cols:
        return cand
    return None


@app.route("/object/count", methods=["GET", "POST", "OPTIONS"])
def object_count():
    """资源目录各模型实例数统计。"""
    if request.method == "OPTIONS":
        return make_response("", 204)
    cols = set(list_collections())
    # 已注册的对象模型（用于区分「模型不存在」与「模型存在但无实例集合」）
    valid_obj_ids = {
        d.get("bk_obj_id")
        for d in get_db_connection()["cc_ObjectBase"].find({}, {"bk_obj_id": 1})
    }
    payload = request.get_json(silent=True) or {}
    obj_ids = (payload.get("condition") or {}).get("obj_ids") or []
    obj_ids = [str(x) for x in obj_ids if x][:20]  # 与 bk-cmdb 一致：单次最多 20 个

    data = []
    for oid in obj_ids:
        if oid not in valid_obj_ids:
            # 模型在 cc_ObjectBase 中不存在：与 bk-cmdb nonexistentObjects 一致
            data.append({"bk_obj_id": oid, "inst_count": 0, "error": "model not found"})
            continue
        table = _resolve_inst_table(oid, cols)
        count = get_collection_count(table) if table else 0
        data.append({"bk_obj_id": oid, "inst_count": count, "error": ""})

    resp = {
        "bk_error_code": 0,
        "bk_error_msg": "",
        "result": True,
        "code": 0,
        "message": "success",
        "data": data,
    }
    return jsonify(resp)


# ---------------------------------------------------------------------------
# 根路径（无 /api/v3 前缀）端点兜底
#
# 前端部分 store 用 window.API_HOST（= origin + '/'）直拼请求，落到本 UI 服务的根路径，
# 例如 hosts/search、hosts/search/web、biz/search/web、user/list、organization/department、
# object/exportmany、object/importmany、object/object/<id>/export|import、
# insts/object/<id>/export|import、regular/verify_*、collector/*、proxy/get/usermanage<path>、
# importtemplate/<objId> 等（详见 §8.8）。这些端点不在 /api/v3 代理范围内，原会让 UI 报 404。
#
# 处理策略：
#   1) 优先代理到 app.py 的同名 /api/v3/<path> 接口（复用真实逻辑）。
#      app.py 已实现的可直接获得真实数据：hosts/search、hosts/search/web、
#      biz/search/web、object/count 等。
#   2) 若 app.py 未实现（404，最小系统未覆盖的导入/导出/网络采集/用户管理类），
#      返回 bk-cmdb 风格的成功空响应，避免 UI 弹 404 / 错误：
#        - 下载/模板类（路径含 export 或 importtemplate）：返回空文件体；
#        - 列表/对象类：返回 data:[] 信封。
# 显式路由（/、/login、/logout、/object/count、/api/v3/<path>、/static/<path>）优先级更高，
# 本兜底仅捕获其余根路径请求。
# ---------------------------------------------------------------------------
def _bk_envelope(data):
    """bk-cmdb 通用成功响应信封（前端拦截器认 bk_error_code:0 / result:true）。"""
    return {
        "bk_error_code": 0,
        "bk_error_msg": "",
        "result": True,
        "code": 0,
        "message": "success",
        "data": data,
    }


def _safe_root_response(subpath, method):
    """app.py 未实现该 /api/v3 等价接口时的安全空响应。"""
    # 下载/模板类：返回空文件体，避免前端 $download 把 JSON 当文件解析报错
    if "export" in subpath or "importtemplate" in subpath:
        return Response("", status=200, mimetype="text/csv; charset=utf-8")
    # 列表/对象类：返回空数据信封
    return jsonify(_bk_envelope([]))


@app.route("/<path:subpath>", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
def root_api_fallback(subpath):
    """根路径（无 /api/v3 前缀）端点的代理 + 安全兜底。"""
    if request.method == "OPTIONS":
        return make_response("", 204)
    # 显式路由已由 Flask 优先匹配；此处仅兜底真正的根路径请求。
    # 代理到 app.py 同名 /api/v3 接口（复用真实逻辑）。
    target = f"{BACKEND_URL}/api/v3/{subpath}"
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length", "cookie")
    }
    cookies = {k: v for k, v in request.cookies.items()}
    try:
        resp = requests.request(
            method=request.method,
            url=target,
            headers=headers,
            cookies=cookies,
            params=request.args,
            data=request.get_data(),
            allow_redirects=False,
            timeout=30,
        )
    except Exception:
        # 后端不可达：返回安全空响应，不让 UI 报 404
        return _safe_root_response(subpath, request.method)

    if resp.status_code == 404:
        # app.py 无此 /api/v3 等价接口（最小系统未覆盖）→ 安全空响应
        return _safe_root_response(subpath, request.method)

    # 透传 app.py 的真实响应
    excluded = ("content-length", "transfer-encoding", "connection", "content-encoding", "set-cookie")
    out_headers = [(k, v) for k, v in resp.headers.items() if k.lower() not in excluded]
    out = Response(resp.content, status=resp.status_code, headers=out_headers)
    for name, value in resp.cookies.items():
        out.set_cookie(name, value, httponly=True, samesite="Lax", path="/")
    return out


if __name__ == "__main__":
    print(f"[UI] 启动 UI 服务：port={UI_PORT} backend={BACKEND_URL} ui_dir={PROD_UI_DIR}")
    app.run(host="0.0.0.0", port=UI_PORT, debug=False, use_reloader=False)
