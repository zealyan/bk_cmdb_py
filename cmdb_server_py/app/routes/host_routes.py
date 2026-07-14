"""动态主机分组（Dynamic Group / Custom Query）接口

对齐 Go 侧 ``scene_server/host_server/service/dynamic_grouping.go`` + ``logics/dynamic_grouping.go``，
为前端 ``views/dynamic-group``（store: ``dynamic-group.js``）提供 BFF 无关、仅依赖 MongoDB 的实现。

前端接口（均挂 /api/v3 前缀）：
  POST   /api/v3/dynamicgroup                 -> create（新建）
  PUT    /api/v3/dynamicgroup/<bizId>/<id>    -> update（编辑）
  DELETE /api/v3/dynamicgroup/<bizId>/<id>    -> delete（删除）
  GET    /api/v3/dynamicgroup/<bizId>/<id>    -> details（详情）
  POST   /api/v3/dynamicgroup/search/<bizId>  -> search（列表，路由进入即调用，修复 init 报错）
  POST   /api/v3/dynamicgroup/data/<bizId>/<id> -> preview/execute（预览，按 bk_obj_id 分 host/set）

数据存储：``cc_DynamicGroup``（tablenames.go BKTableNameDynamicGroup）。
文档字段对齐 metadata.DynamicGroup：bk_biz_id / id / name / bk_obj_id / info / create_user /
modify_user / create_time / last_time。
"""

import re
import uuid
from datetime import datetime

from flask import Blueprint, jsonify, request

from app.models.db import get_mongo_collection, get_db_connection
from app.routes.admin_routes import make_response

dynamic_group_bp = Blueprint('dynamic_group', __name__)

DYNAMIC_GROUP_COLL = "cc_DynamicGroup"


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _now():
    """与本项目其它路由一致的时间戳格式（"%Y-%m-%d %H:%M:%S" 字符串）。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _escape_regex(val):
    """对齐 Go parser.SpecialCharChange：转义正则特殊字符后做不区分大小写模糊匹配。"""
    if not isinstance(val, str):
        val = str(val)
    return re.sub(r'([.*+?^${}()|[\]\\/])', r'\\\1', val)


def _cond_list_to_mongo(conds):
    """将 [{field, operator, value}, ...] 转为 Mongo 查询字典（单对象条件）。"""
    q = {}
    for c in (conds or []):
        field = c.get("field")
        op = c.get("operator", "$eq")
        val = c.get("value")
        if not field:
            continue
        if op == "$regex":
            q[field] = {"$regex": _escape_regex(val), "$options": "i"}
        elif op in ("$in", "$nin"):
            q[field] = {op: val if isinstance(val, list) else [val]}
        elif op == "$eq":
            q[field] = val
        elif op in ("$ne", "$gt", "$gte", "$lt", "$lte"):
            q.setdefault(field, {})[op] = val
        else:
            q[field] = val
    return q


def _doc_to_group(doc):
    """把 Mongo 文档规整为前端 DynamicGroup 对象（剔除 _id）。"""
    if doc is None:
        return None
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


def _merge_host_id_filter(host_q, candidate_ids):
    """将「按业务/集群/模块收窄出的候选主机ID」与 host_q 已有条件合并（取交集，绝不覆盖）。"""
    if candidate_ids is None:
        return
    existing = host_q.get("bk_host_id")
    base = None
    if isinstance(existing, dict):
        if "$in" in existing:
            base = set(existing["$in"])
        elif "$eq" in existing:
            base = {existing["$eq"]}
    elif existing is not None:
        base = {existing}

    if base is not None:
        host_q["bk_host_id"] = {"$in": [h for h in candidate_ids if h in base]}
    else:
        host_q["bk_host_id"] = {"$in": candidate_ids}


def _build_dynamic_group_host_query(conn, biz_id, conditions):
    """根据动态分组的 info.condition 构造 cc_HostBase 查询（host / set / module / plat 条件）。

    返回 host_q，可直接用于 cc_HostBase.find/count_documents。
    - host 条件：直接作用到主机字段；
    - set/module 条件：经 cc_SetBase/cc_ModuleBase + cc_ModuleHostConfig 反查所属主机ID；
    - plat（云区域）条件：作用到主机 bk_cloud_id；
    - 始终以 bk_biz_id 限定业务范围（主机不直存 bk_biz_id，须经 cc_ModuleHostConfig 反查）。
    """
    host_field_q = {}
    rel_query = {"bk_biz_id": biz_id}
    set_ids, mod_ids = [], []

    for cond in (conditions or []):
        obj = cond.get("bk_obj_id")
        items = cond.get("condition") or []
        if obj == "host":
            host_field_q.update(_cond_list_to_mongo(items))
        elif obj == "plat":
            # 云区域条件直接落到主机 bk_cloud_id
            host_field_q.update(_cond_list_to_mongo(items))
        elif obj == "set":
            q = _cond_list_to_mongo(items)
            ids = [d["bk_set_id"] for d in conn.cc_SetBase.find(q, {"bk_set_id": 1, "_id": 0})]
            set_ids.extend(ids)
        elif obj == "module":
            q = _cond_list_to_mongo(items)
            ids = [d["bk_module_id"] for d in conn.cc_ModuleBase.find(q, {"bk_module_id": 1, "_id": 0})]
            mod_ids.extend(ids)

    if set_ids:
        rel_query["bk_set_id"] = {"$in": set_ids}
    if mod_ids:
        rel_query["bk_module_id"] = {"$in": mod_ids}

    candidate = [r["bk_host_id"] for r in
                 conn.cc_ModuleHostConfig.find(rel_query, {"bk_host_id": 1, "_id": 0})]
    _merge_host_id_filter(host_field_q, candidate)
    return host_field_q


def _build_dynamic_group_set_query(conn, biz_id, conditions):
    """根据动态分组的 info.condition 构造 cc_SetBase 查询（set 动态分组）。"""
    set_field_q = {"bk_biz_id": biz_id}
    set_ids, mod_ids, host_ids = [], [], []

    for cond in (conditions or []):
        obj = cond.get("bk_obj_id")
        items = cond.get("condition") or []
        if obj == "set":
            set_field_q.update(_cond_list_to_mongo(items))
        elif obj == "module":
            q = _cond_list_to_mongo(items)
            ids = [d["bk_module_id"] for d in conn.cc_ModuleBase.find(q, {"bk_module_id": 1, "bk_set_id": 1, "_id": 0})]
            mod_ids.extend(ids)
        elif obj == "host":
            q = _cond_list_to_mongo(items)
            ids = [d["bk_host_id"] for d in conn.cc_HostBase.find(q, {"bk_host_id": 1, "_id": 0})]
            host_ids.extend(ids)

    # 模块条件 -> 模块所属 set_id；主机条件 -> 经 cc_ModuleHostConfig 反查 set_id
    if mod_ids:
        for m in conn.cc_ModuleBase.find({"bk_module_id": {"$in": mod_ids}}, {"bk_set_id": 1, "_id": 0}):
            if m.get("bk_set_id") is not None:
                set_ids.append(m["bk_set_id"])
    if host_ids:
        for r in conn.cc_ModuleHostConfig.find({"bk_host_id": {"$in": host_ids}}, {"bk_set_id": 1, "_id": 0}):
            if r.get("bk_set_id") is not None:
                set_ids.append(r["bk_set_id"])

    if (mod_ids or host_ids):
        set_field_q["bk_set_id"] = {"$in": set_ids} if set_ids else {"$in": []}
    return set_field_q


def _normalize_doc(doc):
    """轻量化 host/set 文档规整：列表值转逗号字符串（对齐前端标量展示），并补 bk_inst_id。"""
    if not isinstance(doc, dict):
        return doc
    for k, v in list(doc.items()):
        if isinstance(v, list):
            doc[k] = ",".join(str(x) for x in v)
    pk = "bk_host_id" if "bk_host_id" in doc else ("bk_set_id" if "bk_set_id" in doc else None)
    if pk and "bk_inst_id" not in doc:
        doc["bk_inst_id"] = doc[pk]
    return doc


def _apply_page_and_sort(cursor, page, default_sort="bk_host_id"):
    """统一处理分页与排序。"""
    start = int(page.get("start", 0) or 0)
    limit = int(page.get("limit", 20) or 20)
    sort = page.get("sort") or default_sort
    if sort:
        sort_dir = -1 if sort.startswith("-") else 1
        sort_field = sort[1:] if sort.startswith("-") else sort
        cursor = cursor.sort(sort_field, sort_dir)
    cursor = cursor.skip(start).limit(limit)
    return cursor


# ---------------------------------------------------------------------------
# 路由（注意顺序：search/data 必须先于通用 <bizId>/<id> 注册，避免被其吞掉）
# ---------------------------------------------------------------------------

@dynamic_group_bp.route('/dynamicgroup/search/<bizId>', methods=['POST'])
def search_dynamic_group(bizId):
    """动态分组列表查询 —— 路由进入即调用（index.vue created -> dynamicGroup/search）。

    请求体：{ condition: { name?: string }, page: { start, limit, sort }, fields?, disableCounter? }
    响应：{ count, info }（data 顶层），对齐 Go SearchDynamicGroup -> RespEntity(DynamicGroupBatch)。
    """
    conn = get_db_connection()
    coll = conn[DYNAMIC_GROUP_COLL]

    try:
        biz_id = int(bizId)
    except (TypeError, ValueError):
        return make_response(result=False, code=1190001, message="invalid bk_biz_id")

    body = request.get_json(silent=True) or {}
    condition = body.get("condition") or {}
    page = body.get("page") or {}
    fields = body.get("fields")
    disable_counter = bool(body.get("disableCounter"))

    query = {"bk_biz_id": biz_id}
    # 对齐 Go：condition 透传为查询条件（不含 bk_biz_id，已单独设置），name 走模糊匹配
    for k, v in condition.items():
        if k == "name" and isinstance(v, str) and v:
            query["name"] = {"$regex": _escape_regex(v), "$options": "i"}
        elif k == "bk_obj_id":
            query["bk_obj_id"] = v
    query = {k: v for k, v in query.items() if v is not None}

    count = 0 if disable_counter else coll.count_documents(query)
    sort = page.get("sort") or "-last_time"
    sort_dir = -1 if sort.startswith("-") else 1
    sort_field = sort[1:] if sort.startswith("-") else sort

    projection = None
    if fields:
        projection = {f: 1 for f in fields}
        projection["_id"] = 0

    cursor = coll.find(query, projection)
    cursor = cursor.sort(sort_field, sort_dir)
    start = int(page.get("start", 0) or 0)
    limit = int(page.get("limit", 20) or 20)
    cursor = cursor.skip(start).limit(limit)

    info = [_doc_to_group(d) for d in cursor]
    return make_response(data={"count": count, "info": info})


@dynamic_group_bp.route('/dynamicgroup', methods=['POST'])
def create_dynamic_group():
    """新建动态分组。请求体即 DynamicGroup 对象。

    响应：{ id }，对齐 Go CreateDynamicGroup -> RespEntity(IDResult{ID})。
    """
    conn = get_db_connection()
    coll = conn[DYNAMIC_GROUP_COLL]
    body = request.get_json(silent=True) or {}

    biz_id = body.get("bk_biz_id")
    name = (body.get("name") or "").strip()
    bk_obj_id = (body.get("bk_obj_id") or "").strip()
    info = body.get("info") or {}

    if not isinstance(biz_id, int) or biz_id <= 0:
        return make_response(result=False, code=1190002, message="empty bk_biz_id")
    if not name:
        return make_response(result=False, code=1190003, message="empty name")
    if not bk_obj_id:
        return make_response(result=False, code=1190004, message="empty bk_obj_id")
    if not isinstance(info.get("condition"), list) or len(info["condition"]) == 0:
        return make_response(result=False, code=1190005, message="empty info.condition")

    now = _now()
    create_user = body.get("create_user") or "admin"
    new_id = str(uuid.uuid4())
    doc = {
        "bk_biz_id": biz_id,
        "id": new_id,
        "name": name,
        "bk_obj_id": bk_obj_id,
        "info": info,
        "create_user": create_user,
        "modify_user": create_user,
        "create_time": now,
        "last_time": now,
    }
    coll.insert_one(doc)
    return make_response(data={"id": new_id})


@dynamic_group_bp.route('/dynamicgroup/data/<bizId>/<dgid>', methods=['POST'])
def preview_dynamic_group(bizId, dgid):
    """动态分组预览/执行。请求体：{ fields, page, condition?, disableCounter? }。

    按分组 bk_obj_id 分派：host -> 查 cc_HostBase；set -> 查 cc_SetBase。
    响应：{ count, info }，对齐 Go ExecuteDynamicGroup -> RespEntity(InstDataInfo)。
    """
    conn = get_db_connection()
    coll = conn[DYNAMIC_GROUP_COLL]

    try:
        biz_id = int(bizId)
    except (TypeError, ValueError):
        return make_response(result=False, code=1190001, message="invalid bk_biz_id")

    body = request.get_json(silent=True) or {}
    fields = body.get("fields") or []
    page = body.get("page") or {}
    disable_counter = bool(body.get("disableCounter"))

    group = coll.find_one({"bk_biz_id": biz_id, "id": dgid})
    if group is None:
        return make_response(result=False, code=1190006, message="dynamic group not found")

    obj_id = group.get("bk_obj_id")
    conditions = (group.get("info") or {}).get("condition") or []

    if obj_id == "host":
        host_q = _build_dynamic_group_host_query(conn, biz_id, conditions)
        target_coll = conn.cc_HostBase
        default_sort = "bk_host_id"
    elif obj_id == "set":
        set_q = _build_dynamic_group_set_query(conn, biz_id, conditions)
        target_coll = conn.cc_SetBase
        default_sort = "bk_set_id"
    else:
        return make_response(result=False, code=1190007, message="unsupported bk_obj_id: %s" % obj_id)

    count = 0 if disable_counter else target_coll.count_documents(host_q if obj_id == "host" else set_q)
    cursor = target_coll.find(host_q if obj_id == "host" else set_q)
    cursor = _apply_page_and_sort(cursor, page, default_sort=default_sort)

    projection = None
    if fields:
        projection = {f: 1 for f in fields}
        projection["_id"] = 0
        # 主键必须保留，前端表格/拓扑回填依赖
        pk = "bk_host_id" if obj_id == "host" else "bk_set_id"
        projection[pk] = 1
        cursor = target_coll.find(
            host_q if obj_id == "host" else set_q, projection)

    info = [_normalize_doc(_doc_to_group(d)) for d in cursor]
    return make_response(data={"count": count, "info": info})


@dynamic_group_bp.route('/dynamicgroup/<bizId>/<dgid>', methods=['GET'])
def get_dynamic_group(bizId, dgid):
    """动态分组详情。响应：完整 DynamicGroup 对象（data 顶层）。"""
    conn = get_db_connection()
    coll = conn[DYNAMIC_GROUP_COLL]
    try:
        biz_id = int(bizId)
    except (TypeError, ValueError):
        return make_response(result=False, code=1190001, message="invalid bk_biz_id")

    group = coll.find_one({"bk_biz_id": biz_id, "id": dgid})
    if group is None:
        return make_response(result=False, code=1190006, message="dynamic group not found")
    return make_response(data=_doc_to_group(group))


@dynamic_group_bp.route('/dynamicgroup/<bizId>/<dgid>', methods=['PUT'])
def update_dynamic_group(bizId, dgid):
    """编辑动态分组。请求体可含 name / bk_obj_id / info。响应：data=null（对齐 Go）。"""
    conn = get_db_connection()
    coll = conn[DYNAMIC_GROUP_COLL]
    try:
        biz_id = int(bizId)
    except (TypeError, ValueError):
        return make_response(result=False, code=1190001, message="invalid bk_biz_id")

    body = request.get_json(silent=True) or {}
    updates = {}

    if "info" in body:
        info = body["info"]
        if not isinstance(info, dict) or not isinstance(info.get("condition"), list):
            return make_response(result=False, code=1190005, message="invalid info.condition")
        if "bk_obj_id" not in body:
            return make_response(result=False, code=1190008, message="bk_obj_id is required when updating info")
        updates["bk_obj_id"] = body["bk_obj_id"]
        updates["info"] = info

    if "name" in body:
        updates["name"] = body["name"]

    if not updates:
        return make_response(result=False, code=1190009, message="empty update content")

    updates["modify_user"] = body.get("modify_user") or "admin"
    updates["last_time"] = _now()

    result = coll.update_one({"bk_biz_id": biz_id, "id": dgid}, {"$set": updates})
    if result.matched_count == 0:
        return make_response(result=False, code=1190006, message="dynamic group not found")
    return make_response(data=None)


@dynamic_group_bp.route('/dynamicgroup/<bizId>/<dgid>', methods=['DELETE'])
def delete_dynamic_group(bizId, dgid):
    """删除动态分组。响应：data=null（对齐 Go）。"""
    conn = get_db_connection()
    coll = conn[DYNAMIC_GROUP_COLL]
    try:
        biz_id = int(bizId)
    except (TypeError, ValueError):
        return make_response(result=False, code=1190001, message="invalid bk_biz_id")

    result = coll.delete_one({"bk_biz_id": biz_id, "id": dgid})
    if result.deleted_count == 0:
        return make_response(result=False, code=1190006, message="dynamic group not found")
    return make_response(data=None)
