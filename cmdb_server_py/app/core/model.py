"""模型管理核心业务层（对齐 bk-cmdb Go 端 ``source_controller/coreservice/core/model``）。

本模块是模型元数据 CRUD 的**真实落库逻辑**，被 ``app.routes.model_routes``（门面层）调用。
按 Go 的 ``coreservice/core/model`` 文件职责拆区块：Model / Attribute / Classification /
Association / AssociationType / Unique / PropertyGroup，外加 Topology / Statistics。

约定：
- 所有元数据集合的文档都带 ``id`` 字段（由 ``cc_idgenerator`` 原子自增，经 ``next_sequence`` 生成）。
- ``bk_supplier_account`` 默认 ``"0"``（对齐 id0 租户隔离）。
- 创建写 ``id`` / ``bk_supplier_account`` / ``creator`` / ``create_time`` / ``last_time``；
  更新写 ``last_time`` 并对入参字段做 ``$set``（剔除内部字段）。
- ``find/*`` 返回 ``(count, info)``；列表类（objectunique / objectattgroup）返回数组。
"""

from datetime import datetime

from app.models.db import get_db_connection, get_mongo_collection, next_sequence
from app.models.tablenames import (
    BK_TABLE_NAME_OBJ_DES,
    BK_TABLE_NAME_OBJ_ATT_DES,
    BK_TABLE_NAME_OBJ_CLASSIFICATION,
    BK_TABLE_NAME_OBJ_ASST,
    BK_TABLE_NAME_OBJ_UNIQUE,
    BK_TABLE_NAME_PROPERTY_GROUP,
    BK_TABLE_NAME_ASST_DES,
)

DEFAULT_SUPPLIER = "0"
INTERNAL_FIELDS = {"_id", "id", "bk_supplier_account", "create_time", "creator", "ispre"}

# bk-cmdb 内置（预定义）模型：其属性 ispre=True 是合法的。
# 自定义/网络模型（bk_switch、bk_router 等）的属性不应为 ispre，否则前端会禁用
# 「必填」复选框并丢弃 isrequired（getPreFieldUpdateParams 仅放行 option/unit/placeholder），
# 导致「修改模型属性必填/非必填提交不生效」。
BUILTIN_MODEL_IDS = {
    "biz", "set", "module", "host", "process", "plat",
    "cloud_area", "bk_biz_set_obj",
}


class ModelError(Exception):
    """业务逻辑错误，由路由层捕获并转为 make_response(result=False, code=..., message=...)。"""

    def __init__(self, message, code=400):
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------- #
# 通用工具
# --------------------------------------------------------------------------- #
def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _coll(name):
    return get_mongo_collection(name)


def _new_id(conn, name):
    """对齐 Go NextSequence：模型集合直接用集合名作为序列名（重定向仅作用于分片实例表）。"""
    return next_sequence(conn, name)


def _strip(doc):
    if doc is None:
        return None
    doc.pop("_id", None)
    return doc


def _build_query(params, *fields):
    """从 params 中提取已知字段拼查询条件；bk_supplier_account 缺省取 '0'。"""
    query = {}
    if params:
        for f in fields:
            if params.get(f) not in (None, ""):
                query[f] = params[f]
    if "bk_supplier_account" not in query:
        query["bk_supplier_account"] = DEFAULT_SUPPLIER
    return query


def _list(coll_name, query, limit=2000):
    coll = _coll(coll_name)
    count = coll.count_documents(query)
    docs = [ _strip(d) for d in coll.find(query).limit(limit) ]
    return count, docs


def _find_by_id(coll_name, rid):
    try:
        rid_int = int(rid)
    except (TypeError, ValueError):
        rid_int = rid
    doc = _coll(coll_name).find_one({"id": rid_int})
    return _strip(doc)


def _update_by_id(coll_name, rid, fields):
    try:
        rid_int = int(rid)
    except (TypeError, ValueError):
        rid_int = rid
    clean = {k: v for k, v in (fields or {}).items() if k not in INTERNAL_FIELDS and not k.startswith("_")}
    if not clean:
        raise ModelError("无可更新字段", code=400)
    clean["last_time"] = _now()
    result = _coll(coll_name).update_one({"id": rid_int}, {"$set": clean})
    if result.matched_count == 0:
        raise ModelError("记录不存在: id=%s" % rid, code=404)
    return _strip(_coll(coll_name).find_one({"id": rid_int}))


def _delete_by_id(coll_name, rid):
    try:
        rid_int = int(rid)
    except (TypeError, ValueError):
        rid_int = rid
    result = _coll(coll_name).delete_one({"id": rid_int})
    if result.deleted_count == 0:
        raise ModelError("记录不存在: id=%s" % rid, code=404)
    return result.deleted_count


# --------------------------------------------------------------------------- #
# Model（cc_ObjDes）
# --------------------------------------------------------------------------- #
def create_model(params):
    conn = get_db_connection()
    if conn is None:
        raise ModelError("数据库连接失败", code=500)
    bk_obj_id = (params or {}).get("bk_obj_id")
    if not bk_obj_id:
        raise ModelError("bk_obj_id 不能为空", code=400)
    supplier = (params or {}).get("bk_supplier_account") or DEFAULT_SUPPLIER
    exist = _coll(BK_TABLE_NAME_OBJ_DES).find_one({"bk_obj_id": bk_obj_id, "bk_supplier_account": supplier})
    if exist:
        raise ModelError("模型已存在: bk_obj_id=%s" % bk_obj_id, code=400)
    doc = dict(params)
    doc["id"] = _new_id(conn, BK_TABLE_NAME_OBJ_DES)
    doc["bk_supplier_account"] = supplier
    doc["creator"] = (params or {}).get("creator") or "admin"
    doc["create_time"] = _now()
    doc["last_time"] = _now()
    doc.setdefault("bk_ishidden", False)
    doc.setdefault("bk_ispaused", False)
    doc.setdefault("ispre", False)
    _coll(BK_TABLE_NAME_OBJ_DES).insert_one(doc)
    # 对齐 Go createDefaultAttrs：建模型同时注入「实例名」等内置默认属性，
    # 否则前端实例表单缺少「实例名称」字段、无法新增实例（见 ensure_model_default_attributes）。
    ensure_model_default_attributes(bk_obj_id, supplier, is_mainline=False)
    return _strip(doc)


def ensure_model_default_attributes(bk_obj_id, supplier=DEFAULT_SUPPLIER, is_mainline=False):
    """对齐 Go ``createDefaultAttrs``：建模型时自动注入内置默认属性（幂等 + 自愈纠正）。

    Go 在 ``CreateObject`` / ``CreateMainlineAssociation`` 时**必为每模型注入**：
      - ``bk_inst_name``（实例名，ispre/isonly/is_required=true，singlechar）：
        即 ``GetInstNameField(objID)``，自定义模型恒为 ``bk_inst_name``；
      - ``bk_parent_id``（仅主线模型，ispre/isonly/is_required=true，int）。

    本函数具备 **「确保」语义**：
      - 属性不存在 → 插入（注入）；
      - 属性已存在但标志位被 ``normalize_custom_model_ispre`` 或人工误改 → 纠正为期望值
        （保证 ``bk_inst_name`` 始终 ``ispre/isrequired/isonly=True``，匹配 Go 语义，
        前端才会把它当受保护的实例名属性，而非「未初始化」的可删普通字段）。

    返回本次新增/纠正的属性条数（用于启动日志统计）。
    """
    conn = get_db_connection()
    if conn is None:
        return 0
    att_coll = _coll(BK_TABLE_NAME_OBJ_ATT_DES)
    changed = 0

    def _ensure(pid, pname, ptype, isrequired, isonly, ispre, issystem):
        nonlocal changed
        existing = att_coll.find_one({"bk_obj_id": bk_obj_id, "bk_supplier_account": supplier,
                                      "bk_property_id": pid})
        desired = {
            "bk_property_name": pname,
            "bk_property_type": ptype,
            "bk_property_group": "default",
            "creator": "system",
            "isrequired": isrequired,
            "isonly": isonly,
            "ispre": ispre,
            "editable": True,
            "isreadonly": False,
            "bk_isapi": False,
            "bk_issystem": issystem,
        }
        if existing is None:
            doc = {
                "id": _new_id(conn, BK_TABLE_NAME_OBJ_ATT_DES),
                "bk_obj_id": bk_obj_id,
                "bk_supplier_account": supplier,
                "bk_biz_id": 0,
                "bk_property_id": pid,
                "bk_property_index": -1,
                "create_time": _now(),
                "last_time": _now(),
            }
            doc.update(desired)
            att_coll.insert_one(doc)
            changed += 1
        else:
            # 纠正已存在但被误改的标志位（防止 normalize_custom_model_ispre 误伤）
            fix = {k: v for k, v in desired.items() if existing.get(k) != v}
            if fix:
                att_coll.update_one({"_id": existing["_id"]}, {"$set": fix})
                changed += 1

    # 实例名：所有模型必注入（自定义模型 GetInstNameField 返回 bk_inst_name）
    _ensure("bk_inst_name", "实例名", "singlechar", True, True, True, False)
    # 主线模型注入 bk_parent_id 只对内建模型（biz/set/module）有效：内建模型由 Go 的
    # createDefaultAttrs 注入（IsSystem=true），但本条 ensure_model_default_attributes
    # 仅对自定义模型生效（caller 已过滤 BUILTIN_MODEL_IDS），故不再重复注入 bk_parent_id。
    # 自定义主线模型不应有 bk_parent_id 作为用户可见属性列（由属性列表端点的 bk_parent_id
    # 过滤逻辑保障，见 object_routes.py _query_object_attr_by_obj_ids）。

    # 确保「default」属性分组存在（否则 bk_inst_name 的 bk_property_group="default"
    # 指向不存在的分组，前端按分组渲染字段时将跳过该属性，模型详情页无任何字段可显示）。
    group_coll = _coll(BK_TABLE_NAME_PROPERTY_GROUP)
    if not group_coll.find_one({"bk_obj_id": bk_obj_id, "bk_supplier_account": supplier, "bk_group_id": "default"}):
        group_coll.insert_one({
            "id": _new_id(conn, BK_TABLE_NAME_PROPERTY_GROUP),
            "bk_obj_id": bk_obj_id,
            "bk_supplier_account": supplier,
            "bk_biz_id": 0,
            "bk_group_id": "default",
            "bk_group_name": "基础信息",
            "bk_group_index": 1,
            "bk_isdefault": True,
            "ispre": False,
            "is_collapse": False,
            "create_time": _now(),
            "last_time": _now(),
        })
        changed += 1

    return changed


def ensure_all_models_default_attributes():
    """启动自愈：为所有「非内置」模型补齐/纠正默认属性（bk_inst_name / 主线 bk_parent_id）。

    Python 旧版本建模型未注入默认属性，导致存量自定义/主线模型缺 bk_inst_name，
    实例表单无名称字段、无法新增实例；或 ``normalize_custom_model_ispre`` 误把
    bk_inst_name 的 ispre 清零。本函数对每个模型调用 ``ensure_model_default_attributes``
    （具备「确保」语义：缺失则注入、存在但标志位错误则纠正），返回发生变更的模型数。
    """
    conn = get_db_connection()
    if conn is None:
        return 0
    obj_coll = _coll(BK_TABLE_NAME_OBJ_DES)
    asst_coll = _coll(BK_TABLE_NAME_OBJ_ASST)
    fixed = 0
    for obj in obj_coll.find({"bk_obj_id": {"$nin": list(BUILTIN_MODEL_IDS)}}):
        oid = obj.get("bk_obj_id")
        supplier = obj.get("bk_supplier_account") or DEFAULT_SUPPLIER
        # 是否主线：存在 bk_mainline 关联即为主线模型
        is_mainline = asst_coll.find_one(
            {"bk_obj_id": oid, "bk_supplier_account": supplier, "bk_asst_id": "bk_mainline"}) is not None
        if ensure_model_default_attributes(oid, supplier, is_mainline) > 0:
            fixed += 1
    return fixed


def update_model(rid, params):
    """更新模型 — 禁止停用/删除内置模型。"""
    doc = _find_by_id(BK_TABLE_NAME_OBJ_DES, rid)
    if doc is None:
        raise ModelError("模型不存在: id=%s" % rid, code=404)
    obj_id = doc.get("bk_obj_id")
    # 禁止通过 update 停用内置模型
    if obj_id in BUILTIN_MODEL_IDS and params.get("bk_ispaused") is True:
        raise ModelError("内置模型不允许停用: %s" % obj_id, code=400)
    return _update_by_id(BK_TABLE_NAME_OBJ_DES, rid, params)


def delete_model(rid):
    doc = _find_by_id(BK_TABLE_NAME_OBJ_DES, rid)
    if doc is None:
        raise ModelError("模型不存在: id=%s" % rid, code=404)
    obj_id = doc.get("bk_obj_id")
    supplier = doc.get("bk_supplier_account", DEFAULT_SUPPLIER)
    # 元数据级联清理（属性/关联/唯一规则/属性分组），不动实例分片表（避免误删业务数据）
    _coll(BK_TABLE_NAME_OBJ_ATT_DES).delete_many({"bk_obj_id": obj_id, "bk_supplier_account": supplier})
    _coll(BK_TABLE_NAME_OBJ_ASST).delete_many({"bk_obj_id": obj_id, "bk_supplier_account": supplier})
    _coll(BK_TABLE_NAME_OBJ_UNIQUE).delete_many({"bk_obj_id": obj_id, "bk_supplier_account": supplier})
    _coll(BK_TABLE_NAME_PROPERTY_GROUP).delete_many({"bk_obj_id": obj_id, "bk_supplier_account": supplier})
    _delete_by_id(BK_TABLE_NAME_OBJ_DES, rid)
    return 1


# --------------------------------------------------------------------------- #
# Mainline（拓扑主线节点删除）
# --------------------------------------------------------------------------- #
def get_mainline_neighbors(bk_obj_id):
    """读取并校验主线节点的上下游（不修改数据）。

    对齐 Go ``DeleteMainlineAssociation`` 的守门与上下游推导：
      - 内置主线模型（biz/set/module/host/...）禁止删除；
      - 模型必须存在；
      - 必须存在 ``bk_asst_id=bk_mainline`` 且（``bk_obj_id==target`` 或
        ``bk_asst_obj_id==target``）的关联；
      - 预定义(ispre)主线关联禁止删除；
      - 需同时推导出 childObjID（target 作为父时的子级）与 parentObjID（target 作为子时的父级）。

    返回 ``{"child_obj_id", "parent_obj_id", "obj_id"}``；任一守门不通过抛 ``ModelError``。
    """
    supplier = DEFAULT_SUPPLIER
    if bk_obj_id in BUILTIN_MODEL_IDS:
        raise ModelError("内置主线模型不允许删除: %s" % bk_obj_id, code=400)
    obj_doc = _coll(BK_TABLE_NAME_OBJ_DES).find_one(
        {"bk_obj_id": bk_obj_id, "bk_supplier_account": supplier})
    if obj_doc is None:
        raise ModelError("模型不存在: bk_obj_id=%s" % bk_obj_id, code=404)
    asst_coll = _coll(BK_TABLE_NAME_OBJ_ASST)
    matched = list(asst_coll.find({
        "bk_asst_id": "bk_mainline",
        "bk_supplier_account": supplier,
        "$or": [{"bk_obj_id": bk_obj_id}, {"bk_asst_obj_id": bk_obj_id}],
    }))
    if not matched:
        raise ModelError("模型 %s 不是主线模型，无主线关联可删除" % bk_obj_id, code=400)
    child_obj_id = None
    parent_obj_id = None
    for a in matched:
        if a.get("ispre"):
            raise ModelError("预定义主线关联禁止删除: %s" % a.get("bk_obj_asst_id"), code=400)
        if a.get("bk_asst_obj_id") == bk_obj_id:
            child_obj_id = a.get("bk_obj_id")          # target 作为父级 -> 子级
        if a.get("bk_obj_id") == bk_obj_id:
            parent_obj_id = a.get("bk_asst_obj_id")    # target 作为子级 -> 父级
    if not child_obj_id or not parent_obj_id:
        raise ModelError("主线模型 %s 缺少父级或子级，无法安全删除" % bk_obj_id, code=400)
    return {"child_obj_id": child_obj_id, "parent_obj_id": parent_obj_id, "obj_id": obj_doc.get("id")}


def delete_mainline_object(bk_obj_id):
    """删除一个主线模型节点：重链上下游 + 删除其主线关联与模型元数据。

    对齐 Go ``DeleteMainlineAssociation``（不含实例级处理，实例重挂/删除由路由层
    ``_reset_mainline_inst`` 在调用本函数前完成，顺序与 Go 一致）。

    流程：
      1) 重链 child -> parent（如 ``set_bk_mainline_biz``），已存在则跳过；
      2) 删除所有命中（target 为子或父）的主线关联（``appsys_bk_mainline_biz`` 与
         ``set_bk_mainline_appsys``）；
      3) 级联清理其余以 target 为源端的关联、属性、唯一规则、属性分组；
      4) 删除 cc_ObjDes 模型本体。
    """
    conn = get_db_connection()
    if conn is None:
        raise ModelError("数据库连接失败", code=500)
    supplier = DEFAULT_SUPPLIER
    nb = get_mainline_neighbors(bk_obj_id)   # 守门 + 取上下游
    child_obj_id = nb["child_obj_id"]
    parent_obj_id = nb["parent_obj_id"]
    obj_id = nb["obj_id"]
    asst_coll = _coll(BK_TABLE_NAME_OBJ_ASST)

    # 1) 重链 child -> parent（如 set_bk_mainline_biz）
    relink_id = "%s_bk_mainline_%s" % (child_obj_id, parent_obj_id)
    if not asst_coll.find_one({"bk_obj_asst_id": relink_id, "bk_supplier_account": supplier}):
        create_object_association({
            "bk_obj_id": child_obj_id,
            "bk_asst_obj_id": parent_obj_id,
            "bk_asst_id": "bk_mainline",
            "bk_obj_asst_id": relink_id,
            "mapping": "1:1",
            "on_delete": "none",
            "ispre": False,
            "creator": "admin",
            "bk_supplier_account": supplier,
        })

    # 2) 删除所有命中（target 作为子或父）的主线关联
    asst_coll.delete_many({
        "bk_asst_id": "bk_mainline",
        "bk_supplier_account": supplier,
        "$or": [{"bk_obj_id": bk_obj_id}, {"bk_asst_obj_id": bk_obj_id}],
    })

    # 3) 级联清理其余以 target 为源端的元数据
    _coll(BK_TABLE_NAME_OBJ_ASST).delete_many({"bk_obj_id": bk_obj_id, "bk_supplier_account": supplier})
    _coll(BK_TABLE_NAME_OBJ_ATT_DES).delete_many({"bk_obj_id": bk_obj_id, "bk_supplier_account": supplier})
    _coll(BK_TABLE_NAME_OBJ_UNIQUE).delete_many({"bk_obj_id": bk_obj_id, "bk_supplier_account": supplier})
    _coll(BK_TABLE_NAME_PROPERTY_GROUP).delete_many({"bk_obj_id": bk_obj_id, "bk_supplier_account": supplier})
    _delete_by_id(BK_TABLE_NAME_OBJ_DES, obj_id)
    return {"bk_obj_id": bk_obj_id, "child_obj_id": child_obj_id, "parent_obj_id": parent_obj_id}


def search_model(params):
    query = _build_query(params, "bk_supplier_account", "bk_classification_id", "bk_obj_id", "bk_obj_name")
    count, info = _list(BK_TABLE_NAME_OBJ_DES, query)
    return {"count": count, "info": info}


def search_model_topo(params):
    """简化拓扑：返回所有模型及其关联关系（best-effort，不做完整 mainline 推导）。"""
    supplier = (params or {}).get("bk_supplier_account") or DEFAULT_SUPPLIER
    models = [ _strip(d) for d in _coll(BK_TABLE_NAME_OBJ_DES).find({"bk_supplier_account": supplier}) ]
    assts = [ _strip(d) for d in _coll(BK_TABLE_NAME_OBJ_ASST).find({"bk_supplier_account": supplier}) ]
    topo = []
    for m in models:
        obj_id = m.get("bk_obj_id")
        relations = [
            {"bk_asst_obj_id": a.get("bk_asst_obj_id"), "bk_asst_id": a.get("bk_asst_id"), "mapping": a.get("mapping")}
            for a in assts if a.get("bk_obj_id") == obj_id
        ]
        topo.append({
            "bk_obj_id": obj_id,
            "bk_obj_name": m.get("bk_obj_name"),
            "bk_classification_id": m.get("bk_classification_id"),
            "bk_obj_icon": m.get("bk_obj_icon"),
            "associations": relations,
        })
    return {"count": len(topo), "info": topo}


# --------------------------------------------------------------------------- #
# Attribute（cc_ObjAttDes）
# --------------------------------------------------------------------------- #
def create_model_attributes(params):
    conn = get_db_connection()
    if conn is None:
        raise ModelError("数据库连接失败", code=500)
    # 兼容批量（数组）与单条（dict）
    items = params if isinstance(params, list) else [params]
    created = []
    for item in items:
        bk_obj_id = item.get("bk_obj_id")
        if not bk_obj_id:
            raise ModelError("属性缺少 bk_obj_id", code=400)
        supplier = item.get("bk_supplier_account") or DEFAULT_SUPPLIER
        doc = dict(item)
        doc["id"] = _new_id(conn, BK_TABLE_NAME_OBJ_ATT_DES)
        doc["bk_supplier_account"] = supplier
        doc["bk_biz_id"] = item.get("bk_biz_id", 0)
        doc["creator"] = item.get("creator") or "admin"
        doc["create_time"] = _now()
        doc["last_time"] = _now()
        doc.setdefault("bk_property_index", 0)
        doc.setdefault("editable", True)
        doc.setdefault("isreadonly", False)
        doc.setdefault("isrequired", False)
        doc.setdefault("bk_isapi", False)
        doc.setdefault("bk_issystem", False)
        doc.setdefault("bk_property_group", "default")
        _coll(BK_TABLE_NAME_OBJ_ATT_DES).insert_one(doc)
        created.append(_strip(doc))
    return created


def update_model_attributes(rid, params):
    return _update_by_id(BK_TABLE_NAME_OBJ_ATT_DES, rid, params)


def normalize_custom_model_ispre():
    """幂等自愈：将「非内置模型」属性中错误的 ispre=True 归一为 False。

    根因背景：bk-cmdb 的 initdb 数据导入会把自定义/网络模型（如 bk_switch）的
    名称、固资编号等字段也标记为 ispre=True。前端对 ispre 字段会禁用「必填」复选框，
    且 saveField 走 getPreFieldUpdateParams（仅放行 option/unit/placeholder），从而丢弃
    isrequired —— 表现为「修改模型属性必填/非必填，提交数据不生效」。

    内置模型（biz/host/set/module/process/plat/cloud_area/bk_biz_set_obj）的 ispre 保持原值。

    ⚠️ 关键约束：必须排除系统内置默认属性 ``bk_inst_name``（实例名）与主线模型的
    ``bk_parent_id``。这两个字段由 ``ensure_model_default_attributes`` 对齐 Go
    ``createDefaultAttrs`` 注入，且 **必须** ``ispre=True``（前端 ``disabledConfig``
    硬编码保护 ``bk_inst_name`` 不可删除/不可改名）。若此处把它们也归一为 False，
    自定义模型（如 ios）的实例名属性会失去保护、前端显示「未初始化」。
    """
    conn = get_db_connection()
    if conn is None:
        return 0
    coll = _coll(BK_TABLE_NAME_OBJ_ATT_DES)
    query = {
        "ispre": True,
        "bk_obj_id": {"$nin": list(BUILTIN_MODEL_IDS)},
        "bk_property_id": {"$nin": ["bk_inst_name", "bk_parent_id"]},
    }
    result = coll.update_many(query, {"$set": {"ispre": False}})
    return result.modified_count


def update_model_attribute_index(obj_id, property_id, index):
    """修改属性顺序索引 — 兼容 frontend 传 bk_property_id（字符串）或 id（整数）"""
    result = _coll(BK_TABLE_NAME_OBJ_ATT_DES).update_one(
        {"bk_obj_id": obj_id, "bk_property_id": property_id},
        {"$set": {"bk_property_index": index, "last_time": _now()}},
    )
    if result.matched_count == 0:
        # 尝试按 id（整数 pk）匹配：frontend 可能传 id 而非 bk_property_id
        try:
            pid = int(property_id)
            result = _coll(BK_TABLE_NAME_OBJ_ATT_DES).update_one(
                {"bk_obj_id": obj_id, "id": pid},
                {"$set": {"bk_property_index": index, "last_time": _now()}},
            )
        except (ValueError, TypeError):
            pass
    if result.matched_count == 0:
        raise ModelError("属性不存在: %s/%s" % (obj_id, property_id), code=404)
    return 1


def delete_model_attributes(rid):
    return _delete_by_id(BK_TABLE_NAME_OBJ_ATT_DES, rid)


def search_model_attributes(params):
    query = _build_query(
        params, "bk_supplier_account", "bk_obj_id", "bk_property_id",
        "bk_property_name", "bk_property_type", "bk_biz_id",
    )
    count, info = _list(BK_TABLE_NAME_OBJ_ATT_DES, query)
    return {"count": count, "info": info}


# --------------------------------------------------------------------------- #
# Classification（cc_ObjClassification）
# --------------------------------------------------------------------------- #
def create_classification(params):
    conn = get_db_connection()
    if conn is None:
        raise ModelError("数据库连接失败", code=500)
    bk_classification_id = (params or {}).get("bk_classification_id")
    if not bk_classification_id:
        raise ModelError("bk_classification_id 不能为空", code=400)
    supplier = (params or {}).get("bk_supplier_account") or DEFAULT_SUPPLIER
    exist = _coll(BK_TABLE_NAME_OBJ_CLASSIFICATION).find_one(
        {"bk_classification_id": bk_classification_id, "bk_supplier_account": supplier})
    if exist:
        raise ModelError("分类已存在: %s" % bk_classification_id, code=400)
    doc = dict(params)
    doc["id"] = _new_id(conn, BK_TABLE_NAME_OBJ_CLASSIFICATION)
    doc["bk_supplier_account"] = supplier
    doc["create_time"] = _now()
    doc["last_time"] = _now()
    _coll(BK_TABLE_NAME_OBJ_CLASSIFICATION).insert_one(doc)
    return _strip(doc)


def update_classification(rid, params):
    return _update_by_id(BK_TABLE_NAME_OBJ_CLASSIFICATION, rid, params)


def delete_classification(rid):
    return _delete_by_id(BK_TABLE_NAME_OBJ_CLASSIFICATION, rid)


def search_classification(params):
    query = _build_query(params, "bk_supplier_account", "bk_classification_id")
    count, info = _list(BK_TABLE_NAME_OBJ_CLASSIFICATION, query)
    return {"count": count, "info": info}


def find_classification_object(params):
    """返回某分类下的模型列表。"""
    bk_classification_id = (params or {}).get("bk_classification_id")
    supplier = (params or {}).get("bk_supplier_account") or DEFAULT_SUPPLIER
    query = {"bk_classification_id": bk_classification_id, "bk_supplier_account": supplier}
    count, info = _list(BK_TABLE_NAME_OBJ_DES, query)
    return {"count": count, "info": info}


def object_statistics(params):
    """各分类下的模型计数。"""
    supplier = (params or {}).get("bk_supplier_account") or DEFAULT_SUPPLIER
    stats = []
    for cls in _coll(BK_TABLE_NAME_OBJ_CLASSIFICATION).find({"bk_supplier_account": supplier}):
        cid = cls.get("bk_classification_id")
        cnt = _coll(BK_TABLE_NAME_OBJ_DES).count_documents(
            {"bk_classification_id": cid, "bk_supplier_account": supplier})
        stats.append({
            "bk_classification_id": cid,
            "bk_classification_name": cls.get("bk_classification_name"),
            "bk_classification_icon": cls.get("bk_classification_icon"),
            "model_count": cnt,
        })
    return stats


# --------------------------------------------------------------------------- #
# Association（cc_ObjAsst）
# --------------------------------------------------------------------------- #
def _build_obj_asst_id(obj_id, asst_id, asst_obj_id):
    return f"{obj_id}_{asst_id}_{asst_obj_id}"


def create_object_association(params):
    conn = get_db_connection()
    if conn is None:
        raise ModelError("数据库连接失败", code=500)
    bk_obj_id = (params or {}).get("bk_obj_id")
    bk_asst_id = (params or {}).get("bk_asst_id")
    bk_asst_obj_id = (params or {}).get("bk_asst_obj_id")
    if not (bk_obj_id and bk_asst_id and bk_asst_obj_id):
        raise ModelError("关联缺少 bk_obj_id / bk_asst_id / bk_asst_obj_id", code=400)
    supplier = (params or {}).get("bk_supplier_account") or DEFAULT_SUPPLIER
    # 确保关联类型在 cc_AsstDes 中存在，缺失时自动补全（避免 UI 实例关联页找不到类型的重复错误）
    exist_type = _coll(BK_TABLE_NAME_ASST_DES).find_one({"bk_asst_id": bk_asst_id, "bk_supplier_account": supplier})
    if not exist_type:
        type_doc = {
            "id": _new_id(conn, BK_TABLE_NAME_ASST_DES),
            "bk_asst_id": bk_asst_id,
            "bk_asst_name": bk_asst_id,
            "bk_supplier_account": supplier,
            "src_des": "关联",
            "dest_des": "被关联",
            "direction": "src_to_dest",
            "ispre": False,
        }
        _coll(BK_TABLE_NAME_ASST_DES).insert_one(type_doc)
    doc = dict(params)
    doc["bk_obj_asst_id"] = _build_obj_asst_id(bk_obj_id, bk_asst_id, bk_asst_obj_id)
    doc["id"] = _new_id(conn, BK_TABLE_NAME_OBJ_ASST)
    doc["bk_supplier_account"] = supplier
    doc["creator"] = (params or {}).get("creator") or "admin"
    doc["create_time"] = _now()
    doc["last_time"] = _now()
    doc.setdefault("mapping", "1:1")
    doc.setdefault("on_delete", "none")
    doc.setdefault("ispre", False)
    _coll(BK_TABLE_NAME_OBJ_ASST).insert_one(doc)
    return _strip(doc)


def update_object_association(rid, params):
    return _update_by_id(BK_TABLE_NAME_OBJ_ASST, rid, params)


def delete_object_association(rid):
    return _delete_by_id(BK_TABLE_NAME_OBJ_ASST, rid)


def search_object_association(params):
    """UI relation.vue 以 ``condition: { bk_obj_id, bk_asst_obj_id, ... }`` 包裹参数，
    需解包后将顶层键（condition 内的字段）平铺到 params 中再构建查询。

    返回 **数组**（非 {count, info}），因为 UI relation.vue 直接对返回值做
    ``source.some()`` / ``dest.filter()`` 操作，需要数组。"""
    if isinstance(params, dict) and isinstance(params.get("condition"), dict):
        cond = params["condition"]
        for _k in ("bk_obj_id", "bk_asst_obj_id", "bk_asst_id", "bk_obj_asst_id", "bk_supplier_account"):
            if _k in cond:
                params[_k] = cond[_k]
    query = _build_query(params, "bk_supplier_account", "bk_obj_id", "bk_asst_obj_id", "bk_asst_id", "bk_obj_asst_id")
    _, info = _list(BK_TABLE_NAME_OBJ_ASST, query)
    return info


# --------------------------------------------------------------------------- #
# AssociationType（cc_AsstDes）
# --------------------------------------------------------------------------- #
def create_association_type(params):
    conn = get_db_connection()
    if conn is None:
        raise ModelError("数据库连接失败", code=500)
    bk_asst_id = (params or {}).get("bk_asst_id")
    if not bk_asst_id:
        raise ModelError("bk_asst_id 不能为空", code=400)
    supplier = (params or {}).get("bk_supplier_account") or DEFAULT_SUPPLIER
    exist = _coll(BK_TABLE_NAME_ASST_DES).find_one({"bk_asst_id": bk_asst_id, "bk_supplier_account": supplier})
    if exist:
        raise ModelError("关联类型已存在: %s" % bk_asst_id, code=400)
    doc = dict(params)
    doc["id"] = _new_id(conn, BK_TABLE_NAME_ASST_DES)
    doc["bk_supplier_account"] = supplier
    doc.setdefault("direction", "src_to_dest")
    doc.setdefault("ispre", False)
    _coll(BK_TABLE_NAME_ASST_DES).insert_one(doc)
    return _strip(doc)


def update_association_type(rid, params):
    return _update_by_id(BK_TABLE_NAME_ASST_DES, rid, params)


def delete_association_type(rid):
    return _delete_by_id(BK_TABLE_NAME_ASST_DES, rid)


def search_association_type(params):
    query = _build_query(params, "bk_supplier_account", "bk_asst_id")
    count, info = _list(BK_TABLE_NAME_ASST_DES, query)
    return {"count": count, "info": info}


def find_topo_association_type(params):
    """按关联类型查询使用这些类型的关联关系列表（简化：返回 objectassociation 列表）。"""
    supplier = (params or {}).get("bk_supplier_account") or DEFAULT_SUPPLIER
    asst_ids = (params or {}).get("bk_asst_ids") or (params or {}).get("asst_ids") or []
    query = {"bk_supplier_account": supplier}
    if asst_ids:
        query["bk_asst_id"] = {"$in": asst_ids}
    count, info = _list(BK_TABLE_NAME_OBJ_ASST, query)
    return {"count": count, "info": info}


# --------------------------------------------------------------------------- #
# Unique（cc_ObjectUnique）
# --------------------------------------------------------------------------- #
def create_object_unique(obj_id, params):
    conn = get_db_connection()
    if conn is None:
        raise ModelError("数据库连接失败", code=500)
    supplier = (params or {}).get("bk_supplier_account") or DEFAULT_SUPPLIER
    doc = dict(params)
    doc["bk_obj_id"] = obj_id
    doc["bk_supplier_account"] = supplier
    doc["id"] = _new_id(conn, BK_TABLE_NAME_OBJ_UNIQUE)
    doc.setdefault("keys", [])
    doc.setdefault("ispre", False)
    doc["last_time"] = _now()
    _coll(BK_TABLE_NAME_OBJ_UNIQUE).insert_one(doc)
    return _strip(doc)


def update_object_unique(obj_id, rid, params):
    return _update_by_id(BK_TABLE_NAME_OBJ_UNIQUE, rid, params)


def delete_object_unique(obj_id, rid):
    return _delete_by_id(BK_TABLE_NAME_OBJ_UNIQUE, rid)


def search_object_unique(obj_id):
    docs = [ _strip(d) for d in _coll(BK_TABLE_NAME_OBJ_UNIQUE).find({"bk_obj_id": obj_id}) ]
    return docs


# --------------------------------------------------------------------------- #
# PropertyGroup（cc_PropertyGroup）
# --------------------------------------------------------------------------- #
def create_property_group(params):
    conn = get_db_connection()
    if conn is None:
        raise ModelError("数据库连接失败", code=500)
    bk_obj_id = (params or {}).get("bk_obj_id")
    bk_group_id = (params or {}).get("bk_group_id")
    if not (bk_obj_id and bk_group_id):
        raise ModelError("属性分组缺少 bk_obj_id / bk_group_id", code=400)
    supplier = (params or {}).get("bk_supplier_account") or DEFAULT_SUPPLIER
    doc = dict(params)
    doc["bk_supplier_account"] = supplier
    doc["bk_biz_id"] = (params or {}).get("bk_biz_id", 0)
    doc["id"] = _new_id(conn, BK_TABLE_NAME_PROPERTY_GROUP)
    doc.setdefault("bk_isdefault", False)
    doc.setdefault("is_collapse", False)
    doc.setdefault("bk_group_index", 1)
    _coll(BK_TABLE_NAME_PROPERTY_GROUP).insert_one(doc)
    return _strip(doc)


def update_property_group(params):
    rid = (params or {}).get("id")
    if rid is None:
        raise ModelError("缺少 id", code=400)
    return _update_by_id(BK_TABLE_NAME_PROPERTY_GROUP, rid, params)


def update_property_group_index(groups):
    """批量重排属性分组顺序：入参为 [{id, bk_group_index}, ...]。"""
    updated = 0
    for g in (groups or []):
        rid = g.get("id")
        if rid is None:
            continue
        result = _coll(BK_TABLE_NAME_PROPERTY_GROUP).update_one(
            {"id": int(rid)}, {"$set": {"bk_group_index": g.get("bk_group_index", 1), "last_time": _now()}})
        updated += result.modified_count
    return updated


def delete_property_group(rid):
    return _delete_by_id(BK_TABLE_NAME_PROPERTY_GROUP, rid)


def search_property_group(obj_id):
    docs = [ _strip(d) for d in _coll(BK_TABLE_NAME_PROPERTY_GROUP).find({"bk_obj_id": obj_id}) ]
    return docs


def bind_group_property(params):
    """将属性绑定到分组（简化存储：直接更新 cc_ObjAttDes.bk_property_group）。"""
    bk_obj_id = (params or {}).get("bk_obj_id")
    bk_property_id = (params or {}).get("bk_property_id")
    bk_property_group = (params or {}).get("bk_property_group")
    if not (bk_obj_id and bk_property_id and bk_property_group):
        raise ModelError("绑定缺少 bk_obj_id / bk_property_id / bk_property_group", code=400)
    result = _coll(BK_TABLE_NAME_OBJ_ATT_DES).update_one(
        {"bk_obj_id": bk_obj_id, "bk_property_id": bk_property_id},
        {"$set": {"bk_property_group": bk_property_group, "last_time": _now()}},
    )
    if result.matched_count == 0:
        raise ModelError("属性不存在: %s/%s" % (bk_obj_id, bk_property_id), code=404)
    return 1


def unbind_group_property(obj_id, property_id, group_id):
    """解绑属性与分组（简化存储：将 cc_ObjAttDes.bk_property_group 置空）。"""
    result = _coll(BK_TABLE_NAME_OBJ_ATT_DES).update_one(
        {"bk_obj_id": obj_id, "bk_property_id": property_id, "bk_property_group": group_id},
        {"$set": {"bk_property_group": "", "last_time": _now()}},
    )
    if result.matched_count == 0:
        raise ModelError("属性分组绑定不存在", code=404)
    return 1
