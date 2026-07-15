import json
from datetime import datetime
from flask import Blueprint, jsonify, request, g
from app.models.db import db, get_db_connection, get_mongo_collection, next_sequence
from app.config import Config
from app.core.model import ModelError, ensure_model_default_attributes, get_mainline_neighbors, delete_mainline_object

object_bp = Blueprint('object', __name__)

# 原项目权限错误码
PERMISSION_DENIED_CODE = 9900403

import re as _re


def validate_unique_constraint(obj_id, instance_data, collection_name, exclude_id=None):
    """唯一约束校验 — 对齐 Go validator_unique.go getValidUniqueOptions。
    
    查询 cc_ObjectUnique 中 bk_obj_id=obj_id 的规则，对每条非空 keys 组合：
    1. 解析 keys[].key_id → cc_ObjAttDes.id → 取 bk_property_id
    2. 检查 instance_data 中是否包含所有相关属性
    3. 构建 Mongo 查询条件，统计已有实例数
    4. 若已存在（更新时排除自身），报唯一冲突错误。
    """
    conn = get_db_connection()
    if conn is None:
        return  # 数据库不可用时跳过校验
    # 获取该对象的全部属性（用于 key_id → bk_property_id 映射）
    att_des = list(conn["cc_ObjAttDes"].find(
        {"bk_obj_id": obj_id},
        {"id": 1, "bk_property_id": 1, "_id": 0}
    ))
    id_to_prop = {a["id"]: a["bk_property_id"] for a in att_des if "id" in a}
    
    # 获取该对象的唯一规则
    unique_rules = list(conn["cc_ObjectUnique"].find(
        {"bk_obj_id": obj_id, "keys": {"$ne": [], "$exists": True}},
        {"keys": 1, "_id": 0}
    ))
    if not unique_rules:
        return  # 无规则，跳过
    
    collection = conn[collection_name]
    
    for rule in unique_rules:
        keys = rule.get("keys") or []
        if not keys:
            continue
        # 解析 key_id → bk_property_id
        prop_ids = []
        for k in keys:
            if k.get("key_kind") != "property":
                continue
            kid = k.get("key_id")
            prop_id = id_to_prop.get(kid)
            if prop_id:
                prop_ids.append(prop_id)
        if not prop_ids:
            continue
        
        # 检查 instance_data 是否包含所有属性值
        query_cond = {}
        all_present = True
        for pid in prop_ids:
            val = instance_data.get(pid)
            if val is None or val == "":
                # 属性值缺失时，该规则不生效（不能用于部分匹配）
                if len(prop_ids) == 1:
                    all_present = False
                    break
                # 多属性组合时，任一缺失则整体规则不生效
                all_present = False
                break
            query_cond[pid] = val
        
        if not all_present:
            continue
        
        # 更新时排除自身
        if exclude_id is not None:
            id_field = "bk_inst_id"  # 通用对象主键
            # 对内置对象用正确的 ID 字段
            id_field_map = {"biz":"bk_biz_id","set":"bk_set_id","module":"bk_module_id",
                           "host":"bk_host_id","process":"bk_process_id","plat":"bk_cloud_id"}
            id_field = id_field_map.get(obj_id, "bk_inst_id")
            query_cond[id_field] = {"$ne": exclude_id}
        
        count = collection.count_documents(query_cond)
        if count > 0:
            prop_names = []
            for pid in prop_ids:
                ainfo = conn["cc_ObjAttDes"].find_one(
                    {"bk_obj_id": obj_id, "bk_property_id": pid},
                    {"bk_property_name": 1}
                )
                prop_names.append(ainfo["bk_property_name"] if ainfo else pid)
            msg = "唯一校验失败: 字段 %s 的组合值已存在" % " + ".join(prop_names)
            raise ModelError(msg, code=11000)


def _to_int(v):
    """将数字字符串安全地转为 int，失败原样返回。"""
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        try:
            return int(v)
        except ValueError:
            try:
                return int(float(v))
            except ValueError:
                return v
    return v


# 主键 / 自增 ID 字段集合：前端常以字符串形式传入（路由参数、表单值），
# 需还原为 int 才能命中 Mongo 中以 int 存储的 ID 值（否则 "6" != 6 导致查不到）。
_ID_FIELDS = {
    "bk_inst_id", "bk_host_id", "bk_set_id", "bk_module_id",
    "bk_biz_id", "bk_process_id", "bk_cloud_id", "bk_biz_set_id",
    "bk_supplier_account",
}


def _coerce_value(field, value):
    if field in _ID_FIELDS:
        if isinstance(value, (list, tuple, set)):
            return [_to_int(x) for x in value]
        return _to_int(value)
    return value


def _ensure_list(v):
    if isinstance(v, (list, tuple, set)):
        return list(v)
    return [v]


def _first(v):
    if isinstance(v, (list, tuple)) and v:
        return v[0]
    return v


def _second(v):
    if isinstance(v, (list, tuple)) and len(v) > 1:
        return v[1]
    return v


def _derive_asset_id(obj_id, next_id):
    """为缺失的必填资产编号（bk_asset_id）派生默认值，保证创建不被阻断。

    bk-cmdb 交换机等模型的 bk_asset_id 标记为必填，但本地自运维场景下管理员常仅填名称即创建，
    缺失时由后端派生 "<obj_id>-<inst_id>"（如 bk_switch-6）以保持字段完整。
    """
    return f"{obj_id}-{next_id}"


def _convert_rule_to_query(rule):
    """将 bk-cmdb 前端条件规则 {field, operator, value} 转换为 Mongo 查询片段。

    对齐 bk-cmdb v3.10 前端 instance.js / filters/utils.js 实际发出的算子，
    避免后端把整段 conditions 直接当 Mongo 查询而返回空结果。
    """
    if not isinstance(rule, dict):
        return None
    field = rule.get("field")
    operator = rule.get("operator")
    value = rule.get("value")
    if not field or operator is None:
        return None
    value = _coerce_value(field, value)

    op_map = {
        "equal": lambda: {field: value},
        "not_equal": lambda: {field: {"$ne": value}},
        "$eq": lambda: {field: value},
        "$ne": lambda: {field: {"$ne": value}},
        "in": lambda: {field: {"$in": _ensure_list(value)}},
        "not_in": lambda: {field: {"$nin": _ensure_list(value)}},
        "$in": lambda: {field: {"$in": _ensure_list(value)}},
        "$nin": lambda: {field: {"$nin": _ensure_list(value)}},
        "less": lambda: {field: {"$lt": value}},
        "less_or_equal": lambda: {field: {"$lte": value}},
        "greater": lambda: {field: {"$gt": value}},
        "greater_or_equal": lambda: {field: {"$gte": value}},
        "datetime_greater_or_equal": lambda: {field: {"$gte": value}},
        "datetime_less_or_equal": lambda: {field: {"$lte": value}},
        "$lt": lambda: {field: {"$lt": value}},
        "$lte": lambda: {field: {"$lte": value}},
        "$gt": lambda: {field: {"$gt": value}},
        "$gte": lambda: {field: {"$gte": value}},
        "between": lambda: {field: {"$gte": _to_int(_first(value)), "$lte": _to_int(_second(value))}},
        "not_between": lambda: {field: {"$lt": _to_int(_first(value)), "$gt": _to_int(_second(value))}},
        "contains": lambda: {field: {"$regex": _re.escape(str(value)), "$options": "i"}},
        "not_contains": lambda: {field: {"$not": {"$regex": _re.escape(str(value)), "$options": "i"}}},
        "begins_with": lambda: {field: {"$regex": "^" + _re.escape(str(value)), "$options": "i"}},
        "ends_with": lambda: {field: {"$regex": _re.escape(str(value)) + "$", "$options": "i"}},
        "is_null": lambda: {field: {"$in": [None, ""]}},
        "not_null": lambda: {field: {"$nin": [None, ""]}},
    }
    fn = op_map.get(operator)
    if fn is None:
        # 未知算子默认按等于处理，避免整条条件被丢弃
        return {field: value}
    try:
        return fn()
    except Exception:
        return {field: value}


def build_instance_query(req_data):
    """将前端实例搜索条件统一转换为 Mongo 查询。

    前端可能发送三种结构：
    - conditions: { condition: 'AND'|'OR', rules: [{field, operator, value}] }（主用）
    - time_condition: { oper: 'and', rules: [{field, start, end}] }（时间区间）
    - condition: { field: value, ... }（旧版扁平结构，或内嵌 rules 结构）
    归一化为 Mongo 查询 dict；空条件返回 {}（匹配全部实例）。
    """
    query = {}
    if not isinstance(req_data, dict):
        return query

    conditions = req_data.get("conditions")
    if isinstance(conditions, dict) and conditions.get("rules") is not None:
        rules = conditions.get("rules") or []
        logic = str(conditions.get("condition", "AND")).upper()
        fragments = []
        for rule in rules:
            frag = _convert_rule_to_query(rule)
            if frag:
                fragments.append(frag)
        if fragments:
            if logic == "OR":
                query["$or"] = fragments
            else:
                for frag in fragments:
                    query.update(frag)

    # 时间区间条件
    time_condition = req_data.get("time_condition")
    if isinstance(time_condition, dict) and time_condition.get("rules"):
        logic = str(time_condition.get("oper", "and")).lower()
        fragments = []
        for rule in time_condition.get("rules") or []:
            field = rule.get("field")
            start = rule.get("start")
            end = rule.get("end")
            if not field:
                continue
            frag = {field: {}}
            if start is not None:
                frag[field]["$gte"] = start
            if end is not None:
                frag[field]["$lte"] = end
            if frag[field]:
                fragments.append(frag)
        if fragments:
            if logic == "or":
                query.setdefault("$or", []).extend(fragments)
            else:
                for frag in fragments:
                    query.update(frag)

    # 旧版扁平 condition
    condition = req_data.get("condition")
    if isinstance(condition, dict):
        if condition.get("rules") is not None:
            return build_instance_query({"conditions": condition})
        for k, v in condition.items():
            if k in ("condition", "rules"):
                continue
            query[k] = v

    return query


def make_response(result=True, code=0, message="success", data=None, **kwargs):
    # bk-cmdb 前端统一以 bk_error_code===0 判定请求成功并取 data；
    # 缺失该字段会让所有列表页静默无数据，故与 result/code 同时下发。
    if result and code == 0:
        bk_error_code, bk_error_msg = 0, ""
    else:
        bk_error_code = code if code != 0 else 500
        bk_error_msg = message
    response = {
        "bk_error_code": bk_error_code,
        "bk_error_msg": bk_error_msg,
        "result": result,
        "code": code,
        "message": message,
    }
    if data is not None:
        response["data"] = data
    # 添加额外的字段到响应顶层
    response.update(kwargs)
    return jsonify(response)


def get_inst_collection_name(obj_id):
    """按 bk-cmdb common/tablenames.go 的 GetInstTableName 规则返回实例集合名。

    内置对象使用独立集合；通用对象（含 bk_switch/bk_router/bk_load_balance/bk_firewall、
    bk_biz_set_obj 等）使用分片集合 cc_ObjectBase_<supplier>_pub_<obj_id>（initdb 默认 supplier=0）。
    """
    mapping = {
        "biz": "cc_ApplicationBase",
        "bk_biz_set_obj": "cc_BizSetBase",
        "set": "cc_SetBase",
        "module": "cc_ModuleBase",
        "host": "cc_HostBase",
        "process": "cc_Process",
        "plat": "cc_PlatBase",
        "cloud_area": "cc_PlatBase",
    }
    if obj_id in mapping:
        return mapping[obj_id]
    # 通用对象：cc_ObjectBase_0_pub_<obj_id>（如 bk_switch -> cc_ObjectBase_0_pub_bk_switch）
    return f"cc_ObjectBase_0_pub_{obj_id}"


def get_inst_id_field(obj_id):
    """返回某对象实例的主键字段名，对齐 common/metadata.GetInstIDFieldByObjID。

    host 用 bk_host_id、set 用 bk_set_id、module 用 bk_module_id、biz 用 bk_biz_id，
    其余通用对象（bk_switch 等）用 bk_inst_id。更新/创建时必须按此字段匹配，否则会 404。
    """
    mapping = {
        "bk_biz_set_obj": "bk_biz_set_id",
        "biz": "bk_biz_id",
        "set": "bk_set_id",
        "module": "bk_module_id",
        "object": "bk_inst_id",
        "host": "bk_host_id",
        "process": "bk_process_id",
        "plat": "bk_cloud_id",
        "cloud_area": "bk_cloud_id",
    }
    return mapping.get(obj_id, "bk_inst_id")


# --------------------------------------------------------------------------- #
# 业务拓扑实例树：沿动态主线链 + bk_parent_id 遍历（对齐 Go buildTopoInstRst）
# --------------------------------------------------------------------------- #
OBJ_NAME_MAP = {
    "biz": "业务", "bk_biz_set_obj": "业务集", "set": "集群", "module": "模块",
    "host": "主机", "process": "进程", "plat": "云区域", "cloud_area": "云区域",
}


def get_inst_name_field(obj_id):
    """返回某对象实例的名称字段（built-in 各异，通用对象统一 bk_inst_name）。"""
    mapping = {
        "biz": "bk_biz_name", "bk_biz_set_obj": "bk_biz_set_name", "set": "bk_set_name",
        "module": "bk_module_name", "host": "bk_host_name", "process": "bk_process_name",
        "plat": "bk_cloud_name", "cloud_area": "bk_cloud_name",
    }
    return mapping.get(obj_id, "bk_inst_name")


def get_mainline_chain(supplier='0'):
    """推导有序主线链 [根..叶]，从 cc_ObjAsst(bk_asst_id=bk_mainline) 动态排出。

    返回示例（无自定义层）: ['biz','set','module','host']；
    插入 appsys1 后: ['biz','appsys1','set','module','host']。
    """
    asst_coll = get_mongo_collection('cc_ObjAsst')
    mainline_assocs = list(asst_coll.find(
        {"bk_asst_id": "bk_mainline", "bk_supplier_account": supplier},
        {"bk_obj_id": 1, "bk_asst_obj_id": 1, "_id": 0}))
    if not mainline_assocs:
        return ["biz", "set", "module", "host"]
    child_to_parent = {}
    parent_to_child = {}
    for a in mainline_assocs:
        c = a.get("bk_obj_id")
        p = a.get("bk_asst_obj_id")
        if not c or not p:
            continue
        child_to_parent[c] = p
        parent_to_child[p] = c
    roots = set(child_to_parent.values()) - set(child_to_parent.keys())
    if not roots:
        return ["biz", "set", "module", "host"]
    current = list(roots)[0]
    chain = []
    seen = set()
    while current and current not in seen:
        chain.append(current)
        seen.add(current)
        current = parent_to_child.get(current)
    return chain or ["biz", "set", "module", "host"]


def _make_topo_node(inst, obj_id, obj_name_map=None, name_field=None, id_field=None):
    if name_field is None:
        name_field = get_inst_name_field(obj_id)
    if id_field is None:
        id_field = get_inst_id_field(obj_id)
    obj_name = (obj_name_map or {}).get(obj_id) if obj_name_map else OBJ_NAME_MAP.get(obj_id, obj_id)
    return {
        "bk_inst_id": inst.get(id_field),
        "bk_inst_name": inst.get(name_field, ""),
        "bk_obj_id": obj_id,
        "bk_obj_name": obj_name,
        "default": inst.get("default", inst.get("bk_default", 0)),
        "child": [],
    }


def build_mainline_inst_tree(conn, supplier, bk_biz_id, with_idle_pool=True):
    """沿动态主线链 + bk_parent_id 遍历业务实例树，对齐 Go SearchMainlineAssociationInstTopo。

    关键点（对齐 Go buildTopoInstRst 的空闲机池特殊处理）：
      当遍历到 set 层时，父实例 id 列表须**额外包含 biz id**，使空闲机池
      （default=1，其 bk_parent_id 指向 biz 而非自定义主线实例）能在 set 层被取到，
      并因其 parent==biz 而直接挂到业务节点下（而非自定义层）。
    其余层级严格按 bk_parent_id 一级级下钻；host 无 bk_parent_id 关系，不进实例树
    （沿用现有「host 仅作计数、不渲染为树节点」的行为）。
    """
    chain = get_mainline_chain(supplier)
    biz = conn.cc_ApplicationBase.find_one(
        {"bk_biz_id": bk_biz_id, "bk_supplier_account": supplier})
    if not biz:
        return []

    # 一次性取回所有主线模型名（自定义层用 cc_ObjDes 名称）
    obj_name_map = dict(OBJ_NAME_MAP)
    for d in conn.cc_ObjDes.find(
            {"bk_supplier_account": supplier},
            {"bk_obj_id": 1, "bk_obj_name": 1, "_id": 0}):
        obj_name_map[d.get("bk_obj_id")] = d.get("bk_obj_name", d.get("bk_obj_id"))

    biz_id = biz.get("bk_biz_id")
    biz_node = _make_topo_node(biz, "biz", obj_name_map=obj_name_map)

    # node_by_id: 全量节点字典（跨级查找父节点用）。
    # 必须跨级：空闲机池(default=1) 的 bk_parent_id 指向 biz，而 biz 已不在「当前层」字典中，
    # 若只用当前层 parent_nodes 会丢失它（见 Go buildTopoInstRst 的 idle pool 直接挂 biz 逻辑）。
    node_by_id = {biz_id: biz_node}
    parent_nodes = {biz_id: biz_node}   # 仅用于驱动下一层的父实例 id 列表
    for i in range(1, len(chain)):
        obj = chain[i]
        if obj == "host":
            continue
        child_coll = conn[get_inst_collection_name(obj)]
        child_id_field = get_inst_id_field(obj)
        name_field = get_inst_name_field(obj)
        parent_ids = list(parent_nodes.keys())
        # Go 怪异逻辑：set 层额外纳入 biz id，捕获空闲机池(default=1, parent=biz)
        if obj == "set":
            parent_ids = parent_ids + [biz_id]
        filt = {
            "bk_parent_id": {"$in": parent_ids},
            "bk_supplier_account": supplier,
            "bk_data_status": {"$ne": "disabled"},
        }
        if not with_idle_pool and obj == "set":
            filt["default"] = {"$ne": 1}
        children = list(child_coll.find(filt))
        # Go SortTopoInst: default(1/2/3) 排前，其余按名称
        children.sort(key=lambda x: (
            0 if x.get("default", x.get("bk_default", 0)) in (1, 2, 3) else 1,
            x.get(name_field, "") or ""))
        new_parent_nodes = {}
        for c in children:
            pid = c.get("bk_parent_id")
            pnode = node_by_id.get(pid)   # 跨级查找父节点（含 biz）
            if pnode is None:
                continue
            node = _make_topo_node(c, obj, obj_name_map=obj_name_map,
                                  name_field=name_field, id_field=child_id_field)
            pnode["child"].append(node)
            new_parent_nodes[c.get(child_id_field)] = node
            node_by_id[c.get(child_id_field)] = node
        parent_nodes = new_parent_nodes
    return [biz_node]


def _attach_host_counts(conn, supplier, biz_node):
    """后序聚合 host_count：module = 直连主机数；set/biz 累加子树。

    主机-模块关系来自 cc_ModuleHostConfig（host 无 bk_parent_id，故单独 join）。
    """
    host_cfg = list(conn.cc_ModuleHostConfig.find(
        {"bk_supplier_account": supplier, "bk_biz_id": biz_node.get("bk_inst_id")},
        {"bk_module_id": 1, "_id": 0}))
    module_host = {}
    for r in host_cfg:
        module_host[r.get("bk_module_id")] = module_host.get(r.get("bk_module_id"), 0) + 1

    def walk(node):
        cnt = 0
        for child in node.get("child", []):
            cnt += walk(child)
            if child.get("bk_obj_id") == "module":
                child["host_count"] = module_host.get(child.get("bk_inst_id"), 0)
                child["service_instance_count"] = 0
                cnt += child["host_count"]
            elif child.get("bk_obj_id") == "host":
                cnt += 1
        node["host_count"] = cnt
        node.setdefault("service_instance_count", 0)
        return cnt
    walk(biz_node)
    return biz_node


def _parse_body():
    """兼容多种请求体格式（JSON / form / raw），返回 dict。"""
    if request.is_json:
        return request.get_json() or {}
    elif request.form:
        return request.form.to_dict()
    elif request.data:
        try:
            return json.loads(request.data)
        except Exception:
            return {}
    return {}


def normalize_inst_doc(doc, obj_id):
    """对齐 bk-cmdb：实例搜索/拓扑响应始终附带 bk_inst_id 与 bk_obj_id。

    前端编辑实例时按 `instState.bk_obj_id` + `instState.bk_inst_id` 拼出
    PUT /update/instance/object/{obj}/inst/{id} 的 URL。若响应里缺这两个字段，
    前端拿到 undefined → URL 变成 inst/undefined → 更新 404。真实 bk-cmdb 的搜索层
    会补这两个字段，这里对齐。host 的真实主键是 bk_host_id、通用对象是 bk_inst_id。
    """
    if not doc:
        return doc
    id_field = get_inst_id_field(obj_id)
    if "bk_inst_id" not in doc and id_field in doc:
        doc["bk_inst_id"] = doc[id_field]
    # 补全模型标识，供前端编辑时拼 URL（bk_switch 等通用对象）
    if "bk_obj_id" not in doc:
        doc["bk_obj_id"] = obj_id
    return doc


def check_user_biz_permission(username, biz_id):
    """检查用户是否有权限访问特定业务
    
    Args:
        username: 用户名
        biz_id: 业务ID
        
    Returns:
        bool: 有权限返回True，否则返回False
    """
    conn = get_db_connection()
    if conn is None:
        return False
    
    # 内置超级管理员直接放行
    if Config.is_superuser(username):
        return True

    # 检查用户是否有该业务的访问权限
    user_biz = conn.user_business.find_one({
        'username': username,
        'bk_biz_id': biz_id
    })
    
    return user_biz is not None


def get_user_accessible_biz_ids(username):
    """获取用户可访问的所有业务ID列表
    
    Args:
        username: 用户名
        
    Returns:
        list: 业务ID列表
    """
    conn = get_db_connection()
    if conn is None:
        return []
    
    # 内置超级管理员可访问全部业务
    if Config.is_superuser(username):
        return [b['bk_biz_id'] for b in conn.cc_ApplicationBase.find(
            {}, {'bk_biz_id': 1, '_id': 0})]

    user_biz_list = list(conn.user_business.find(
        {'username': username},
        {'bk_biz_id': 1, '_id': 0}
    ))
    
    return [ub['bk_biz_id'] for ub in user_biz_list]


@object_bp.route('/find/objectclassification', methods=['POST'])
def find_object_classification():
    try:
        collection = get_mongo_collection('cc_ObjClassification')
        docs = collection.find({}, {'_id': 0})
        classifications = []
        seen_ids = set()
        
        for doc in docs:
            class_id = doc.get("bk_classification_id")
            if class_id and class_id not in seen_ids:
                classifications.append(doc)
                seen_ids.add(class_id)
            elif not class_id:
                # 如果没有 ID，直接添加
                classifications.append(doc)
        
        return make_response(data=classifications)
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/find/objectattgroup', methods=['POST'])
def find_object_att_group():
    try:
        conn = get_db_connection()

        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")
        
        docs = conn.cc_PropertyGroup.find({}, {'_id': 0})
        groups = []
        seen_group_ids = set()
        
        for doc in docs:
            group_id = doc.get("bk_group_id")
            obj_id = doc.get("bk_obj_id")
            unique_key = f"{obj_id}_{group_id}" if group_id and obj_id else str(id(doc))
            
            if unique_key not in seen_group_ids:
                groups.append(doc)
                seen_group_ids.add(unique_key)
        
        return make_response(data=groups)
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/find/objectattgroup/object/<obj_id>', methods=['POST'])
def find_object_att_group_by_obj(obj_id):
    try:
        groups = []
        collection = get_mongo_collection('cc_PropertyGroup')
        docs = collection.find({"bk_obj_id": obj_id})
        # 简单的排序
        docs_sorted = sorted(docs, key=lambda x: x.get("id", 0))
        for doc in docs_sorted:
            group = {
                "id": doc.get("id"),
                "bk_group_id": doc.get("bk_group_id"),
                "bk_group_name": doc.get("bk_group_name"),
                "bk_group_index": doc.get("bk_group_index"),
                "bk_obj_id": doc.get("bk_obj_id"),
                "is_collapse": doc.get("is_collapse", False)
            }
            groups.append(group)
        
        return make_response(data=groups)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


def _query_object_attr_by_obj_ids(obj_ids):
    """根据 bk_obj_id 列表查询 cc_ObjAttDes，并转换为前端所需的字段结构。"""
    # 前端会自动添加的 ID 属性，避免重复
    auto_add_id_props = {
        'biz': 'bk_biz_id',
        'host': 'bk_host_id',
        'set': 'bk_set_id',
        'module': 'bk_module_id',
        'process': 'bk_process_id',
        'plat': 'bk_cloud_id',
        'biz_set': 'bk_biz_set_id'
    }

    all_attributes = []
    seen_prop_ids = set()  # 用于去重，避免重复的 bk_property_id

    if not obj_ids:
        return all_attributes

    collection = get_mongo_collection('cc_ObjAttDes')
    docs = collection.find({"bk_obj_id": {"$in": obj_ids}})
    # 简单的排序
    docs_sorted = sorted(docs, key=lambda x: x.get("bk_property_index", x.get("id", 0)))
    for doc in docs_sorted:
        # 转换字段格式，匹配Go原版API返回的字段结构
        attr = {
            "id": doc.get("id"),
            "bk_supplier_account": doc.get("bk_supplier_account", "0"),
            "bk_obj_id": doc.get("bk_obj_id"),
            "bk_property_id": doc.get("bk_property_id"),
            "bk_property_name": doc.get("bk_property_name"),
            "bk_property_type": doc.get("bk_property_type"),
            "bk_property_group": doc.get("bk_property_group", "default"),
            "bk_property_index": doc.get("bk_property_index", 0),
            "unit": doc.get("unit", ""),
            "placeholder": doc.get("placeholder", ""),
            "editable": doc.get("editable", True),
            # 字段名兼容：Go 规范字段为无下划线的 ispre/isrequired/isonly；
            # 部分 initdb 文档带有遗留的 is_pre/is_required/is_only（且常与规范字段值冲突），
            # 优先取规范字段，缺失时回退到遗留字段，避免 bk_inst_name 等内置属性被误读成 False。
            "ispre": doc.get("ispre", doc.get("is_pre", False)),
            "isrequired": doc.get("isrequired", doc.get("is_required", False)),
            "isreadonly": doc.get("isreadonly", doc.get("is_readonly", False)),
            "isonly": doc.get("isonly", doc.get("is_only", False)),
            "bk_issystem": doc.get("bk_issystem", doc.get("bk_is_system", False)),
            "bk_isapi": doc.get("bk_isapi", doc.get("bk_is_api", False)),
            "option": doc.get("option", ""),
            "description": doc.get("description", ""),
            "creator": doc.get("creator", ""),
            "create_time": doc.get("create_time", ""),
            "last_time": doc.get("last_time", ""),
            "bk_property_group_name": doc.get("bk_property_group", "default")
        }
        # 确保布尔字段有正确的默认值
        if attr.get("editable") is None:
            attr["editable"] = True
        if attr.get("isreadonly") is None:
            attr["isreadonly"] = False

        # 去重：只添加没有见过的 bk_property_id
        prop_id = attr.get("bk_property_id")
        obj_type = attr.get("bk_obj_id")

        # 避免返回前端会自动添加的 ID 属性
        if prop_id and prop_id not in seen_prop_ids:
            # 跳过 bk_parent_id：主线模型的结构字段，不应作为用户可见的属性列
            # （Go createDefaultAttrs 虽会注入 bk_parent_id，但 UI 前端按规范隐含处理，
            #  不由属性列表公式展示。参见 Go object.go createDefaultAttrs IsSystem=true）。
            if prop_id == "bk_parent_id":
                continue
            # 检查是否是会被前端自动添加的 ID 属性
            auto_prop = auto_add_id_props.get(obj_type)
            if auto_prop and prop_id == auto_prop:
                # 跳过这个属性，因为前端会自动添加
                continue
            all_attributes.append(attr)
            seen_prop_ids.add(prop_id)

    return all_attributes


@object_bp.route('/find/objectattr', methods=['POST'])
def find_object_attr():
    try:
        # 兼容多种请求数据格式
        req_data = {}
        if request.is_json:
            req_data = request.get_json() or {}
        elif request.form:
            req_data = request.form.to_dict()
        elif request.data:
            try:
                import json
                req_data = json.loads(request.data)
            except:
                req_data = {}

        bk_obj_id = req_data.get('bk_obj_id', '')

        # 处理 $in 操作符
        if isinstance(bk_obj_id, dict) and '$in' in bk_obj_id:
            obj_ids = bk_obj_id['$in']
        elif isinstance(bk_obj_id, str):
            obj_ids = [bk_obj_id]
        else:
            obj_ids = []

        all_attributes = _query_object_attr_by_obj_ids(obj_ids)
        return make_response(data=all_attributes)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/find/objectattr/<bk_obj_id>', methods=['POST'])
def find_object_attr_by_obj(bk_obj_id):
    """兼容前端「高级筛选」按路径参数拉取指定对象属性：find/objectattr/<bk_obj_id>。"""
    try:
        all_attributes = _query_object_attr_by_obj_ids([bk_obj_id])
        return make_response(data=all_attributes)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/find/topomodelmainline', methods=['POST'])
def find_topo_model_mainline():
    """获取拓扑主线模型 — 动态查询 cc_ObjAsst（bk_asst_id = bk_mainline），对齐 Go 逻辑。

    Go 参考: src/scene_server/topo_server/logics/model/mainline_association.go
    主线链由 cc_ObjAsst 中 bk_asst_id="bk_mainline" 的关联定义，
    bk_obj_id=子级, bk_asst_obj_id=父级。
    """
    try:
        req_data = {}
        if request.is_json:
            req_data = request.get_json() or {}
        bk_supplier_account = req_data.get('bk_supplier_account', '0')

        # 1. 查询所有 bk_mainline 关联
        asst_coll = get_mongo_collection('cc_ObjAsst')
        mainline_assocs = list(asst_coll.find(
            {"bk_asst_id": "bk_mainline", "bk_supplier_account": bk_supplier_account},
            {"bk_obj_id": 1, "bk_asst_obj_id": 1, "_id": 0}
        ))
        if not mainline_assocs:
            return make_response(data=[])

        # 2. 构建 parent_map: child → parent
        #    以及反向映射 parent → child（主线链是线性的，每个 parent 至多一个 child）
        child_to_parent = {}   # bk_obj_id(子) → bk_asst_obj_id(父)
        parent_to_child = {}   # bk_asst_obj_id(父) → bk_obj_id(子)
        for assoc in mainline_assocs:
            child = assoc.get("bk_obj_id")
            parent = assoc.get("bk_asst_obj_id")
            child_to_parent[child] = parent
            parent_to_child[parent] = child

        all_children = set(child_to_parent.keys())
        all_parents = set(child_to_parent.values())

        # 根节点：是 parent 但不是 child
        roots = all_parents - all_children
        if not roots:
            return make_response(data=[])
        root = list(roots)[0]

        # 3. 从根节点开始遍历主线链
        obj_des_coll = get_mongo_collection('cc_ObjDes')
        topo_data = []
        current = root
        while current:
            obj_info = obj_des_coll.find_one(
                {"bk_obj_id": current, "bk_supplier_account": bk_supplier_account},
                {"_id": 0, "bk_obj_id": 1, "bk_obj_name": 1, "ispre": 1}
            ) or {}
            next_obj = parent_to_child.get(current)

            topo_data.append({
                "bk_obj_id": current,
                "bk_obj_name": obj_info.get("bk_obj_name", current),
                "bk_supplier_account": bk_supplier_account,
                "is_built-in": obj_info.get("ispre", True),
                "default": 0,
                "bk_next_obj": next_obj,
            })
            current = next_obj  # 移至下一级

        return make_response(data=topo_data)
    except Exception as e:
        print(f"获取拓扑主线模型失败: {e}")
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


def _calc_mainline_position(parent):
    """根据父模型 position 计算新建主线模型的位置（放在父模型右侧 300px）。

    cc_ObjDes.position 在 DB 中为 JSON 字符串，如 '{"bk_host_manage":{"x":-600,"y":-650}}'，
    需先 json.loads 再取嵌套的 x/y；新节点用其自身分类 key 包装回去，供前端 node.position.x/y 读取。
    """
    px, py = 0, 0
    raw = (parent or {}).get("position")
    if isinstance(raw, str):
        s = raw.strip()
        if s:
            try:
                raw = json.loads(s)
            except Exception:
                raw = None
    if isinstance(raw, dict):
        if "x" in raw and "y" in raw:
            px, py = raw.get("x") or 0, raw.get("y") or 0
        else:
            vals = [v for v in raw.values() if isinstance(v, dict) and "x" in v]
            if vals:
                px, py = vals[0].get("x") or 0, vals[0].get("y") or 0
    new_x = (px or 0) + 300
    new_y = (py or 0)
    return json.dumps({"bk_uncategorized": {"x": new_x, "y": new_y}})


def _propagate_mainline_inst(conn, supplier, bk_obj_id, bk_obj_name, parent_obj_id, child_obj_id, now):
    """对齐 Go inst.SetMainlineInstAssociation：批量把存量业务拓扑挂到新主线节点下。

    批处理策略与 Go 一致（**非逐业务查改**，而是）：
        A) 一次查询取回全部父实例（parent 实例，这里为 biz / 上层自定义主线实例）；
           为每个父实例建 1 个新主线对象实例，并记录 旧父实例 id -> 新实例 id 的映射
           new_parent_current_map；
        B) 一次 $in 查询取回全部直属子级（排除空闲机池），而非每个父实例各查一次；
        C) 在内存把子级按「新父实例 id」分组，每组仅 1 次批量 update_many（$in 子级 id），
           把子级 bk_parent_id 从旧父 id 改为新实例 id。
    整个过程同步阻塞（与 Go 一致），无 goroutine / 无事务回滚；Go 的并发仅存在于
    读侧主机/服务实例计数（fillStatistics 路径），与本写路径无关。

    实例名清洗对齐 Go mainlineSpecialCharacterRegexp：剥离 `# / , > < |`。
    集合/字段命名遵循本仓库 get_inst_collection_name / get_inst_id_field
    （对齐 bk-cmdb common/tablenames.go GetInstTableName）：内置对象用独立大写集合
    （如 cc_SetBase），自定义/通用对象用分片集合 cc_ObjectBase_0_pub_<obj_id>，主键
    bk_inst_id、名称 bk_inst_name。
    """
    import re as _re
    # 实例名清洗（对齐 Go：剥离 # / , > < |）
    instance_name = _re.sub(r'[#/,><|]', '', bk_obj_name or '')

    # 新主线对象实例：自定义对象 → cc_ObjectBase_0_pub_<bk_obj_id>，主键 bk_inst_id，名称 bk_inst_name
    inst_coll_name = get_inst_collection_name(bk_obj_id)
    inst_coll = conn[inst_coll_name]
    inst_id_field = get_inst_id_field(bk_obj_id)   # 自定义对象恒为 bk_inst_id
    inst_name_field = 'bk_inst_name'

    # 确保实例表存在（Go CreateObject 会建表 + 唯一索引）
    try:
        inst_coll.create_index([(inst_id_field, 1)], unique=True)
    except Exception:
        pass

    parent_coll = conn[get_inst_collection_name(parent_obj_id)]

    # 步骤 A：一次取回全部父实例，逐父实例建新实例并记录 old_parent_id -> new_inst_id 映射
    # 投影须含 bk_biz_id（对齐 Go：非 biz 父级时要把 bk_biz_id 透传到新实例，
    # 否则会错误回退成父实例 id 本身）
    new_parent_current_map = {}
    parent_ids = []
    for parent in parent_coll.find({"bk_supplier_account": supplier},
                                   {get_inst_id_field(parent_obj_id): 1, "bk_biz_id": 1, "_id": 0}):
        parent_id = parent.get(get_inst_id_field(parent_obj_id))
        if parent_id is None:
            continue
        parent_ids.append(parent_id)
        new_inst_id = next_sequence(conn, inst_coll_name)
        inst_doc = {
            inst_id_field: new_inst_id,
            inst_name_field: instance_name,
            "bk_obj_id": bk_obj_id,
            "bk_biz_id": parent.get("bk_biz_id", parent_id),
            "bk_parent_id": parent_id,
            "bk_supplier_account": supplier,
            "bk_ispaused": False,
            "bk_ishidden": False,
            "default": 0,
            "creator": "admin",
            "create_time": now,
            "last_time": now,
            "description": "",
        }
        inst_coll.insert_one(inst_doc)
        new_parent_current_map[parent_id] = new_inst_id

    # 无子级则提前结束（与 Go 一致，新实例已建好）
    child_base = conn[get_inst_collection_name(child_obj_id)] if child_obj_id else None
    if child_base is None or not parent_ids:
        return

    child_id_field = get_inst_id_field(child_obj_id)

    # 步骤 B：一次 $in 取回全部直属子级（set 子级排除空闲机池），而非逐父实例查
    child_filter = {"bk_parent_id": {"$in": parent_ids}}
    if child_obj_id == 'set':
        child_filter["default"] = {"$ne": 1}
    children = list(child_base.find(
        child_filter, {child_id_field: 1, "bk_parent_id": 1, "_id": 0}))

    # 步骤 C：内存分组，子级按「新父实例 id」聚组（对齐 Go expectParent2Children）
    expect_parent_2_children = {}
    for child in children:
        old_parent_id = child.get("bk_parent_id")
        new_parent_id = new_parent_current_map.get(old_parent_id)
        if new_parent_id is None:
            continue
        child_id = child.get(child_id_field)
        if child_id is None:
            continue
        expect_parent_2_children.setdefault(new_parent_id, []).append(child_id)

    # 每组一次批量更新（$in 子级 id），对齐 Go setMainlineParentInst
    for new_parent_id, child_ids in expect_parent_2_children.items():
        if not child_ids:
            continue
        child_base.update_many(
            {child_id_field: {"$in": child_ids}},
            {"$set": {"bk_parent_id": new_parent_id, "last_time": now}}
        )


@object_bp.route('/create/topomodelmainline', methods=['POST'])
def create_topo_model_mainline():
    """新建拓扑主线层级 —— 模型关系页「新建层级」按钮。

    前端 store: objectMainLineModule/createMainlineObject
    -> POST /api/v3/create/topomodelmainline

    入参（来自 handleCreateBusinessLevel）:
        {
            bk_asst_obj_id: <父模型 bk_obj_id>,   # 点击「新建层级」的节点（实际只会出现 biz）
            bk_obj_id: <新模型 id>,
            bk_obj_name: <新模型名>,
            bk_obj_icon: <图标>,
            bk_classification_id: 'bk_uncategorized',
            bk_supplier_account: '0',
            creator: 'admin'
        }

    逻辑（对齐 Go CreateMainlineAssociation）:
        1) 在 cc_ObjDes 新建模型对象（ispre=False）；
        2) 在 cc_ObjAsst 新建 bk_mainline 关联：新模型 -> 父模型；
        3) 若父模型已有下级，把该下级关联的父级从父模型改为新模型（重链主线：parent->new->child）；
        4) 批量重挂存量业务拓扑（对齐 Go inst.SetMainlineInstAssociation）：为每个存量业务创建
           新主线对象实例，并把原直属子级（如 set）的 bk_parent_id 重挂到新实例。
    """
    try:
        req_data = {}
        if request.is_json:
            req_data = request.get_json() or {}
        supplier = req_data.get('bk_supplier_account') or '0'
        parent_obj_id = req_data.get('bk_asst_obj_id')
        bk_obj_id = req_data.get('bk_obj_id')
        bk_obj_name = req_data.get('bk_obj_name')
        if not (parent_obj_id and bk_obj_id and bk_obj_name):
            return make_response(result=False, code=400,
                                 message="缺少必填参数 bk_asst_obj_id / bk_obj_id / bk_obj_name")

        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        obj_des_coll = get_mongo_collection('cc_ObjDes')
        obj_asst_coll = get_mongo_collection('cc_ObjAsst')

        # 父模型必须存在
        parent = obj_des_coll.find_one(
            {"bk_obj_id": parent_obj_id, "bk_supplier_account": supplier}, {"_id": 0})
        if not parent:
            return make_response(result=False, code=400,
                                 message="父模型不存在: bk_obj_id=%s" % parent_obj_id)

        # 新模型不能已存在
        if obj_des_coll.find_one({"bk_obj_id": bk_obj_id, "bk_supplier_account": supplier}):
            return make_response(result=False, code=400,
                                 message="模型已存在: bk_obj_id=%s" % bk_obj_id)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        position = _calc_mainline_position(parent)

        # 1) 新建 cc_ObjDes
        new_obj_id = next_sequence(conn, 'cc_ObjDes')
        obj_doc = {
            "id": new_obj_id,
            "bk_supplier_account": supplier,
            "bk_obj_id": bk_obj_id,
            "bk_obj_name": bk_obj_name,
            "bk_obj_icon": req_data.get('bk_obj_icon') or 'icon-cc-default',
            "bk_classification_id": req_data.get('bk_classification_id') or 'bk_uncategorized',
            "ispre": False,
            "bk_ishidden": False,
            "bk_ispaused": False,
            "creator": req_data.get('creator') or 'admin',
            "modifier": '',
            "create_time": now,
            "last_time": now,
            "description": '',
            "position": position,
        }
        obj_des_coll.insert_one(obj_doc)

        # 对齐 Go createDefaultAttrs：主线模型建好后注入默认属性
        # （bk_inst_name + 主线 bk_parent_id），否则前端实例表单无「实例名称」字段。
        ensure_model_default_attributes(bk_obj_id, supplier, is_mainline=True)

        # 2) 新建 bk_mainline 关联：新模型 -> 父模型
        asst_id = next_sequence(conn, 'cc_ObjAsst')
        asst_doc = {
            "id": asst_id,
            "bk_obj_id": bk_obj_id,
            "bk_asst_obj_id": parent_obj_id,
            "bk_asst_id": "bk_mainline",
            "bk_obj_asst_id": "%s_bk_mainline_%s" % (bk_obj_id, parent_obj_id),
            "bk_obj_asst_name": "",
            "bk_supplier_account": supplier,
            "ispre": False,
            "mapping": "1:1",
            "on_delete": "none",
            "creator": req_data.get('creator') or 'admin',
            "create_time": now,
            "last_time": now,
        }
        obj_asst_coll.insert_one(asst_doc)

        # 3) 重链：父模型已有下级时，把该下级的父级改为新模型
        existing_child_asst = obj_asst_coll.find_one({
            "bk_asst_id": "bk_mainline",
            "bk_asst_obj_id": parent_obj_id,
            "bk_obj_id": {"$ne": bk_obj_id},
            "bk_supplier_account": supplier,
        })
        child_obj_id = existing_child_asst.get("bk_obj_id") if existing_child_asst else None
        if existing_child_asst:
            obj_asst_coll.update_one(
                {"_id": existing_child_asst["_id"]},
                {"$set": {
                    "bk_asst_obj_id": bk_obj_id,
                    "bk_obj_asst_id": "%s_bk_mainline_%s" % (child_obj_id, bk_obj_id),
                    # 重链后的关联不再属于「预定义」，须置 ispre=False，
                    # 否则后续 DeleteMainlineAssociation 的 ispre 守门会误拦（对齐 Go
                    # createMainlineObjectAssociation 中 IsPre=false 的语义）。
                    "ispre": False,
                    "last_time": now,
                }}
            )

        # 4) 批量重挂存量业务拓扑（对齐 Go inst.SetMainlineInstAssociation）
        _propagate_mainline_inst(conn, supplier, bk_obj_id, bk_obj_name,
                                 parent_obj_id, child_obj_id, now)

        obj_doc.pop("_id", None)
        return make_response(data=obj_doc)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


def _reset_mainline_inst(conn, supplier, target_obj_id, child_obj_id, parent_obj_id, now):
    """对齐 Go inst.ResetMainlineInstAssociation：删除主线对象实例时，把其直属子级实例
    重挂到祖父(parent)实例，并删除该主线对象的所有实例（逆 ``_propagate_mainline_inst``）。

    数据关系（与 ``_propagate_mainline_inst`` 一致）：
      - target 实例的 ``bk_parent_id`` 指向祖父(parent)实例 id；
      - child 实例的 ``bk_parent_id`` 指向 target 实例 id；
    重挂：把 child 实例的 ``bk_parent_id`` 改为对应 target 实例的 ``bk_parent_id``（祖父 id），
    随后删除全部 target 实例。同名冲突（重挂后与祖父已有子级同名）整体中止，
    对齐 Go ``CCErrTopoDeleteMainLineObjectAndInstNameRepeat``。无实例则提前返回（no-op）。
    """
    from collections import Counter

    target_id_field = get_inst_id_field(target_obj_id)
    child_id_field = get_inst_id_field(child_obj_id)

    target_coll = conn[get_inst_collection_name(target_obj_id)]
    child_coll = conn[get_inst_collection_name(child_obj_id)]

    target_insts = list(target_coll.find(
        {"bk_supplier_account": supplier},
        {target_id_field: 1, "bk_parent_id": 1, "bk_inst_name": 1, "_id": 0}))
    if not target_insts:
        return  # 无实例，无需重挂/删除

    # 收集重挂计划，并校验同名冲突（对齐 Go checkInstNameRepeat）
    reparent_map = {}       # target 实例 id -> (祖父实例 id, [child 实例 id...])
    planned = []            # [(祖父实例 id, child 实例名)]  将被重挂到祖父的子级
    reparented_ids = set()  # 所有将被移动的子级实例 id
    for t in target_insts:
        t_id = t.get(target_id_field)
        gp_id = t.get("bk_parent_id")
        if t_id is None or gp_id is None:
            continue
        children = list(child_coll.find(
            {"bk_parent_id": t_id, "bk_supplier_account": supplier},
            {child_id_field: 1, "bk_inst_name": 1, "_id": 0}))
        child_ids = [c.get(child_id_field) for c in children if c.get(child_id_field) is not None]
        reparent_map[t_id] = (gp_id, child_ids)
        reparented_ids.update(child_ids)
        for c in children:
            planned.append((gp_id, c.get("bk_inst_name")))

    # 祖父实例「原本就已有」的子级名（排除本次将被移动的子级，因其当前 bk_parent_id 可能
    # 与祖父实例 id 数值相同导致误判；移动子级不算「已存在」，见 appsys/biz 实例 id 重叠场景）
    gp_ids = {gp for (gp, _) in planned}
    gp_existing = {gp: set() for gp in gp_ids}
    for gp in gp_ids:
        for c in child_coll.find({"bk_parent_id": gp, "bk_supplier_account": supplier},
                                 {child_id_field: 1, "bk_inst_name": 1, "_id": 0}):
            if c.get(child_id_field) in reparented_ids:
                continue
            gp_existing[gp].add(c.get("bk_inst_name"))

    # 重挂后每个祖父下的「最终子级名」= 原有(排除移动) + 本次重挂；若有重复则冲突
    gp_final = {gp: list(names) for gp, names in gp_existing.items()}
    for (gp, name) in planned:
        gp_final[gp].append(name)
    for gp, names in gp_final.items():
        if len(names) != len(set(names)):
            raise ModelError("删除主线对象 %s 实例时发生同名冲突，已中止" % target_obj_id, code=400)

    # 执行重挂
    for t_id, (gp_id, child_ids) in reparent_map.items():
        if child_ids:
            child_coll.update_many(
                {child_id_field: {"$in": child_ids}},
                {"$set": {"bk_parent_id": gp_id, "last_time": now}})

    # 删除 target 实例
    target_coll.delete_many({"bk_supplier_account": supplier})


@object_bp.route('/delete/topomodelmainline/object/<bk_obj_id>', methods=['DELETE'])
def delete_topo_model_mainline(bk_obj_id):
    """删除拓扑主线层级 —— 模型详情页「删除」按钮（isMainLineModel 时调用）。

    前端 store: objectMainLineModule/deleteMainlineObject
    -> DELETE /api/v3/delete/topomodelmainline/object/{bk_obj_id}

    对齐 Go DeleteMainLineObject -> DeleteMainlineAssociation：
      1) 读取上下游并校验（get_mainline_neighbors）；
      2) 实例重挂（逆 _propagate_mainline_inst），在元数据删除前完成；
      3) 元数据删除 + 重链（core.delete_mainline_object）。
    """
    try:
        supplier = (request.args.get('bk_supplier_account') or
                    (request.get_json(silent=True) or {}).get('bk_supplier_account') or '0')
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        # 1) 读取上下游（校验），用于实例重挂
        nb = get_mainline_neighbors(bk_obj_id)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 2) 实例重挂（逆 _propagate_mainline_inst），在元数据删除前
        _reset_mainline_inst(conn, supplier, bk_obj_id,
                             nb["child_obj_id"], nb["parent_obj_id"], now)

        # 3) 元数据删除 + 重链
        result = delete_mainline_object(bk_obj_id)
        return make_response(data=result)
    except ModelError as e:
        return make_response(result=False, code=getattr(e, 'code', 400), message=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/find/classificationobject', methods=['POST'])
def find_classification_object():
    """获取模型分类"""
    try:
        # 兼容多种请求数据格式
        req_data = {}
        if request.is_json:
            req_data = request.get_json() or {}
        elif request.form:
            req_data = request.form.to_dict()
        elif request.data:
            try:
                import json
                req_data = json.loads(request.data)
            except:
                req_data = {}
        
        bk_supplier_account = req_data.get('bk_supplier_account', '0')
        
        # 从数据库读取对象和分类
        class_map = {}
        
        # 先读取所有分类
        collection_cls = get_mongo_collection('cc_ObjClassification')
        classifications = list(collection_cls.find({}, {'_id': 0}))
        for cls in classifications:
            cls_id = cls.get("bk_classification_id")
            class_map[cls_id] = {
                "bk_classification_id": cls.get("bk_classification_id"),
                "bk_classification_name": cls.get("bk_classification_name", cls_id),
                "bk_classification_icon": cls.get("bk_classification_icon", "icon-cc-default"),
                "bk_classification_type": cls.get("bk_classification_type", "inner"),
                "id": cls.get("id"),
                "is_built-in": cls.get("is_built_in", True),
                "bk_objects": []
            }
        
        # 读取所有对象
        # 修复：对象模型定义由 initdb 写入 cc_ObjDes（共 11 个模型），cc_ObjectBase 为空集合；
        # 之前误读 cc_ObjectBase 导致「模型」页（find/classificationobject）返回空。
        collection_obj = get_mongo_collection('cc_ObjDes')
        docs = collection_obj.find({})
        # 简单的排序
        docs_sorted = sorted(docs, key=lambda x: x.get("id", 0))
        db_objects = []
        for doc in docs_sorted:
            db_objects.append({
                "id": doc.get("id"),
                "bk_obj_id": doc.get("bk_obj_id"),
                "bk_obj_name": doc.get("bk_obj_name"),
                "bk_classification_id": doc.get("bk_classification_id"),
                "bk_supplier_account": doc.get("bk_supplier_account"),
                "bk_obj_icon": doc.get("bk_obj_icon"),
                "is_built-in": doc.get("ispre"),
                "is_pre": doc.get("is_pre"),
                "bk_ispaused": doc.get("bk_ispaused", False),
                "bk_ishidden": doc.get("bk_ishidden", False),
            })
        
        # 将对象按分类分组
        for obj in db_objects:
            cls_id = obj.get("bk_classification_id")
            if cls_id in class_map:
                class_map[cls_id]["bk_objects"].append(obj)
            else:
                # 创建默认分类
                if cls_id not in class_map:
                    class_map[cls_id] = {
                        "bk_classification_id": cls_id,
                        "bk_classification_name": cls_id,
                        "bk_classification_icon": "icon-cc-default",
                        "bk_classification_type": "inner",
                        "id": len(class_map) + 1,
                        "is_built-in": True,
                        "bk_objects": []
                    }
                class_map[cls_id]["bk_objects"].append(obj)
        
        class_data = list(class_map.values())
        return make_response(data=class_data)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"获取模型分类失败: {e}")
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/topoinstchild/object/<obj_id>/biz/<int:biz_id>/inst/<int:inst_id>', methods=['GET'])
def get_inst_topo_child(obj_id, biz_id, inst_id):
    """获取子节点实例"""
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        result = []
        
        if obj_id == "biz":
            # 业务节点下是集群
            sets = list(conn.cc_SetBase.find({
                "bk_biz_id": biz_id,
                "bk_data_status": {"$ne": "disabled"}
            }))
            
            for s in sets:
                result.append({
                    "bk_obj_id": "set",
                    "bk_inst_id": s.get("bk_set_id"),
                    "bk_inst_name": s.get("bk_set_name"),
                    "default": 0
                })
                
        elif obj_id == "set":
            # 集群节点下是模块
            modules = list(conn.cc_ModuleBase.find({
                "bk_set_id": inst_id,
                "bk_biz_id": biz_id,
                "bk_data_status": {"$ne": "disabled"}
            }))
            
            for m in modules:
                result.append({
                    "bk_obj_id": "module",
                    "bk_inst_id": m.get("bk_module_id"),
                    "bk_inst_name": m.get("bk_module_name"),
                    "default": 0
                })
        
        return make_response(data=result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/find/topopath/biz/<int:biz_id>', methods=['POST'])
def find_topo_path(biz_id):
    """获取拓扑路径

    根据请求体中的 topo_nodes 返回每个节点从根业务到自身的完整路径。
    请求示例：{"topo_nodes":[{"bk_obj_id":"module","bk_inst_id":1}]}
    响应示例：{"nodes":[{"topo_node":{"bk_obj_id":"module","bk_inst_id":1,...},
                            "topo_path":[{"bk_obj_id":"biz",...},{bk_obj_id":"set",...},{bk_obj_id":"module",...}]}]}
    """
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        req_data = request.get_json() or {}
        topo_nodes = req_data.get("topo_nodes", []) or []
        if not isinstance(topo_nodes, list):
            topo_nodes = []

        nodes = []
        for node in topo_nodes:
            obj_id = node.get("bk_obj_id")
            inst_id = node.get("bk_inst_id")
            if not obj_id or inst_id is None:
                continue

            path = []
            topo_node = None

            if obj_id == "biz":
                biz = conn.cc_ApplicationBase.find_one({"bk_biz_id": inst_id}, {"_id": 0})
                if biz:
                    topo_node = {"bk_obj_id": "biz", "bk_inst_id": inst_id, "bk_inst_name": biz.get("bk_biz_name", "")}
                    path = [topo_node]

            elif obj_id == "set":
                set_doc = conn.cc_SetBase.find_one({"bk_set_id": inst_id, "bk_data_status": {"$ne": "disabled"}}, {"_id": 0})
                if set_doc:
                    biz_id_inner = set_doc.get("bk_biz_id")
                    biz = conn.cc_ApplicationBase.find_one({"bk_biz_id": biz_id_inner}, {"_id": 0}) if biz_id_inner else None
                    biz_node = {"bk_obj_id": "biz", "bk_inst_id": biz_id_inner, "bk_inst_name": biz.get("bk_biz_name", "")} if biz else None
                    set_node = {"bk_obj_id": "set", "bk_inst_id": inst_id, "bk_inst_name": set_doc.get("bk_set_name", "")}
                    topo_node = set_node
                    path = [n for n in [biz_node, set_node] if n]

            elif obj_id == "module":
                module = conn.cc_ModuleBase.find_one({"bk_module_id": inst_id, "bk_data_status": {"$ne": "disabled"}}, {"_id": 0})
                if module:
                    set_id = module.get("bk_set_id")
                    biz_id_inner = module.get("bk_biz_id")
                    if not biz_id_inner and set_id:
                        set_doc = conn.cc_SetBase.find_one({"bk_set_id": set_id}, {"_id": 0, "bk_biz_id": 1})
                        if set_doc:
                            biz_id_inner = set_doc.get("bk_biz_id")
                    biz = conn.cc_ApplicationBase.find_one({"bk_biz_id": biz_id_inner}, {"_id": 0}) if biz_id_inner else None
                    set_doc = conn.cc_SetBase.find_one({"bk_set_id": set_id, "bk_data_status": {"$ne": "disabled"}}, {"_id": 0}) if set_id else None

                    biz_node = {"bk_obj_id": "biz", "bk_inst_id": biz_id_inner, "bk_inst_name": biz.get("bk_biz_name", "")} if biz else None
                    set_node = {"bk_obj_id": "set", "bk_inst_id": set_id, "bk_inst_name": set_doc.get("bk_set_name", "")} if set_doc else None
                    module_node = {"bk_obj_id": "module", "bk_inst_id": inst_id, "bk_inst_name": module.get("bk_module_name", "")}
                    topo_node = module_node
                    path = [n for n in [biz_node, set_node, module_node] if n]

            elif obj_id == "host":
                # 主机可能属于多个模块，返回其每个模块路径
                relations = list(conn.cc_ModuleHostConfig.find({"bk_host_id": inst_id}, {"_id": 0, "bk_biz_id": 1, "bk_set_id": 1, "bk_module_id": 1}))
                if relations:
                    # 取第一个关系构建路径
                    rel = relations[0]
                    biz_id_inner = rel.get("bk_biz_id")
                    set_id = rel.get("bk_set_id")
                    module_id = rel.get("bk_module_id")
                    host_doc = conn.cc_HostBase.find_one({"bk_host_id": inst_id}, {"_id": 0, "bk_host_innerip": 1, "bk_host_name": 1})
                    host_name = host_doc.get("bk_host_innerip") or host_doc.get("bk_host_name") if host_doc else ""
                    host_name = host_name.split(",")[0] if isinstance(host_name, str) and "," in host_name else host_name

                    biz = conn.cc_ApplicationBase.find_one({"bk_biz_id": biz_id_inner}, {"_id": 0}) if biz_id_inner else None
                    set_doc = conn.cc_SetBase.find_one({"bk_set_id": set_id, "bk_data_status": {"$ne": "disabled"}}, {"_id": 0}) if set_id else None
                    module = conn.cc_ModuleBase.find_one({"bk_module_id": module_id, "bk_data_status": {"$ne": "disabled"}}, {"_id": 0}) if module_id else None

                    biz_node = {"bk_obj_id": "biz", "bk_inst_id": biz_id_inner, "bk_inst_name": biz.get("bk_biz_name", "")} if biz else None
                    set_node = {"bk_obj_id": "set", "bk_inst_id": set_id, "bk_inst_name": set_doc.get("bk_set_name", "")} if set_doc else None
                    module_node = {"bk_obj_id": "module", "bk_inst_id": module_id, "bk_inst_name": module.get("bk_module_name", "")} if module else None
                    host_node = {"bk_obj_id": "host", "bk_inst_id": inst_id, "bk_inst_name": host_name}
                    topo_node = host_node
                    path = [n for n in [biz_node, set_node, module_node, host_node] if n]

            if topo_node and path:
                nodes.append({
                    "topo_node": topo_node,
                    "topo_path": path
                })

        return make_response(data={"nodes": nodes})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/find/biz_set/topo_path', methods=['POST'])
def find_biz_set_topo_path():
    """获取业务集拓扑路径"""
    try:
        req_data = request.get_json() or {}
        bk_biz_set_id = req_data.get('bk_biz_set_id')
        bk_parent_obj_id = req_data.get('bk_parent_obj_id')
        bk_parent_id = req_data.get('bk_parent_id')
        
        # 构建拓扑路径
        path = []
        
        # 添加业务集节点
        path.append({
            "bk_obj_id": "bk_biz_set_obj",
            "bk_obj_name": "业务集",
            "bk_inst_id": bk_biz_set_id,
            "bk_inst_name": f"业务集_{bk_biz_set_id}"
        })
        
        return make_response(data=path)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/topo/internal/<supplier_account>/<int:bk_biz_id>/with_statistics', methods=['GET'])
def topo_internal_with_statistics_new(supplier_account, bk_biz_id):
    """获取内部拓扑（空闲机池）及统计信息。

    复刻原 bk-cmdb 语义：空闲机池是 cc_SetBase 中 bk_default=1（或名为“空闲机池”）的真实集群，
    其下挂 空闲机/故障机/待回收 等默认模块。前端业务拓扑组件会把本接口结果以 is_idle_set 前置
    到业务拓扑 sets 列表中（l.unshift(d)），因此业务拓扑接口必须排除空闲机池，避免重复。
    """
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        # 空闲机池模块的 default 值映射（按名称兜底，因部分数据缺失 default 字段）
        idle_module_default = {"空闲机": 1, "故障机": 2, "待回收": 3}

        # 定位空闲机池集群：空闲机池是「资源池」(bk_biz_id=1, default=1) 的内置集群，
        # 与“当前业务”无关。bk-cmdb 的「转移到空闲机」对话框会按主机所在业务来请求本接口
        # （bk_biz_id 可能是任意业务而非资源池），若只在请求业务内查找，非资源池业务会查不到
        # 空闲机池，从而退化成 bk_set_id=0 / module=[] 的空节点 —— 前端便把它渲染成普通集群图标
        # 且因无可选模块而“无法编辑”。故：请求业务内找不到时回退到资源池业务，
        # 始终返回真实的空闲机池（含其模块），并用空闲机池自身的 bk_biz_id 查模块/主机。
        res_pool = conn.cc_ApplicationBase.find_one(
            {"default": 1}, {"bk_biz_id": 1, "_id": 0})
        res_biz_id = res_pool.get("bk_biz_id") if res_pool else 1
        candidate_biz_ids = [bk_biz_id]
        if res_biz_id is not None and res_biz_id != bk_biz_id:
            candidate_biz_ids.append(res_biz_id)

        idle_set = None
        for _biz in candidate_biz_ids:
            idle_set = conn.cc_SetBase.find_one({
                "bk_biz_id": _biz,
                "bk_data_status": {"$ne": "disabled"},
                "$or": [{"default": 1}, {"bk_default": 1}, {"bk_set_name": "空闲机池"}]
            })
            if idle_set:
                break
        if not idle_set:
            idle_set = conn.cc_SetBase.find_one({
                "bk_biz_id": res_biz_id,
                "bk_data_status": {"$ne": "disabled"},
                "bk_set_name": {"$regex": "空闲机池"}
            })

        if not idle_set:
            # 退化：仍返回结构合法的空闲机池节点，避免前端解构报错
            return make_response(data={
                "bk_set_id": 0,
                "bk_set_name": "空闲机池",
                "default": 1,
                "module": []
            })

        idle_set_id = idle_set.get("bk_set_id")
        idle_biz_id = idle_set.get("bk_biz_id")
        host_relations = list(conn.cc_ModuleHostConfig.find({
            "bk_biz_id": idle_biz_id, "bk_set_id": idle_set_id
        }))

        modules = list(conn.cc_ModuleBase.find({
            "bk_biz_id": idle_biz_id,
            "bk_set_id": idle_set_id,
            "bk_data_status": {"$ne": "disabled"}
        }))

        module_list = []
        for m in modules:
            mid = m.get("bk_module_id")
            mname = m.get("bk_module_name", "")
            default = m.get("default")
            if default is None:
                default = m.get("bk_default") or idle_module_default.get(mname, 0)
            host_count = len([r for r in host_relations if r.get("bk_module_id") == mid])
            module_list.append({
                "bk_module_id": mid,
                "bk_module_name": mname,
                "default": default,
                "host_count": host_count,
                "service_instance_count": 0
            })

        result = {
            "bk_set_id": idle_set_id,
            "bk_set_name": idle_set.get("bk_set_name", "空闲机池"),
            "default": 1,
            # 顶层 host_count：空闲机池下各内置模块主机数之和。
            # 前端 2322.js 的 setNodeCount 会按 bk_obj_id+bk_inst_id 匹配并把 node.host_count
            # 设为本响应的顶层 host_count；若不返回，空闲机池节点徽标计数会显示 0。
            "host_count": sum(m.get("host_count", 0) for m in module_list),
            "module": module_list
        }
        return make_response(data=result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/object/count', methods=['POST'])
def object_count():
    """批量获取对象实例数量"""
    try:
        req_data = {}
        if request.is_json:
            req_data = request.get_json() or {}
        elif request.form:
            req_data = request.form.to_dict()
        elif request.data:
            try:
                import json
                req_data = json.loads(request.data)
            except:
                req_data = {}
        
        condition = req_data.get('condition', {})
        obj_ids = condition.get('obj_ids', [])
        
        result = []
        
        for obj_id in obj_ids:
            count = 0
            try:
                collection_name = get_inst_collection_name(obj_id)
                query = {"bk_data_status": {"$ne": "disabled"}} if obj_id == 'biz' else {}
                collection = get_mongo_collection(collection_name)
                count = collection.count_documents(query)
            except Exception as e:
                print(f"统计 {obj_id} 实例数量失败: {e}")
                count = 0
            
            result.append({
                "bk_obj_id": obj_id,
                "inst_count": count,
                "error": ""
            })
        
        return make_response(data=result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/search/instances/object/<obj_id>', methods=['POST'])
def search_instances_by_obj(obj_id):
    """搜索特定对象的实例列表"""
    try:
        req_data = {}
        if request.is_json:
            req_data = request.get_json() or {}
        elif request.form:
            req_data = request.form.to_dict()
        elif request.data:
            try:
                import json
                req_data = json.loads(request.data)
            except:
                req_data = {}
        
        fields = req_data.get('fields', [])
        page = req_data.get('page', {})
        # 将前端 conditions（{condition, rules}）/ condition（扁平）/ time_condition
        # 统一转换为合法 Mongo 查询；空条件返回 {}（匹配全部）。
        query = build_instance_query(req_data)

        start = page.get('start', 0)
        limit = page.get('limit', 20)
        sort = page.get('sort', 'bk_inst_id')

        try:
            collection_name = get_inst_collection_name(obj_id)
            
            collection = get_mongo_collection(collection_name)
            cursor = collection.find(query)
            
            if sort:
                sort_direction = 1
                if sort.startswith('-'):
                    sort_direction = -1
                    sort = sort[1:]
                cursor = cursor.sort(sort, sort_direction)
            
            total_count = collection.count_documents(query)
            
            cursor = cursor.skip(start).limit(limit)
            
            instances = []
            for doc in cursor:
                doc.pop('_id', None)
                doc = normalize_inst_doc(doc, obj_id)

                if fields and len(fields) > 0:
                    filtered_doc = {}
                    for field in fields:
                        if field in doc:
                            filtered_doc[field] = doc[field]
                    instances.append(filtered_doc)
                else:
                    instances.append(doc)
            
            return make_response(data={
                "count": total_count,
                "info": instances
            })
        except Exception as e:
            print(f"查询 {obj_id} 实例失败: {e}")
            return make_response(data={
                "count": 0,
                "info": []
            })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/count/instances/object/<obj_id>', methods=['POST'])
def count_instances_by_obj(obj_id):
    """统计特定对象的实例数量"""
    try:
        req_data = {}
        if request.is_json:
            req_data = request.get_json() or {}
        elif request.form:
            req_data = request.form.to_dict()
        elif request.data:
            try:
                import json
                req_data = json.loads(request.data)
            except:
                req_data = {}
        
        query = build_instance_query(req_data)

        count = 0
        try:
            collection_name = get_inst_collection_name(obj_id)
            # biz 默认排除 disabled
            if obj_id == 'biz' and not conditions:
                query = {"bk_data_status": {"$ne": "disabled"}}
            collection = get_mongo_collection(collection_name)
            count = collection.count_documents(query)
        except Exception as e:
            print(f"统计 {obj_id} 实例数量失败: {e}")
            count = 0
        
        return make_response(data={"count": count})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/find/topoinst_with_statistics/biz/<int:bk_biz_id>', methods=['POST'])
def find_topo_inst_with_statistics(bk_biz_id):
    """获取业务拓扑实例及统计信息"""
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        # 获取当前用户
        current_username = getattr(g, 'current_user', None)
        
        # 检查用户权限（如果能获取到用户名，必须检查权限）
        accessible_biz_ids = []
        if current_username:
            accessible_biz_ids = get_user_accessible_biz_ids(current_username)
        
        # 如果有用户名但没有可访问的业务，或者请求的业务不在可访问列表中，返回空结果
        if current_username and bk_biz_id not in accessible_biz_ids:
            return make_response(data=[])

        # 查询业务数据
        business = conn.cc_ApplicationBase.find_one({"bk_biz_id": bk_biz_id})
        if not business:
            # 如果没有找到指定业务，且用户有可访问的业务，返回第一个用户有权限的业务
            if current_username and accessible_biz_ids:
                for biz_id in accessible_biz_ids:
                    business = conn.cc_ApplicationBase.find_one({"bk_biz_id": biz_id})
                    if business:
                        bk_biz_id = biz_id
                        break
            else:
                # 如果没有任何用户信息，返回空结构
                return make_response(data=[])
        
        if not business:
            # 如果没有任何业务，返回空结构
            return make_response(data=[])

        supplier = (request.get_json(silent=True) or {}).get('bk_supplier_account') or '0'
        biz_id = business.get("bk_biz_id")

        # 沿动态主线链构建实例树（with_idle_pool=False：空闲机池不单独成节点，
        # 对齐 Go withDefault=false；其主机仍计入业务总数）。
        tree = build_mainline_inst_tree(conn, supplier, biz_id, with_idle_pool=False)
        if not tree:
            return make_response(data=[])
        biz_node = tree[0]

        # 各 module 直连主机数 + set/biz 累加（后序聚合）
        _attach_host_counts(conn, supplier, biz_node)
        # 业务节点总数含空闲机池主机（bk-cmdb 语义），覆盖聚合值
        total_host_count = conn.cc_ModuleHostConfig.count_documents(
            {"bk_supplier_account": supplier, "bk_biz_id": biz_id})
        biz_node["host_count"] = total_host_count
        biz_node.setdefault("service_instance_count", 0)

        return make_response(data=[biz_node])
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))







@object_bp.route('/find/topoinst/bk_biz_id/<int:bk_biz_id>/host/<int:bk_host_id>', methods=['POST'])
def find_topoinst_by_host(bk_biz_id, bk_host_id):
    """主机所属拓扑路径：bk_biz_id -> set -> module -> host。

    对应前端「主机详情 / 所属拓扑」页签请求的
    POST /find/topoinst/bk_biz_id/{bk_biz_id}/host/{bk_host_id}，
    此前无对应路由（兜底返回空），导致所属拓扑为空。复刻 bk-cmdb 返回单条拓扑路径。
    """
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        rel = conn.cc_ModuleHostConfig.find_one({"bk_biz_id": bk_biz_id, "bk_host_id": bk_host_id})
        if not rel:
            return make_response(data=[])

        set_id = rel.get("bk_set_id")
        module_id = rel.get("bk_module_id")

        biz = conn.cc_ApplicationBase.find_one({"bk_biz_id": bk_biz_id}) or {}
        set_doc = conn.cc_SetBase.find_one({"bk_set_id": set_id}) or {}
        module_doc = conn.cc_ModuleBase.find_one({"bk_module_id": module_id}) or {}
        host_doc = conn.cc_HostBase.find_one({"bk_host_id": bk_host_id}) or {}

        host_node = {
            "bk_obj_id": "host",
            "bk_inst_id": bk_host_id,
            "bk_inst_name": host_doc.get("bk_host_name", ""),
            "host_count": 1,
            "child": []
        }
        module_node = {
            "bk_obj_id": "module",
            "bk_inst_id": module_id,
            "bk_inst_name": module_doc.get("bk_module_name", ""),
            "default": module_doc.get("bk_default", 0),
            "host_count": 1,
            "child": [host_node]
        }
        set_node = {
            "bk_obj_id": "set",
            "bk_inst_id": set_id,
            "bk_inst_name": set_doc.get("bk_set_name", ""),
            "default": set_doc.get("bk_default", 0),
            "host_count": 1,
            "child": [module_node]
        }
        biz_node = {
            "bk_obj_id": "biz",
            "bk_inst_id": bk_biz_id,
            "bk_inst_name": biz.get("bk_biz_name", ""),
            "default": biz.get("bk_default", 0),
            "host_count": 1,
            "child": [set_node]
        }
        return make_response(data=[biz_node])
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/find/topoinstnode/host_serviceinst_count/<int:biz_id>', methods=['POST'])
def find_topoinstnode_host_serviceinst_count(biz_id):
    """获取拓扑节点的主机和服务实例统计信息"""
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")
        
        # 兼容多种请求数据格式
        req_data = {}
        if request.is_json:
            req_data = request.get_json() or {}
        elif request.form:
            req_data = request.form.to_dict()
        elif request.data:
            try:
                import json
                req_data = json.loads(request.data)
            except:
                req_data = {}
        
        conditions = req_data.get('condition', [])
        
        # 节点可能属于资源池（空闲机池 set/module 归属资源池 biz=1），
        # 不能一概用 URL 上的当前业务 biz_id 查关系，否则空闲机池计数恒为 0。
        # 按节点真实归属业务加载关系（按业务去重缓存，避免重复全表扫描）。
        rel_cache = {}
        def get_relations(b):
            if b not in rel_cache:
                rel_cache[b] = list(conn.cc_ModuleHostConfig.find({"bk_biz_id": b}))
            return rel_cache[b]

        # 为每个节点返回统计数据
        result = []
        for node in conditions:
            bk_obj_id = node.get('bk_obj_id')
            bk_inst_id = node.get('bk_inst_id')

            # 节点真实归属业务：set/module 唯一归属某一业务，空闲机池归属资源池 biz=1。
            # 用其真实业务查关系与模块，而非请求里的“当前业务” biz_id。
            node_biz = biz_id
            if bk_obj_id == "set":
                sdoc = conn.cc_SetBase.find_one({"bk_set_id": bk_inst_id}, {"bk_biz_id": 1, "_id": 0})
                node_biz = sdoc.get("bk_biz_id", biz_id) if sdoc else biz_id
            elif bk_obj_id == "module":
                mdoc = conn.cc_ModuleBase.find_one({"bk_module_id": bk_inst_id}, {"bk_biz_id": 1, "_id": 0})
                node_biz = mdoc.get("bk_biz_id", biz_id) if mdoc else biz_id
            elif bk_obj_id == "biz":
                node_biz = bk_inst_id if bk_inst_id else biz_id

            host_relations = get_relations(node_biz)

            host_count = 0
            if bk_obj_id == "module":
                # 统计模块下的主机
                host_count = len([r for r in host_relations if r.get("bk_module_id") == bk_inst_id])
            elif bk_obj_id == "set":
                # 集群主机数 = 其下所有模块的主机数之和（按模块聚合），
                # 不能依赖关系记录里的 bk_set_id —— 经“主机转移/加入模块”写入的关系可能缺失该字段，
                # 否则 set 计数恒为 0（与真实归属不符）。
                set_module_ids = [m["bk_module_id"] for m in conn.cc_ModuleBase.find(
                    {"bk_biz_id": node_biz, "bk_set_id": bk_inst_id,
                     "bk_data_status": {"$ne": "disabled"}},
                    {"bk_module_id": 1, "_id": 0})]
                host_count = len([r for r in host_relations
                                  if r.get("bk_module_id") in set_module_ids])
            elif bk_obj_id == "biz":
                # 统计业务下的所有主机
                host_count = len(host_relations)

            result.append({
                "bk_obj_id": bk_obj_id,
                "bk_inst_id": bk_inst_id,
                "host_count": host_count,
                "service_instance_count": 0
            })
        
        return make_response(data=result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


class _InstanceCreateError(Exception):
    """创建实例时校验/唯一性失败，携带可供前端展示的错误信息。"""
    def __init__(self, message):
        self.message = message


def _create_one_instance(obj_id, req_data):
    """创建单个对象实例的核心逻辑（单条与批量创建共用）。

    成功返回新实例主键 id（int）；失败抛出 _InstanceCreateError(message)。
    注意：bk_parent_id / bk_biz_id 等拓扑挂接字段由调用方在 req_data 中传入，
    本函数不自动推算父级（对齐主线层级「新增节点」语义）。
    """
    id_field = get_inst_id_field(obj_id)
    # 后端自动生成的主键字段（不计入必填校验）
    auto_id_props = {
        "bk_biz_id", "bk_set_id", "bk_module_id", "bk_inst_id",
        "bk_host_id", "bk_process_id", "bk_cloud_id", "bk_biz_set_id",
    }
    # 缺失时由后端自动派生的必填字段（保持数据完整，避免仅填名称即被拒）
    auto_fill_props = {"bk_asset_id"}

    collection_name = get_inst_collection_name(obj_id)
    collection = get_mongo_collection(collection_name)
    conn = get_db_connection()
    # 提前生成自增 ID，供缺失必填字段派生（如 bk_asset_id）
    next_id = next_sequence(conn, collection_name)

    # 后端必填校验（兜底，前端 v-validate 已拦截；此处防止绕过）：
    # 仅校验 cc_ObjAttDes 中 is_required=true 且非「后端自动生成 ID 字段」的属性。
    att_collection = get_mongo_collection('cc_ObjAttDes')
    required_attrs = list(att_collection.find(
        {"bk_obj_id": obj_id, "is_required": True},
        {"bk_property_id": 1, "bk_property_name": 1},
    ))
    missing = []
    for a in required_attrs:
        pid = a.get("bk_property_id")
        if pid in auto_id_props:
            continue
        # 可自动派生的必填字段：缺失时补默认值，不计入缺失清单
        if pid in auto_fill_props and not req_data.get(pid):
            req_data[pid] = _derive_asset_id(obj_id, next_id)
            continue
        val = req_data.get(pid)
        if val is None or (isinstance(val, str) and val.strip() == ""):
            missing.append(a.get("bk_property_name") or pid)
    if missing:
        raise _InstanceCreateError("以下必填项不能为空: " + "、".join(missing))

    # 获取实例数据，过滤掉 None 值但保留空字符串和 0
    instance_data = {k: v for k, v in req_data.items() if v is not None}

    # 用真实主键字段写入（host->bk_host_id，通用对象->bk_inst_id …）
    instance_data[id_field] = next_id
    # 资产编号（bk_asset_id）为空时派生默认值，保证字段完整（其为非必填可选字段）
    _asset = instance_data.get("bk_asset_id")
    if _asset is None or (isinstance(_asset, str) and _asset.strip() == ""):
        instance_data["bk_asset_id"] = _derive_asset_id(obj_id, next_id)
    instance_data.setdefault("bk_supplier_account", "0")
    instance_data.setdefault("bk_data_status", "active")
    instance_data.setdefault("create_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    instance_data.setdefault("last_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # 唯一约束校验（对齐 Go validator_unique.go）
    try:
        validate_unique_constraint(obj_id, instance_data, collection_name)
    except ModelError as e:
        raise _InstanceCreateError(str(e))

    collection.insert_one(instance_data)
    return next_id


@object_bp.route('/create/instance/object/<obj_id>', methods=['POST'])
def create_instance(obj_id):
    """创建对象实例（单条）。"""
    try:
        req_data = _parse_body()
        cid = _create_one_instance(obj_id, req_data)
        id_field = get_inst_id_field(obj_id)
        return make_response(data={
            "bk_inst_id": cid,
            id_field: cid,
            "id": cid,
        })
    except _InstanceCreateError as e:
        return make_response(result=False, code=500, message=e.message)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/api/v3/batch/create/instance/object/<obj_id>', methods=['POST'])
@object_bp.route('/batch/create/instance/object/<obj_id>', methods=['POST'])
def batch_create_instance(obj_id):
    """批量创建对象实例 —— 主线层级「批量挂载新节点」的后端能力。

    入参: { "instances": [ {bk_inst_name:.., bk_parent_id:.., bk_biz_id:.., ...}, ... ] }
          （也兼容直接传数组 / { "data": [...] }）
    返回: { "info":  [ {index, bk_inst_id, id}, ... ],   # 创建成功的实例
            "error": [ {index, message}, ... ] }          # 失败项（不影响其余项）
    每条实例的 bk_parent_id 决定其在拓扑中的挂接位置（如挂到某业务的 appsys 节点下）。
    """
    try:
        req = _parse_body()
        items = req.get("instances") or req.get("data") or []
        if not isinstance(items, list):
            items = [req]
        created, errors = [], []
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append({"index": idx, "message": "实例数据必须是对象"})
                continue
            try:
                cid = _create_one_instance(obj_id, item)
                created.append({"index": idx, "bk_inst_id": cid, "id": cid})
            except _InstanceCreateError as e:
                errors.append({"index": idx, "message": e.message})
        return make_response(data={"info": created, "error": errors})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


# 更新实例时禁止被用户覆盖的内部字段
_INST_INTERNAL_FIELDS = {
    "bk_inst_id", "bk_supplier_account", "create_time", "last_time", "id", "_id",
}


def _clean_update_fields(info):
    """从用户提交的字段中剔除内部字段，仅保留业务属性。"""
    return {k: v for k, v in (info or {}).items()
            if k not in _INST_INTERNAL_FIELDS and not k.startswith("_")}


@object_bp.route('/update/instance/object/<obj_id>/inst/<int:inst_id>', methods=['PUT'])
def update_instance(obj_id, inst_id):
    """更新单个对象实例（对齐 PUT /update/instance/object/{bk_obj_id}/inst/{inst_id}）。"""
    try:
        req_data = _parse_body()
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        collection = get_mongo_collection(get_inst_collection_name(obj_id))
        id_field = get_inst_id_field(obj_id)
        update_fields = _clean_update_fields(req_data)
        if not update_fields:
            return make_response(result=False, code=500, message="无可更新字段")
        update_fields["last_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 唯一约束校验：更新时检查新值是否与已有实例冲突（排除自身）
        try:
            validate_unique_constraint(obj_id, update_fields, get_inst_collection_name(obj_id), exclude_id=inst_id)
        except ModelError as e:
            return make_response(result=False, code=e.code if hasattr(e, 'code') else 11000,
                                  message=str(e))

        result = collection.update_one({id_field: inst_id}, {"$set": update_fields})
        if result.matched_count == 0:
            return make_response(
                result=False, code=404,
                message="实例不存在: %s=%s" % (id_field, inst_id),
            )
        return make_response(data={})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/delete/instance/object/<obj_id>/inst/<int:inst_id>', methods=['DELETE', 'POST'])
def delete_instance(obj_id, inst_id):
    """删除单个对象实例（对齐 bk-cmdb: DELETE /delete/instance/object/{bk_obj_id}/inst/{inst_id}）。"""
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")
        collection_name = get_inst_collection_name(obj_id)
        collection = get_mongo_collection(collection_name)
        id_field = get_inst_id_field(obj_id)
        result = collection.delete_one({id_field: inst_id})
        if result.deleted_count == 0:
            return make_response(result=False, code=404, message="实例不存在: %s=%s" % (id_field, inst_id))
        return make_response(data={})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/api/v3/delete/instance/object/<obj_id>/inst/<int:inst_id>', methods=['DELETE', 'POST'])
def delete_instance_with_prefix(obj_id, inst_id):
    """带 /api/v3 前缀的删除（兼容前端旧版调用）。"""
    return delete_instance(obj_id, inst_id)


@object_bp.route('/deletemany/instance/object/<obj_id>', methods=['POST', 'DELETE'])
def delete_instances(obj_id):
    """批量删除对象实例（对齐 bk-cmdb: POST /deletemany/instance/object/{bk_obj_id}）。
    
    请求体: {"delete":{"inst_ids":[N,...]}} 或直接 {"inst_ids":[N,...]}
    """
    try:
        req_data = _parse_body()
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")
        collection_name = get_inst_collection_name(obj_id)
        collection = get_mongo_collection(collection_name)
        id_field = get_inst_id_field(obj_id)
        del_ids = req_data.get("inst_ids") or req_data.get("delete", {}).get("inst_ids") or []
        if not del_ids:
            return make_response(result=False, code=500, message="缺少 inst_ids")
        result = collection.delete_many({id_field: {"$in": [int(x) for x in del_ids]}})
        return make_response(data={"deleted_count": result.deleted_count})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


# ---- 主机转移相关 API ----

@object_bp.route('/host/transfer_with_auto_clear_service_instance/bk_biz_id/<int:biz_id>', methods=['POST'])
def transfer_host(biz_id):
    """主机转移（对齐 Go: POST /host/transfer_with_auto_clear_service_instance/bk_biz_id/{id}）。"""
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")
        req_data = request.get_json() or {}
        bk_host_ids = req_data.get("bk_host_ids") or req_data.get("bk_host_id") or []
        default_mod = req_data.get("default_internal_module")
        add_to = req_data.get("add_to_modules") or []
        remove_from = req_data.get("remove_from_modules") or []
        is_remove_all = req_data.get("is_remove_from_all", False)
        
        if isinstance(bk_host_ids, int):
            bk_host_ids = [bk_host_ids]
        if not bk_host_ids:
            return make_response(result=False, code=500, message="缺少 bk_host_ids")
        
        # 目标模块
        target_ids = []
        if default_mod:
            target_ids.append(int(default_mod))
        target_ids.extend([int(x) for x in add_to])
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 对每个主机执行转移
        for hids in [bk_host_ids[i:i+100] for i in range(0, len(bk_host_ids), 100)]:
            for h in hids:
                host_id = int(h)
                # 从源模块移除
                if is_remove_all:
                    # 跨业务转移（如 空闲机池 bk_biz_id=1 → 业务模块 bk_biz_id=3）：
                    # “移除全部”必须删除该主机【所有业务】下、且不在目标模块列表中的当前关系，
                    # 否则空闲机池那条 bk_biz_id=1 的关联不会被删，
                    # 导致主机同时挂在空闲机池与业务模块下（数据不一致）。
                    # 对齐 Go 跨业务转移语义：delHostModuleRelation 删除“非目标的全部模块关系”
                    # （Go: moduleHostConfig 删除 bk_biz_id=URL biz 且 bk_module_id NOT IN 目标模块；
                    #  跨业务场景下源业务即为资源池，这里去掉 biz 限制以覆盖空闲机池关联）。
                    conn.cc_ModuleHostConfig.delete_many({
                        "bk_host_id": host_id,
                        "bk_module_id": {"$nin": target_ids},
                    })
                elif remove_from:
                    conn.cc_ModuleHostConfig.delete_many({
                        "bk_host_id": host_id, "bk_biz_id": biz_id,
                        "bk_module_id": {"$in": [int(x) for x in remove_from]}
                    })
                # 添加到目标模块
                for mod_id in target_ids:
                    # 目标模块可能属于资源池（空闲机/故障机/待回收等内置模块，bk_biz_id=1），
                    # 也可能属于当前业务。必须以模块自身定义（bk_biz_id/bk_set_id）为准，
                    # 不能套用 URL 上的当前业务 biz_id —— 否则会把“资源池的空闲机模块”
                    # 错误地挂到当前业务下（bk_set_id 缺失、bk_biz_id 错配），
                    # 导致集群/拓扑维度计数与“所属拓扑”展示错乱（即未区分 set 分类 default/空闲机池）。
                    # bk_module_id 在全局唯一，按它直接定位模块的真实归属。
                    mod_doc = conn.cc_ModuleBase.find_one(
                        {"bk_module_id": mod_id},
                        {"bk_biz_id": 1, "bk_set_id": 1, "_id": 0})
                    if not mod_doc:
                        continue  # 模块不存在，跳过，避免写入错配关系
                    tgt_biz = mod_doc.get("bk_biz_id")
                    set_id = mod_doc.get("bk_set_id")
                    existing = conn.cc_ModuleHostConfig.find_one({
                        "bk_host_id": host_id, "bk_module_id": mod_id, "bk_biz_id": tgt_biz
                    })
                    if not existing:
                        conn.cc_ModuleHostConfig.insert_one({
                            "bk_host_id": host_id, "bk_module_id": mod_id,
                            "bk_set_id": set_id,
                            "bk_biz_id": tgt_biz, "bk_supplier_account": "0",
                            "create_time": now, "last_time": now
                        })
        
        return make_response(data={"success": True})
    except Exception as e:
        import traceback; traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/host/transfer_with_auto_clear_service_instance/bk_biz_id/<int:biz_id>/preview', methods=['POST'])
def transfer_host_preview(biz_id):
    """主机转移预览 — 返回简化预览数据。"""
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")
        req_data = request.get_json() or {}
        bk_host_ids = req_data.get("bk_host_ids") or req_data.get("bk_host_id") or []
        if isinstance(bk_host_ids, int):
            bk_host_ids = [bk_host_ids]
        bk_host_ids = [int(h) for h in bk_host_ids]

        # 目标模块：default_internal_module（空闲机转移）或 add_to_modules（业务/追加转移）
        default_mod = req_data.get("default_internal_module")
        add_to = req_data.get("add_to_modules") or []
        remove_from = req_data.get("remove_from_modules") or []
        is_remove_all = req_data.get("is_remove_from_all", False)

        target_ids = []
        if default_mod:
            target_ids.append(int(default_mod))
        target_ids.extend([int(x) for x in add_to])

        # 主机的全部当前关系：不按 URL 的 biz_id 过滤，否则跨业务/空闲机池的主机
        # 当前模块会被漏查，导致 to_remove 为空；再叠加 to_add 恒为空，
        # 前端 isSameModule 永远为真 → “目标模块为源模块，无变更信息” 且按钮禁用。
        host_rels = list(conn.cc_ModuleHostConfig.find({"bk_host_id": {"$in": bk_host_ids}}))

        # 模块名映射（当前模块 + 目标模块）
        need_mod_ids = set(r["bk_module_id"] for r in host_rels) | set(target_ids)
        mod_names = {}
        if need_mod_ids:
            for m in conn.cc_ModuleBase.find({"bk_module_id": {"$in": list(need_mod_ids)}}):
                mod_names[m["bk_module_id"]] = m.get("bk_module_name", "")

        hosts = list(conn.cc_HostBase.find({"bk_host_id": {"$in": bk_host_ids}}))
        info = []
        for h in hosts:
            hid = h["bk_host_id"]
            cur = [r for r in host_rels if r["bk_host_id"] == hid]
            cur_mod_ids = set(r["bk_module_id"] for r in cur)

            # 将要添加的模块 = 目标模块中当前未关联的
            to_add = []
            for mid in target_ids:
                if mid not in cur_mod_ids:
                    to_add.append({
                        "bk_module_id": mid,
                        "bk_module_name": mod_names.get(mid, ""),
                        "service_instances": []
                    })

            # 将要移除的模块：is_remove_from_all 移除全部当前；否则按 remove_from_modules
            if is_remove_all:
                rem_ids = set(cur_mod_ids)
            elif remove_from:
                rem_ids = set(int(x) for x in remove_from)
            else:
                rem_ids = set()
            to_remove = [{
                "bk_module_id": r["bk_module_id"],
                "bk_module_name": mod_names.get(r["bk_module_id"], ""),
                "service_instances": []
            } for r in cur if r["bk_module_id"] in rem_ids]

            info.append({
                "bk_host_id": hid,
                "bk_host_innerip": h.get("bk_host_innerip", ""),
                "host_apply_plan": {"conflicts": [], "update_fields": []},
                "to_add_to_modules": to_add,
                "to_remove_from_modules": to_remove,
            })
        return make_response(data=info)
    except Exception as e:
        import traceback; traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/updatemany/instance/object/<obj_id>', methods=['PUT'])
def update_instances(obj_id):
    """批量更新对象实例（对齐 PUT /updatemany/instance/object/{bk_obj_id}）。

    前端请求体: {"update":[{"datas":{字段}, "inst_id":N}], "delete":{"inst_ids":[N,...]}}
    （注意字段名为 datas / inst_ids，与 bk-cmdb v3.10 前端一致）
    """
    try:
        req_data = _parse_body()
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        collection = get_mongo_collection(get_inst_collection_name(obj_id))
        id_field = get_inst_id_field(obj_id)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for item in (req_data.get("update") or []):
            iid = item.get("inst_id")
            if not iid:
                return make_response(result=False, code=500, message="update 项缺少 inst_id")
            update_fields = _clean_update_fields(item.get("datas"))
            if not update_fields:
                continue
            update_fields["last_time"] = now
            collection.update_one({id_field: int(iid)}, {"$set": update_fields})

        # 可选删除分支
        delete = req_data.get("delete") or {}
        del_ids = delete.get("inst_ids") or delete.get("inst_id") or []
        if del_ids:
            collection.delete_many({id_field: {"$in": [int(x) for x in del_ids]}})

        return make_response(data={})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))




@object_bp.route('/find/topoinst/biz/<int:bk_biz_id>', methods=['POST'])
def find_business_topo_inst(bk_biz_id):
    """搜索业务拓扑实例"""
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        # 获取当前用户
        current_username = getattr(g, 'current_user', None)
        
        # 检查用户权限
        accessible_biz_ids = []
        if current_username:
            accessible_biz_ids = get_user_accessible_biz_ids(current_username)
            if bk_biz_id not in accessible_biz_ids:
                return make_response(result=False, code=PERMISSION_DENIED_CODE, message="暂无该业务权限或业务不存在")

        # 查询业务信息
        business = conn.cc_ApplicationBase.find_one({"bk_biz_id": bk_biz_id})
        if not business:
            # 如果没有找到指定业务，返回第一个用户有权限的业务
            if current_username and accessible_biz_ids:
                for biz_id in accessible_biz_ids:
                    business = conn.cc_ApplicationBase.find_one({"bk_biz_id": biz_id})
                    if business:
                        bk_biz_id = biz_id
                        break
        
        if not business:
            return make_response(result=False, code=404, message="业务不存在")

        biz_id = business.get("bk_biz_id")
        biz_name = business.get("bk_biz_name", "")

        # 沿动态主线链 + bk_parent_id 构建业务拓扑实例树（对齐 Go SearchMainlineAssociationInstTopo）。
        # 插入自定义主线层（如 appsys1）后，该层会作为新节点出现在业务拓扑中，
        # 存量 set 实例经 _propagate_mainline_inst 已 reparent 到新层实例下。
        supplier = (request.get_json(silent=True) or {}).get('bk_supplier_account') or '0'
        topo_result = build_mainline_inst_tree(conn, supplier, biz_id, with_idle_pool=True)

        return make_response(data=topo_result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/findmany/resource/directory', methods=['POST'])
def findmany_resource_directory():
    """搜索资源目录"""
    try:
        from app.models.db import get_db_connection
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        req_data = {}
        if request.is_json:
            req_data = request.get_json() or {}
        elif request.form:
            req_data = request.form.to_dict()
        elif request.data:
            try:
                import json
                req_data = json.loads(request.data)
            except:
                req_data = {}

        # 获取资源池相关ID
        # 查找默认业务（资源池业务 bk_default = 1）
        resource_pool_biz = conn.cc_ApplicationBase.find_one({"default": 1})
        if not resource_pool_biz:
            resource_pool_biz = conn.cc_ApplicationBase.find_one({"bk_biz_id": {"$ne": None}})
        
        if not resource_pool_biz:
            return make_response(data={"count": 0, "info": []})
        
        biz_id = resource_pool_biz.get("bk_biz_id")
        
        # 查询主机-模块关系
        host_relations = list(conn.cc_ModuleHostConfig.find({"bk_biz_id": biz_id}))
        
        # 查找资源池集群
        resource_pool_set = conn.cc_SetBase.find_one({"bk_biz_id": biz_id})
        if not resource_pool_set:
            return make_response(data={"count": 0, "info": []})
        
        set_id = resource_pool_set.get("bk_set_id")
        
        # 构建查询条件
        condition = req_data.get("condition", {})
        if not condition:
            condition = {}
        condition["bk_biz_id"] = biz_id
        condition["bk_set_id"] = set_id
        
        # 字段和分页
        fields = req_data.get("fields", [])
        page = req_data.get("page", {})
        sort = page.get("sort", "bk_module_name")
        is_fuzzy = req_data.get("is_fuzzy", False)
        
        # 确保有必要字段
        if "bk_module_id" not in fields:
            fields.append("bk_module_id")
        if "bk_module_name" not in fields:
            fields.append("bk_module_name")
        
        # 构建查询
        query = {}
        for k, v in condition.items():
            if is_fuzzy and isinstance(v, str):
                query[k] = {"$regex": v, "$options": "i"}
            else:
                query[k] = v
        
        # 执行查询
        cursor = conn.cc_ModuleBase.find(query)
        
        # 排序
        if sort:
            sort_dir = 1
            if sort.startswith("-"):
                sort_dir = -1
                sort = sort[1:]
            cursor = cursor.sort(sort, sort_dir)
        
        # 获取数据
        modules = list(cursor)
        count = len(modules)
        
        # 分离空闲机模块和其他模块
        idle_module_id = 0
        module_list = []
        module_map = {}
        
        for m in modules:
            m.pop("_id", None)
            module_id = m.get("bk_module_id")
            module_map[module_id] = m
            
            bk_default = m.get("bk_default", 0)
            if bk_default == 1:
                idle_module_id = module_id
            else:
                module_list.append(module_id)
        
        # 空闲机放在第一位
        if idle_module_id:
            module_list.insert(0, idle_module_id)
        
        # 统计每个模块的主机数量
        result = []
        for module_id in module_list:
            module_info = module_map[module_id]
            # 统计该模块下的主机
            module_hosts = [r for r in host_relations if r.get("bk_module_id") == module_id]
            module_info["host_count"] = len(module_hosts)
            result.append(module_info)
        
        return make_response(data={"count": count, "info": result})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/create/resource/directory', methods=['POST'])
def create_resource_directory():
    """新建资源池自定义目录（对齐 Go: POST /create/resource/directory）。

    前端 2364.*.js 的 createDir 派发 resourceDirectory/createDirectory，
    请求体 params: {bk_module_name: "<目录名>"}，并读取响应 data.created.id。

    Go 实现（topo_server/service/resource_directory.go: CreateResourceDirectory）：
    目录本质是挂在「资源池业务 + 空闲机池集群」下的一个模块实例，
    用 default = DefaultResSelfDefinedModuleFlag(=4) 区别于内置空闲机(1)/故障机(2)/待回收(3)。
    返回 metadata.CreatedOneOptionResult -> data.created.id。
    """
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        # 兼容 json / form / raw data 三种请求体
        req_data = {}
        if request.is_json:
            req_data = request.get_json() or {}
        elif request.form:
            req_data = request.form.to_dict()
        elif request.data:
            try:
                req_data = json.loads(request.data)
            except Exception:
                req_data = {}

        bk_module_name = (req_data.get("bk_module_name") or "").strip()
        if not bk_module_name:
            return make_response(result=False, code=400, message="目录名称不能为空")

        # 资源池业务（bk_default=1），失败回退到任一业务
        resource_pool_biz = conn.cc_ApplicationBase.find_one({"default": 1})
        if not resource_pool_biz:
            resource_pool_biz = conn.cc_ApplicationBase.find_one({"bk_biz_id": {"$ne": None}})
        if not resource_pool_biz:
            return make_response(result=False, code=500, message="未找到资源池业务")
        biz_id = resource_pool_biz.get("bk_biz_id")

        # 资源池集群（空闲机池）：优先取 default=1，回退首个集群
        resource_pool_set = conn.cc_SetBase.find_one({"bk_biz_id": biz_id, "bk_default": 1})
        if not resource_pool_set:
            resource_pool_set = conn.cc_SetBase.find_one({"bk_biz_id": biz_id})
        if not resource_pool_set:
            return make_response(result=False, code=500, message="未找到资源池集群")
        set_id = resource_pool_set.get("bk_set_id")

        # 全局原子自增模块 ID（对齐 Go NextSequence("cc_ModuleBase")）
        new_id = next_sequence(conn, "cc_ModuleBase")

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        module_doc = {
            "bk_module_id": new_id,
            "bk_module_name": bk_module_name,
            "bk_biz_id": biz_id,
            "bk_set_id": set_id,
            "bk_parent_id": set_id,
            "bk_parent_obj": "set",
            # 自定资源目录标志（DefaultResSelfDefinedModuleFlag=4），与内置空闲机/故障机/待回收(1/2/3)区分
            "default": 4,
            "bk_service_category_id": 0,
            "bk_service_template_id": 0,
            "set_template_id": 0,
            "bk_module_type": "1",
            "operator": "",
            "bk_bak_operator": "",
            "bk_supplier_account": "0",
            "bk_data_status": "enabled",
            "create_time": now,
            "last_time": now,
        }
        # 拓扑树实例标识字段（与业务拓扑新建模块一致，便于前端节点渲染）
        module_doc["bk_inst_id"] = new_id
        module_doc["bk_inst_name"] = bk_module_name

        conn.cc_ModuleBase.insert_one(module_doc)
        module_doc.pop("_id", None)

        # 对齐 Go 响应：data.created.id
        return make_response(data={"created": {"id": new_id, "origin_index": 0}})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/update/resource/directory/<int:bk_module_id>', methods=['PUT'])
def update_resource_directory(bk_module_id):
    """重命名资源池自定义目录（对齐 Go: PUT /update/resource/directory/{bk_module_id}）。

    前端 resourceDirectory/updateDirectory 传 params:{bk_module_name}。
    Go 规则：仅允许修改 bk_module_name。
    """
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        req_data = request.get_json() or {}
        new_name = (req_data.get("bk_module_name") or "").strip()
        if not new_name:
            return make_response(result=False, code=400, message="目录名称不能为空")

        mod = conn.cc_ModuleBase.find_one({"bk_module_id": bk_module_id})
        if not mod:
            return make_response(result=False, code=404, message="目录不存在")

        conn.cc_ModuleBase.update_one(
            {"bk_module_id": bk_module_id},
            {"$set": {
                "bk_module_name": new_name,
                "bk_inst_name": new_name,
                "last_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }})
        return make_response(data={"bk_module_id": bk_module_id, "bk_module_name": new_name})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/delete/resource/directory/<int:bk_module_id>', methods=['DELETE'])
def delete_resource_directory(bk_module_id):
    """删除资源池自定义目录（对齐 Go: DELETE /delete/resource/directory/{bk_module_id}）。

    前端 resourceDirectory/deleteDirectory。Go 规则：
    - 目录含主机时拒绝；
    - 内置空闲机/故障机/待回收（default=1/2/3）不可删，自定目录 default=4 可删。
    """
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        mod = conn.cc_ModuleBase.find_one({"bk_module_id": bk_module_id})
        if not mod:
            return make_response(result=False, code=404, message="目录不存在")

        # 内置目录（空闲机/故障机/待回收）不可删
        if mod.get("default") in (1, 2, 3):
            return make_response(result=False, code=400, message="内置目录不可删除")

        # 含主机不可删（前端已拦截 host_count>0，此处为后端兜底）
        rel = conn.cc_ModuleHostConfig.find_one({"bk_module_id": bk_module_id})
        if rel:
            return make_response(result=False, code=400, message="目标包含主机, 不允许删除")

        conn.cc_ModuleBase.delete_one({"bk_module_id": bk_module_id})
        return make_response(data={"bk_module_id": bk_module_id, "deleted": True})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/host/transfer/resource/directory', methods=['POST'])
def transfer_resource_directory():
    """把未分配主机移入资源池目录（对齐 Go: POST /host/transfer/resource/directory）。

    前端 resourceDirectory/changeHostsDirectory 传 params:{bk_host_id:[...], bk_module_id:<目标目录模块id>}。
    Go 语义：仅把「资源池业务」下这些主机的 cc_ModuleHostConfig.bk_module_id 改为目标目录模块
    （目标目录须为 default=1 空闲机 或 default=4 自定目录）。

    严格约束（区分 业务空闲机池 与 非业务/资源池）：
    1. 资源池业务以 default=1 标识（本仓库字段为 default，非 bk_default）；
    2. 目标模块必须【归属资源池】(bk_biz_id==资源池) 且 default∈{1,4}，否则拒绝——
       杜绝把资源池主机指到某业务的模块，造成「主机关系 bk_biz_id 与模块归属业务不一致」的脏数据
       （即所谓“在业务中错误地存在了空闲机”）；
    3. 写入时 bk_biz_id/bk_set_id 跟随目标模块，保证资源池关系始终归属资源池。
    """
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        req = request.get_json() or {}
        host_ids = req.get("bk_host_id") or req.get("host_id") or []
        module_id = int(req.get("bk_module_id") or req.get("module_id") or 0)
        if not host_ids:
            return make_response(result=False, code=400, message="缺少 bk_host_id")
        if not module_id:
            return make_response(result=False, code=400, message="缺少 bk_module_id")
        host_ids = [int(h) for h in host_ids]

        # 资源池业务（本仓库字段为 default，default=1 即资源池）
        rp = conn.cc_ApplicationBase.find_one({"default": 1}) or \
            conn.cc_ApplicationBase.find_one({"bk_biz_id": {"$ne": None}})
        if not rp:
            return make_response(result=False, code=500, message="未找到资源池业务")
        pool_biz = int(rp.get("bk_biz_id"))

        # 目标模块必须【归属资源池】且为 default=1(空闲机) 或 default=4(自定目录)
        mod = conn.cc_ModuleBase.find_one({"bk_module_id": module_id})
        if not mod or mod.get("bk_biz_id") != pool_biz or mod.get("default") not in (1, 4):
            return make_response(result=False, code=400,
                                 message="目标目录不存在、非资源池目录或不属于资源池业务")
        target_set_id = mod.get("bk_set_id")

        # 仅更新【资源池业务】下这些主机的模块归属（bk_biz_id 锁定为资源池，杜绝跨业务指模）
        res = conn.cc_ModuleHostConfig.update_many(
            {"bk_host_id": {"$in": host_ids}, "bk_biz_id": pool_biz},
            {"$set": {"bk_module_id": module_id, "bk_set_id": target_set_id,
                      "bk_biz_id": pool_biz}})
        return make_response(data={"bk_module_id": module_id, "updated": res.modified_count})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/hosts/modules/resource', methods=['POST'])
def move_host_to_resource_pool():
    """确认归还主机池（对齐 Go: POST /hosts/modules/resource -> MoveHostToResourcePool）。

    前端「确认归还主机池」弹窗（5603.*.js 的 cmdb-move-to-resource-confirm）收集目标
    资源池目录后，派发 hostRelation/transferHostToResourceModule，请求体：
        {bk_biz_id: <源业务ID>, bk_host_id: [...], bk_module_id: <目标资源池模块ID，可空>}

    来自资源-主机-未分配 / 业务拓扑的「归还主机池」操作：把【源业务】下的主机跨业务
    转移到【资源池业务】，目标模块为指定资源池目录，缺省为资源池空闲机模块(default=1)。

    Go 语义（host_server/logics/module.go: MoveHostToResourcePool，行 193）：
      1. ownerAppID = 资源池业务（GetDefaultAppID）；拒绝 source==0 或 source==ownerAppID。
      2. 目标模块：bk_module_id 指定则用该资源池模块；否则用资源池空闲机模块(default=1)。
      3. 跨业务转移 TransferToAnotherBusiness：删除源业务下这些主机的全部模块关系，
         再在资源池业务下写入目标模块关系（含空闲机池 set）。
    """
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        req = request.get_json() or {}
        src_biz = int(req.get("bk_biz_id") or 0)
        # 前端用 bk_host_id（数组）；兼容 bk_host_ids / host_id 写法
        host_ids = req.get("bk_host_id") or req.get("bk_host_ids") or req.get("host_id") or []
        target_mod = int(req.get("bk_module_id") or 0)

        if isinstance(host_ids, int):
            host_ids = [host_ids]
        host_ids = [int(h) for h in host_ids]

        if not src_biz:
            return make_response(result=False, code=400, message="缺少 bk_biz_id（源业务）")
        if not host_ids:
            return make_response(result=False, code=400, message="缺少 bk_host_id")

        # 资源池业务：本仓库数据约定用 default 字段（非 bk_default），default=1 即资源池
        rp = conn.cc_ApplicationBase.find_one({"default": 1}) or \
            conn.cc_ApplicationBase.find_one({"bk_biz_id": {"$ne": None}})
        if not rp:
            return make_response(result=False, code=500, message="未找到资源池业务")
        owner_app = int(rp.get("bk_biz_id"))

        # 不能把资源池自己的主机再「归还」给资源池（对齐 Go CCErrHostBelongResourceFail）
        if src_biz == owner_app:
            return make_response(result=False, code=400, message="主机已属于资源池，无法再次归还")

        # 解析目标资源池模块
        if target_mod:
            mod = conn.cc_ModuleBase.find_one({"bk_module_id": target_mod, "bk_biz_id": owner_app})
            if not mod:
                return make_response(result=False, code=400,
                                     message="目标资源池目录不存在或不属于资源池业务")
        else:
            # 缺省：资源池空闲机模块（default=1，bk_module_id=1）
            mod = conn.cc_ModuleBase.find_one({"bk_biz_id": owner_app, "default": 1})
            if not mod:
                return make_response(result=False, code=500, message="未找到资源池空闲机模块")

        target_module_id = int(mod.get("bk_module_id"))
        target_set_id = mod.get("bk_set_id")

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 跨业务转移：删源业务关系 + 写资源池关系
        moved = 0
        for hid in host_ids:
            hid = int(hid)
            # 删除该主机在【源业务】下的全部模块关系（跨业务转移语义，对齐 delHostModuleRelation）
            del_res = conn.cc_ModuleHostConfig.delete_many({
                "bk_host_id": hid, "bk_biz_id": src_biz
            })
            # 资源池侧幂等写入：已存在则更新模块/set，不存在则插入
            upsert_res = conn.cc_ModuleHostConfig.update_one(
                {"bk_host_id": hid, "bk_module_id": target_module_id, "bk_biz_id": owner_app},
                {"$set": {
                    "bk_set_id": target_set_id,
                    "bk_biz_id": owner_app,
                    "bk_module_id": target_module_id,
                    "bk_supplier_account": "0",
                    "last_time": now
                }},
                upsert=True
            )
            if del_res.deleted_count > 0 or (upsert_res.upserted_id is not None):
                moved += 1

        return make_response(data={"bk_module_id": target_module_id, "moved": moved})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


def _ensure_idle_module(conn, biz_id):
    """确保业务存在空闲机模块(default=1)；缺失则按 bk-cmdb 约定自动创建。

    bk-cmdb 中每个业务创建时都会生成 空闲机/故障机/待回收 三个内置模块，
    本仓库 create_business 未生成，故在此按需补齐（挂在业务首个 set 下，无 set 则 set_id=0），
    以保证「分配到业务空闲机池」对任一业务都可用。返回 (bk_module_id, bk_set_id)。
    """
    mod = conn.cc_ModuleBase.find_one({"bk_biz_id": biz_id, "default": 1})
    if mod:
        return int(mod.get("bk_module_id")), mod.get("bk_set_id")
    s = conn.cc_SetBase.find_one({"bk_biz_id": biz_id}) or {}
    set_id = s.get("bk_set_id", 0)
    new_id = next_sequence(conn, "cc_ModuleBase")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.cc_ModuleBase.insert_one({
        "bk_module_id": new_id,
        "bk_module_name": "空闲机",
        "bk_biz_id": biz_id,
        "bk_set_id": set_id,
        "bk_parent_id": set_id,
        "bk_parent_obj": "set" if set_id else None,
        "default": 1,
        "bk_service_category_id": 0,
        "bk_service_template_id": 0,
        "set_template_id": 0,
        "bk_module_type": "1",
        "operator": "",
        "bk_bak_operator": "",
        "bk_supplier_account": "0",
        "bk_data_status": "enabled",
        "create_time": now,
        "last_time": now,
    })
    return new_id, set_id


@object_bp.route('/hosts/modules/idle', methods=['POST'])
def move_host_to_idle_module():
    """分配到业务空闲机池（对齐 Go: POST /hosts/modules/idle -> MoveHost2IdleModule）。

    同业务内转移：把 bk_biz_id 业务下的主机，移动到【该业务】的空闲机模块(default=1)。
    前端 hostRelation/transferHostToIdleModule，请求体 {bk_biz_id, bk_host_id:[...]}。
    Go: moveHostToDefaultModule(DefaultResModuleFlag) -> TransferToInnerModule（删除业务内
    全部模块关系，再写入空闲机模块）。
    """
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        req = request.get_json() or {}
        biz_id = int(req.get("bk_biz_id") or 0)
        host_ids = req.get("bk_host_id") or req.get("bk_host_ids") or req.get("host_id") or []
        if isinstance(host_ids, int):
            host_ids = [host_ids]
        host_ids = [int(h) for h in host_ids]

        if not biz_id:
            return make_response(result=False, code=400, message="缺少 bk_biz_id（目标业务）")
        if not host_ids:
            return make_response(result=False, code=400, message="缺少 bk_host_id")

        # 目标：该业务的空闲机模块（default=1，缺失则自动创建）
        target_module_id, target_set_id = _ensure_idle_module(conn, biz_id)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        moved = 0
        for hid in host_ids:
            hid = int(hid)
            # 同业务内转移：删除该主机在该业务下的全部模块关系，再写入空闲机模块
            del_res = conn.cc_ModuleHostConfig.delete_many({"bk_host_id": hid, "bk_biz_id": biz_id})
            upsert_res = conn.cc_ModuleHostConfig.update_one(
                {"bk_host_id": hid, "bk_module_id": target_module_id, "bk_biz_id": biz_id},
                {"$set": {"bk_set_id": target_set_id, "bk_biz_id": biz_id,
                          "bk_module_id": target_module_id, "bk_supplier_account": "0",
                          "last_time": now}},
                upsert=True)
            if del_res.deleted_count > 0 or upsert_res.upserted_id is not None:
                moved += 1

        return make_response(data={"bk_module_id": target_module_id, "moved": moved})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/hosts/modules/resource/idle', methods=['POST'])
def assign_host_to_app():
    """从资源池分配到业务空闲机池（对齐 Go: POST /hosts/modules/resource/idle -> AssignHostToApp）。

    跨业务转移：把【资源池】下的主机，分配到 bk_biz_id 业务的空闲机模块(default=1)。
    前端 hostRelation/assignHostsToBusiness，请求体 {bk_biz_id, bk_host_id:[...]}。
    Go: 源=资源池(ownerAppID)，目标=bk_biz_id 业务空闲机模块，TransferToAnotherBusiness。
    """
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        req = request.get_json() or {}
        dst_biz = int(req.get("bk_biz_id") or 0)
        host_ids = req.get("bk_host_id") or req.get("bk_host_ids") or req.get("host_id") or []
        if isinstance(host_ids, int):
            host_ids = [host_ids]
        host_ids = [int(h) for h in host_ids]

        if not dst_biz:
            return make_response(result=False, code=400, message="缺少 bk_biz_id（目标业务）")
        if not host_ids:
            return make_response(result=False, code=400, message="缺少 bk_host_id")

        # 资源池业务（default=1）
        rp = conn.cc_ApplicationBase.find_one({"default": 1}) or \
            conn.cc_ApplicationBase.find_one({"bk_biz_id": {"$ne": None}})
        if not rp:
            return make_response(result=False, code=500, message="未找到资源池业务")
        owner_app = int(rp.get("bk_biz_id"))

        # 目标业务即资源池：无需转移（Go 直接返回 nil）
        if dst_biz == owner_app:
            return make_response(data={"bk_module_id": 0, "moved": 0})

        # 目标：bk_biz_id 业务的空闲机模块（default=1，缺失则自动创建）
        target_module_id, target_set_id = _ensure_idle_module(conn, dst_biz)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        moved = 0
        for hid in host_ids:
            hid = int(hid)
            # 跨业务：删除资源池侧关系，写入目标业务空闲机模块
            del_res = conn.cc_ModuleHostConfig.delete_many({"bk_host_id": hid, "bk_biz_id": owner_app})
            upsert_res = conn.cc_ModuleHostConfig.update_one(
                {"bk_host_id": hid, "bk_module_id": target_module_id, "bk_biz_id": dst_biz},
                {"$set": {"bk_set_id": target_set_id, "bk_biz_id": dst_biz,
                          "bk_module_id": target_module_id, "bk_supplier_account": "0",
                          "last_time": now}},
                upsert=True)
            if del_res.deleted_count > 0 or upsert_res.upserted_id is not None:
                moved += 1

        return make_response(data={"bk_module_id": target_module_id, "moved": moved})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/find/module/host/relation/<int:bk_biz_id>', methods=['POST'])
def find_module_host_relation(bk_biz_id):
    """根据模块ID查找主机关联关系"""
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        # 获取请求数据
        req_data = {}
        if request.is_json:
            req_data = request.get_json() or {}
        elif request.form:
            req_data = request.form.to_dict()
        elif request.data:
            try:
                import json
                req_data = json.loads(request.data)
            except:
                req_data = {}

        module_ids = req_data.get("bk_module_ids", [])
        host_fields = req_data.get("host_fields", [])
        module_fields = req_data.get("module_fields", [])
        page = req_data.get("page", {})

        start = page.get("start", 0)
        limit = page.get("limit", 20)
        sort = page.get("sort", "bk_host_id")

        # 查询主机-模块关系
        if module_ids:
            host_relations = list(conn.cc_ModuleHostConfig.find({
                "bk_biz_id": bk_biz_id,
                "bk_module_id": {"$in": module_ids}
            }))
        else:
            host_relations = list(conn.cc_ModuleHostConfig.find({
                "bk_biz_id": bk_biz_id
            }))

        # 获取主机ID列表
        host_ids = [rel.get("bk_host_id") for rel in host_relations]

        if not host_ids:
            return make_response(data={
                "count": 0,
                "relation": []
            })

        # 查询主机信息
        query = {"bk_host_id": {"$in": host_ids}}
        cursor = conn.cc_HostBase.find(query)

        # 排序
        if sort:
            sort_dir = 1
            if sort.startswith("-"):
                sort_dir = -1
                sort = sort[1:]
            cursor = cursor.sort(sort, sort_dir)

        # 总数
        total_count = conn.cc_HostBase.count_documents(query)

        # 分页
        cursor = cursor.skip(start).limit(limit)

        # 获取主机
        hosts = []
        for doc in cursor:
            doc.pop("_id", None)
            if host_fields:
                filtered_host = {}
                for field in host_fields:
                    if field in doc:
                        filtered_host[field] = doc[field]
                hosts.append(filtered_host)
            else:
                hosts.append(doc)

        if not hosts:
            return make_response(data={
                "count": total_count,
                "relation": []
            })

        # 构建主机关联关系
        host_id_list = [host.get("bk_host_id") for host in hosts]

        # 查询这些主机的模块关系
        host_module_map = {}
        module_id_set = set()
        for rel in host_relations:
            host_id = rel.get("bk_host_id")
            if host_id in host_id_list:
                if host_id not in host_module_map:
                    host_module_map[host_id] = []
                module_id = rel.get("bk_module_id")
                host_module_map[host_id].append(module_id)
                module_id_set.add(module_id)

        # 查询模块信息
        modules = []
        if module_id_set:
            module_query = {"bk_module_id": {"$in": list(module_id_set)}}
            module_cursor = conn.cc_ModuleBase.find(module_query)
            for doc in module_cursor:
                doc.pop("_id", None)
                if module_fields:
                    filtered_module = {}
                    for field in module_fields:
                        if field in doc:
                            filtered_module[field] = doc[field]
                    modules.append(filtered_module)
                else:
                    modules.append(doc)

        # 构建模块映射
        module_map = {}
        for module in modules:
            module_id = module.get("bk_module_id")
            module_map[module_id] = module

        # 组装结果
        relation = []
        for host in hosts:
            host_id = host.get("bk_host_id")
            module_ids_for_host = host_module_map.get(host_id, [])
            host_modules = []
            for module_id in module_ids_for_host:
                if module_id in module_map:
                    host_modules.append(module_map[module_id])
            relation.append({
                "host": host,
                "modules": host_modules
            })

        return make_response(data={
            "count": total_count,
            "relation": relation
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/usercustom/user/search', methods=['POST'])
def usercustom_user_search():
    """用户自定义搜索用户"""
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")
        
        # 获取请求数据
        req_data = {}
        if request.is_json:
            req_data = request.get_json() or {}
        elif request.form:
            req_data = request.form.to_dict()
        elif request.data:
            try:
                import json
                req_data = json.loads(request.data)
            except:
                req_data = {}
        
        # 查询用户
        users = list(conn.users.find({}, {'_id': 0}))
        
        return make_response(data={"count": len(users), "info": users})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/usercustom/default/model', methods=['POST'])
def usercustom_default_model():
    """用户自定义默认模型"""
    try:
        return make_response(data={})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/find/topoinst/biz_set/<int:biz_set_id>', methods=['POST'])
def find_biz_set_topo_inst(biz_set_id):
    """获取业务集拓扑实例"""
    try:
        return make_response(data=[])
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))
