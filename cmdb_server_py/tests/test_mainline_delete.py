"""主线节点删除接口回归测试（DELETE /api/v3/delete/topomodelmainline/object/{bk_obj_id}）。

对齐 Go DeleteMainlineAssociation 守门与行为。本仓库 ``make_response`` 恒返回 HTTP 200，
业务成败以 body 的 ``code`` / ``bk_error_code`` 字段判定（前端据此取 data）。

运行：在 cmdb_server_py/ 目录下 ``pytest tests/ -q``（需 MongoDB 可达）。
"""
import pytest


# --------------------------------------------------------------------------- #
# 守门测试（只读，不改动任何数据；均在写入前返回）
# --------------------------------------------------------------------------- #
def test_guard_builtin_model(client):
    """内置主线模型（set）禁止删除 -> code 400。"""
    r = client.delete("/api/v3/delete/topomodelmainline/object/set")
    body = r.get_json()
    assert r.status_code == 200
    assert body["code"] == 400
    assert "内置主线模型" in body["message"]


def test_guard_nonexistent_model(client):
    """不存在的模型 -> code 404。"""
    r = client.delete("/api/v3/delete/topomodelmainline/object/nope")
    body = r.get_json()
    assert r.status_code == 200
    assert body["code"] == 404
    assert "模型不存在" in body["message"]


def test_guard_non_mainline_model(client):
    """非主线模型（bk_switch 通用对象）-> code 400。"""
    r = client.delete("/api/v3/delete/topomodelmainline/object/bk_switch")
    body = r.get_json()
    assert r.status_code == 200
    assert body["code"] == 400
    assert "不是主线模型" in body["message"]


# --------------------------------------------------------------------------- #
# 快乐路径：新建 appsys 主线节点 -> 删除 -> 链路还原（幂等，结束于干净状态）
# --------------------------------------------------------------------------- #
def _ensure_clean_appsys(client):
    """测试前若 appsys 仍存在则先清掉，保证起点一致。"""
    r = client.delete("/api/v3/delete/topomodelmainline/object/appsys")
    # 允许不存在/已删除，仅当意外残留时清理
    return r


def _create_appsys(client):
    payload = {
        "bk_asst_obj_id": "biz",          # 父级：业务
        "bk_obj_id": "appsys",
        "bk_obj_name": "应用系统",
        "bk_obj_icon": "icon-cc-default",
        "bk_classification_id": "bk_uncategorized",
        "bk_supplier_account": "0",
        "creator": "admin",
    }
    r = client.post("/api/v3/create/topomodelmainline", json=payload)
    return r


def _find_chain(client):
    r = client.post("/api/v3/find/topomodelmainline",
                    json={"bk_supplier_account": "0"})
    return r.get_json()


def _ensure_appsys1_exists(client):
    """确保主线节点 appsys1 存在（供业务拓扑渲染测试复用，不删除以保持状态）。"""
    chain = _find_chain(client)
    objs = [n.get("bk_obj_id") for n in (chain.get("data") or [])]
    if "appsys1" in objs:
        return
    client.post("/api/v3/create/topomodelmainline", json={
        "bk_asst_obj_id": "biz", "bk_obj_id": "appsys1", "bk_obj_name": "应用系统1",
        "bk_obj_icon": "icon-cc-default", "bk_classification_id": "bk_uncategorized",
        "bk_supplier_account": "0", "creator": "admin",
    })


def test_business_topo_includes_custom_mainline_level(client):
    """业务拓扑应渲染自定义主线层 appsys1，且存量 set 经 reparent 挂在它之下（对齐 Go）。"""
    _ensure_appsys1_exists(client)
    r = client.post("/api/v3/find/topoinst/biz/3", json={"bk_supplier_account": "0"})
    body = r.get_json()
    assert r.status_code == 200 and body["code"] == 0, body
    biz = (body.get("data") or [None])[0]
    assert biz and biz["bk_obj_id"] == "biz"
    appsys = next((c for c in biz["child"] if c["bk_obj_id"] == "appsys1"), None)
    assert appsys is not None, "业务拓扑应出现 appsys1 自定义主线层: %s" % [c["bk_obj_id"] for c in biz["child"]]
    assert "set" in [c["bk_obj_id"] for c in appsys["child"]], \
        "appsys1 下应有经 reparent 的存量 set 实例"


def test_business_topo_idle_pool_under_biz(client):
    """空闲机池(default=1) 应直接挂在业务下，而非自定义主线层（对齐 Go buildTopoInstRst）。"""
    _ensure_appsys1_exists(client)
    r = client.post("/api/v3/find/topoinst/biz/1", json={"bk_supplier_account": "0"})
    body = r.get_json()
    assert r.status_code == 200 and body["code"] == 0, body
    biz = (body.get("data") or [None])[0]
    child_objs = [c["bk_obj_id"] for c in biz["child"]]
    assert "appsys1" in child_objs, child_objs
    assert "set" in child_objs, "空闲机池应直接挂在业务下: %s" % child_objs


def test_happy_path_create_then_delete(client):
    """新建 appsys（biz->appsys->set）后删除，链路还原为 biz->set->module->host。"""
    _ensure_clean_appsys(client)

    # 1) 新建主线节点
    cr = _create_appsys(client)
    cbody = cr.get_json()
    assert cr.status_code == 200, cbody
    assert cbody["code"] == 0, cbody

    # 新建后链路应含 appsys
    chain = _find_chain(client)
    obj_ids = [n.get("bk_obj_id") for n in (chain.get("data") or [])]
    assert "appsys" in obj_ids, "新建后主线链路应包含 appsys: %s" % obj_ids

    # 2) 删除主线节点
    try:
        dr = client.delete("/api/v3/delete/topomodelmainline/object/appsys")
        dbody = dr.get_json()
        assert dr.status_code == 200, dbody
        assert dbody["code"] == 0, dbody
        assert dbody["data"]["bk_obj_id"] == "appsys"
    finally:
        # 兜底清理，保证测试后数据库回到干净状态（即使断言失败也不残留）
        _ensure_clean_appsys(client)

    # 3) 删除后链路不再含 appsys（容忍预存的其它自定义层如 appsys1，不误删用户数据）
    chain = _find_chain(client)
    obj_ids = [n.get("bk_obj_id") for n in (chain.get("data") or [])]
    assert "appsys" not in obj_ids, "删除后主线链路不应再含 appsys: %s" % obj_ids
    for need in ["biz", "set", "module", "host"]:
        assert need in obj_ids, "删除后链路应仍含 %s: %s" % (need, obj_ids)
    assert obj_ids[0] == "biz", "链路应以 biz 为根: %s" % obj_ids
