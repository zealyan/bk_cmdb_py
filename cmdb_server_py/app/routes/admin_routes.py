import json
from datetime import datetime
from flask import Blueprint, jsonify, request
from app.models.db import get_mongo_collection, get_db_connection, next_sequence

admin_bp = Blueprint('admin', __name__)


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


def _cond_to_mongo(cond_list):
    """将 bk-cmdb 搜索条件 [{field, operator, value}] 转换为 Mongo 查询字典。"""
    q = {}
    if not cond_list:
        return q
    for c in cond_list:
        field = c.get("field")
        op = c.get("operator", "$eq")
        val = c.get("value")
        if not field:
            continue
        if op == "$regex":
            q[field] = {"$regex": val, "$options": "i"}
        elif op in ("$in", "$nin"):
            q[field] = {op: val if isinstance(val, list) else [val]}
        elif op == "$eq":
            q[field] = val
        elif op in ("$ne", "$gt", "$gte", "$lt", "$lte"):
            q.setdefault(field, {})[op] = val
        else:
            q[field] = val
    return q


def get_inst_asst_collection_name(obj_id):
    """返回实例关联的分表名，对齐 Go GetObjectInstAsstTableName 返回 cc_InstAsst_0_pub_{obj_id}。"""
    return "cc_InstAsst_0_pub_%s" % obj_id


def _rules_to_mongo(rules):
    """将前端 conditions.rules 规则树转为 Mongo 查询字典。
    
    rules = [{field, operator, value}, ...]
    operator 支持 'equal'/'$eq'/'not_equal'/'$ne'/'in'/'$in'/'not_in'/'$nin'
    """
    q = {}
    for r in (rules or []):
        field = r.get("field")
        op = r.get("operator", "equal")
        val = r.get("value")
        if not field:
            continue
        if op in ("equal", "eq", "$eq"):
            q[field] = val
        elif op in ("not_equal", "$ne"):
            q[field] = {"$ne": val}
        elif op in ("in", "$in"):
            q[field] = {"$in": val if isinstance(val, list) else [val]}
        elif op in ("not_in", "$nin"):
            q[field] = {"$nin": val if isinstance(val, list) else [val]}
        elif op == "$regex":
            q[field] = {"$regex": val, "$options": "i"}
        elif op in ("$gt", "$gte", "$lt", "$lte"):
            q.setdefault(field, {})[op] = val
        else:
            q[field] = val
    return q


def _build_host_search_query(conn, req_data):
    """根据 hosts/search 请求体构造 cc_HostBase 的 Mongo 查询与拓扑候选主机ID。

    支持：
      - 顶层 bk_biz_id（>0 业务，-1 资源池）
      - condition 中 bk_obj_id 为 biz/set/module/host 的字段条件
      - set/module 条件经 cc_ModuleHostConfig 反查所属主机ID
    返回的 host_q 可直接用于 cc_HostBase 的 find/count_documents。
    """
    conditions = req_data.get("condition", []) or []
    bk_biz_id = req_data.get("bk_biz_id")

    rel_query = {}

    # 业务过滤：顶层 bk_biz_id 或 biz 条件中的 default==1(资源池) / bk_biz_id
    biz_id = None
    if isinstance(bk_biz_id, int):
        if bk_biz_id > 0:
            biz_id = bk_biz_id
        # bk_biz_id == -1（资源池/全部）或缺省：不限定业务，搜索全部主机。
        # 注意：关联列表（model-instance/relation/list-table.vue 的 getHostInstances）固定以
        # bk_biz_id=-1 调用，并显式带 host 字段条件（bk_host_id in [...]）按关联实例ID精确查询。
        # 若此处把 -1 映射成资源池 biz=1，再用 cc_ModuleHostConfig 反查候选集，会把「已关联但归属
        # 真实业务（bk_biz_id>1）的主机」过滤成空，导致交换机等模型的实例关联 tab 表格无行。
    biz_cond = next((c for c in conditions if c.get("bk_obj_id") == "biz"), None)
    if biz_cond:
        for f in biz_cond.get("condition", []) or []:
            if f.get("field") == "default" and f.get("value") == 1:
                biz_id = 1
            elif f.get("field") == "bk_biz_id":
                biz_id = f.get("value")
    # 集群条件 -> 候选 set_id（同时取集合真实归属业务）
    set_cond = next((c for c in conditions if c.get("bk_obj_id") == "set"), None)
    set_ids = []
    set_biz = None
    if set_cond and set_cond.get("condition"):
        set_q = _cond_to_mongo(set_cond["condition"])
        set_docs = list(conn.cc_SetBase.find(set_q, {"bk_set_id": 1, "bk_biz_id": 1, "_id": 0}))
        set_ids = [s["bk_set_id"] for s in set_docs]
        if set_ids:
            rel_query["bk_set_id"] = {"$in": set_ids}
            # 集群唯一归属某一业务。以其真实归属业务作为范围（而非请求里的“当前业务”），
            # 避免空闲机池/资源池的 set 被“当前业务 bk_biz_id”误过滤成空结果
            # （业务拓扑里选中空闲机池节点时，前端按当前业务 bk_biz_id=3 查询，
            #  但空闲机池实际属于资源池 bk_biz_id=1，导致列表空、统计为0）。
            set_biz = set_docs[0].get("bk_biz_id")

    # 模块条件 -> 候选 module_id（同样取真实归属业务）
    module_cond = next((c for c in conditions if c.get("bk_obj_id") == "module"), None)
    mod_ids = []
    mod_biz = None
    if module_cond and module_cond.get("condition"):
        mod_q = _cond_to_mongo(module_cond["condition"])
        mod_docs = list(conn.cc_ModuleBase.find(mod_q, {"bk_module_id": 1, "bk_biz_id": 1, "bk_set_id": 1, "_id": 0}))
        mod_ids = [m["bk_module_id"] for m in mod_docs]
        if mod_ids:
            rel_query["bk_module_id"] = {"$in": mod_ids}
            mod_biz = mod_docs[0].get("bk_biz_id")

    # 业务取值范围优先级：set/module 真实归属业务 > 请求中的 bk_biz_id。
    # 仅在没有 set/module 条件收窄时，才直接使用请求的 bk_biz_id（如主机管理按业务搜索）。
    scope_biz = set_biz if set_biz is not None else mod_biz
    if scope_biz is not None:
        rel_query["bk_biz_id"] = scope_biz
    elif biz_id is not None:
        rel_query["bk_biz_id"] = biz_id

    # 拓扑候选主机ID（仅当 biz/set/module 条件收窄时才有意义）
    candidate_ids = None
    if rel_query:
        candidate_ids = [r["bk_host_id"] for r in
                         conn.cc_ModuleHostConfig.find(rel_query, {"bk_host_id": 1, "_id": 0})]

    # 主机字段条件
    host_q = {}
    host_cond = next((c for c in conditions if c.get("bk_obj_id") == "host"), None)
    if host_cond and host_cond.get("condition"):
        host_q = _cond_to_mongo(host_cond["condition"])

    if candidate_ids is not None:
        if "bk_host_id" in host_q:
            # 交集：候选集（按 biz/set/module 收窄）与主机字段条件（如 bk_host_id=$eq）取AND，
            # 绝不能覆盖——否则主机详情按 bk_host_id 精确查询时会被“业务下全部主机”反查结果淹没，
            # 导致 getHostInfo 取回列表首条（非目标主机），所属拓扑显示成别的模块/集群。
            existing = host_q["bk_host_id"]
            if isinstance(existing, dict) and "$in" in existing:
                base = set(existing["$in"])
            elif isinstance(existing, dict) and "$eq" in existing:
                base = {existing["$eq"]}
            else:
                base = {existing}
            host_q["bk_host_id"] = {"$in": [hid for hid in candidate_ids if hid in base]}
        else:
            host_q["bk_host_id"] = {"$in": candidate_ids}

    return host_q


def _normalize_host_doc(doc):
    """bk-cmdb 前端对 bk_host_innerip / bk_host_outerip 等字段调用 `.split(',')` 期望字符串；
    本系统部分主机数据存为数组（如 ['10.0.1.11']），直接抛出
    `TypeError: ...split is not a function` 导致详情页渲染中断、显示“暂无数据”。
    此处将列表值转为逗号分隔字符串，适配前端标量展示（与原 bk-cmdb 单值字符串字段一致）。"""
    if not isinstance(doc, dict):
        return doc
    for k, v in list(doc.items()):
        if isinstance(v, list):
            doc[k] = ",".join(str(x) for x in v)
    # 对齐 bk-cmdb：实例响应始终带 bk_inst_id（host 真实主键为 bk_host_id 的别名），
    # 前端编辑实例时据此拼 PUT /update/instance/object/host/inst/{id} 的 URL。
    if "bk_inst_id" not in doc and "bk_host_id" in doc:
        doc["bk_inst_id"] = doc["bk_host_id"]
    return doc


def get_mock_config():
    return {
        "backend": {
            "max_biz_topo_level": 5,
            "snapshot_biz_name": ""
        },
        "site": {
            "name": {
                "i18n": {
                    "cn": "蓝鲸配置平台",
                    "en": "BlueKing Configuration Platform"
                }
            },
            "separator": "|"
        },
        "footer": {
            "contact": {
                "i18n": {
                    "cn": "",
                    "en": ""
                }
            },
            "copyright": {
                "i18n": {
                    "cn": "",
                    "en": ""
                }
            }
        },
        "validation_rules": {
            "number": {
                "value": "^(\\-|\\+)?\\d+$",
                "description": "字段类型\"数字\"的验证规则",
                "i18n": {
                    "cn": "请输入正确的数字",
                    "en": "Please enter the correct number"
                }
            },
            "float": {
                "value": "^[+-]?([0-9]*[.]?[0-9]+|[0-9]+[.]?[0-9]*)([eE][+-]?[0-9]+)?$",
                "description": "字段类型\"浮点\"的验证规则",
                "i18n": {
                    "cn": "请输入正确的浮点数",
                    "en": "Please enter the correct float data"
                }
            },
            "singlechar": {
                "value": "\\S*",
                "description": "字段类型\"短字符\"的验证规则",
                "i18n": {
                    "cn": "请输入正确的短字符内容",
                    "en": "Please enter the correct content"
                }
            },
            "longchar": {
                "value": "\\S*",
                "description": "字段类型\"长字符\"的验证规则",
                "i18n": {
                    "cn": "请输入正确的长字符内容",
                    "en": "Please enter the correct content"
                }
            },
            "associationId": {
                "value": "^[a-zA-Z][\\w]*$",
                "description": "关联类型唯一标识验证规则",
                "i18n": {
                    "cn": "格式不正确，请填写英文开头，下划线，数字，英文的组合",
                    "en": "The format is incorrect, can only contain underscores, numbers, letter and start with a letter"
                }
            },
            "classifyId": {
                "value": "^[a-zA-Z][\\w]*$",
                "description": "模型分组唯一标识验证规则",
                "i18n": {
                    "cn": "请输入正确的内容",
                    "en": "Please enter the correct content"
                }
            },
            "modelId": {
                "value": "^[a-zA-Z][\\w]*$",
                "description": "模型唯一标识验证规则",
                "i18n": {
                    "cn": "格式不正确，请填写英文开头，下划线，数字，英文的组合",
                    "en": "The format is incorrect, can only contain underscores, numbers, letter and start with a letter"
                }
            },
            "namedCharacter": {
                "value": "^[a-zA-Z0-9_\\-\\u4e00-\\u9fa5]+$",
                "description": "命名字符验证规则",
                "i18n": {
                    "cn": "只能包含数字、字母、下划线、横线和中文",
                    "en": "Can only contain numbers, letters, underscores, hyphens and Chinese characters"
                }
            }
        },
        "set": "",
        "idle_pool": {
            "idle": "",
            "fault": "",
            "recycle": "",
            "user_modules": []
        }
    }


@admin_bp.route('/api/v3/admin/find/system_config/platform_setting/current', methods=['GET', 'POST'])
def get_current_config():
    try:
        return make_response(data=get_mock_config())
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


@admin_bp.route('/api/v3/admin/find/system_config/platform_setting/initial', methods=['GET', 'POST'])
def get_default_config():
    try:
        return make_response(data=get_mock_config())
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


@admin_bp.route('/api/v3/admin/update/system_config/platform_setting', methods=['PUT', 'POST'])
def update_config():
    try:
        return make_response()
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


# 增加一些常用接口的空实现
@admin_bp.route('/api/v3/find/objclassification', methods=['POST'])
@admin_bp.route('/api/v3/find/objattgroup', methods=['POST'])
@admin_bp.route('/api/v3/find/objassociation', methods=['POST'])
@admin_bp.route('/api/v3/find/objunique', methods=['POST'])
@admin_bp.route('/api/v3/find/objasstpl', methods=['POST'])
@admin_bp.route('/api/v3/find/servicecategory', methods=['POST'])
def empty_api():
    try:
        return make_response(data={"info": []})
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


# 业务集接口
DEFAULT_BIZ_SETS = [
    {
        "bk_biz_set_id": 1,
        "bk_biz_set_name": "测试业务集",
        "bk_supplier_account": "0",
        "bk_biz_set_desc": "测试业务集描述",
        "bk_biz_set_maintainer": "admin",
        "bk_biz_set_producer": "admin",
        "create_time": "2024-01-01T00:00:00Z",
        "last_time": "2024-01-01T00:00:00Z"
    },
    {
        "bk_biz_set_id": 2,
        "bk_biz_set_name": "生产业务集",
        "bk_supplier_account": "0",
        "bk_biz_set_desc": "生产环境业务集",
        "bk_biz_set_maintainer": "admin",
        "bk_biz_set_producer": "admin",
        "create_time": "2024-01-01T00:00:00Z",
        "last_time": "2024-01-01T00:00:00Z"
    }
]

@admin_bp.route('/api/v3/findmany/biz_set/with_reduced', methods=['GET', 'POST'])
@admin_bp.route('/findmany/biz_set/with_reduced', methods=['GET', 'POST'])
def biz_set_reduced():
    try:
        return make_response(
            data={"count": len(DEFAULT_BIZ_SETS), "info": DEFAULT_BIZ_SETS},
            info=DEFAULT_BIZ_SETS,
        )
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))

@admin_bp.route('/api/v3/findmany/biz_set/simplify', methods=['GET', 'POST'])
@admin_bp.route('/findmany/biz_set/simplify', methods=['GET', 'POST'])
def biz_set_simplify():
    try:
        simplified_list = [
            {
                "bk_biz_set_id": bs.get("bk_biz_set_id"),
                "bk_biz_set_name": bs.get("bk_biz_set_name")
            }
            for bs in DEFAULT_BIZ_SETS
        ]
        return make_response(
            data={"count": len(simplified_list), "info": simplified_list},
            info=simplified_list,
        )
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


# 业务集查询接口
@admin_bp.route('/api/v3/findmany/biz_set', methods=['POST'])
@admin_bp.route('/findmany/biz_set', methods=['POST'])
def biz_set_findmany():
    try:
        return make_response(data={"info": DEFAULT_BIZ_SETS, "count": len(DEFAULT_BIZ_SETS)})
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


# 业务集创建接口
@admin_bp.route('/api/v3/create/biz_set', methods=['POST'])
@admin_bp.route('/create/biz_set', methods=['POST'])
def biz_set_create():
    try:
        req_data = request.get_json() or {}
        new_biz_set = {
            "bk_biz_set_id": len(DEFAULT_BIZ_SETS) + 1,
            "bk_biz_set_name": req_data.get("bk_biz_set_name", "新业务集"),
            "bk_supplier_account": "0",
            "bk_biz_set_desc": req_data.get("bk_biz_set_desc", ""),
            "bk_biz_set_maintainer": req_data.get("bk_biz_set_maintainer", "admin"),
            "bk_biz_set_producer": req_data.get("bk_biz_set_producer", "admin"),
            "create_time": "2024-01-01T00:00:00Z",
            "last_time": "2024-01-01T00:00:00Z"
        }
        DEFAULT_BIZ_SETS.append(new_biz_set)
        return make_response(data=new_biz_set)
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


# 业务集更新接口
@admin_bp.route('/api/v3/updatemany/biz_set', methods=['PUT', 'POST'])
@admin_bp.route('/updatemany/biz_set', methods=['PUT', 'POST'])
def biz_set_update():
    try:
        req_data = request.get_json() or {}
        return make_response(data={})
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


# 业务集删除接口
@admin_bp.route('/api/v3/deletemany/biz_set', methods=['POST'])
@admin_bp.route('/deletemany/biz_set', methods=['POST'])
def biz_set_delete():
    try:
        req_data = request.get_json() or {}
        return make_response(data={})
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


# 用户自定义接口
@admin_bp.route('/api/v3/usercustom/user/search', methods=['POST'])
def usercustom_search():
    """查询用户自定义配置 — 当前返回空（前端接手默认值）。"""
    try:
        return make_response(data={"info": []})
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


@admin_bp.route('/api/v3/usercustom/default/model', methods=['POST'])
def usercustom_default_model():
    """默认模型自定义配置。"""
    try:
        return make_response(data={})
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


# ---- usercustom 完整持久化实现 ----

USER_CUSTOM_COLL = "cc_UserCustom"


def _usercustom_load(user, name="default"):
    """从 cc_UserCustom 加载用户自定义配置。"""
    from app.models.db import get_db_connection
    conn = get_db_connection()
    if conn is None:
        return None
    return conn[USER_CUSTOM_COLL].find_one({"user": user, "name": name}, {"_id": 0})


def _usercustom_save(user, name, content):
    """保存用户自定义配置到 cc_UserCustom（upsert）。"""
    from app.models.db import get_db_connection
    conn = get_db_connection()
    if conn is None:
        return False
    from datetime import datetime
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn[USER_CUSTOM_COLL].update_one(
        {"user": user, "name": name},
        {"$set": {"user": user, "name": name, "content": content, "last_time": now_str}},
        upsert=True,
    )
    return True


# 全局配置API
@admin_bp.route('/api/v3/find/platformadmin/config', methods=['POST'])
@admin_bp.route('/find/platformadmin/config', methods=['POST'])
def find_platformadmin_config():
    try:
        return make_response(data=get_mock_config())
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


# 用户自定义API
@admin_bp.route('/api/v3/find/usercustom', methods=['POST'])
@admin_bp.route('/find/usercustom', methods=['POST'])
def find_usercustom():
    """加载用户自定义配置（前端页面加载时调用）。"""
    try:
        req_data = {}
        if request.is_json:
            req_data = request.get_json() or {}
        user = req_data.get("user", req_data.get("bk_user", "admin"))
        doc = _usercustom_load(user)
        if doc and doc.get("content"):
            info = [{"name": "default", "content": doc["content"]}]
        else:
            info = []
        return make_response(data={"info": info})
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


@admin_bp.route('/api/v3/search/usercustom', methods=['POST'])
@admin_bp.route('/search/usercustom', methods=['POST'])
def search_usercustom():
    """搜索用户自定义配置。"""
    try:
        req_data = {}
        if request.is_json:
            req_data = request.get_json() or {}
        user = req_data.get("user", req_data.get("bk_user", "admin"))
        doc = _usercustom_load(user)
        if doc and doc.get("content"):
            info = [{"name": "default", "content": doc["content"]}]
        else:
            info = []
        return make_response(data={"info": info})
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


# 拓扑主线API
@admin_bp.route('/api/v3/find/mainlineobject', methods=['POST'])
@admin_bp.route('/find/mainlineobject', methods=['POST'])
def find_mainlineobject():
    try:
        data = {
            "info": [
                {
                    "bk_obj_id": "biz",
                    "bk_obj_name": "业务",
                    "bk_supplier_account": "0",
                    "bk_next_obj": "set",
                    "is_built-in": True
                },
                {
                    "bk_obj_id": "set",
                    "bk_obj_name": "集群",
                    "bk_supplier_account": "0",
                    "bk_next_obj": "module",
                    "is_built-in": True
                },
                {
                    "bk_obj_id": "module",
                    "bk_obj_name": "模块",
                    "bk_supplier_account": "0",
                    "bk_next_obj": "host",
                    "is_built-in": True
                }
            ]
        }
        return make_response(data=data)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


# 集群模板查询API
@admin_bp.route('/api/v3/findmany/topo/set_template/bk_biz_id/<int:biz_id>/web', methods=['POST'])
@admin_bp.route('/findmany/topo/set_template/bk_biz_id/<int:biz_id>/web', methods=['POST'])
@admin_bp.route('/api/v3/findmany/topo/set_template/bk_biz_id/<int:biz_id>', methods=['POST'])
@admin_bp.route('/findmany/topo/set_template/bk_biz_id/<int:biz_id>', methods=['POST'])
def find_set_template(biz_id):
    try:
        # 从MongoDB查询集群模板
        collection = get_mongo_collection('cc_SetTemplate')
        
        # 构建查询条件
        query = {"bk_biz_id": biz_id}
        
        # 查询数据
        templates = list(collection.find(query))
        
        # 移除_id字段，转换数据格式
        result = []
        for template in templates:
            item = {
                "id": template.get("id"),
                "name": template.get("name"),
                "bk_biz_id": template.get("bk_biz_id"),
                "bk_supplier_account": template.get("bk_supplier_account"),
                "creator": template.get("creator", "system"),
                "modifier": template.get("modifier", "system"),
                "create_time": template.get("create_time"),
                "last_time": template.get("last_time")
            }
            result.append(item)
        
        return make_response(data={"info": result, "count": len(result)})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


# 服务模板查询API
@admin_bp.route('/api/v3/findmany/proc/service_template', methods=['POST'])
@admin_bp.route('/findmany/proc/service_template', methods=['POST'])
@admin_bp.route('/api/v3/findmany/proc/service_template/web', methods=['POST'])
@admin_bp.route('/findmany/proc/service_template/web', methods=['POST'])
def find_service_template():
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
        
        bk_biz_id = req_data.get('bk_biz_id', 0)
        page = req_data.get('page', {})
        start = page.get('start', 0)
        limit = page.get('limit', 20)
        
        # 从MongoDB查询服务模板
        collection = get_mongo_collection('cc_ServiceTemplate')
        
        # 查询数据
        templates = list(collection.find({}))
        
        # 过滤数据，处理bk_biz_id（可能直接在字段中，或者在metadata.label中）
        filtered_templates = []
        for template in templates:
            # 获取业务ID
            template_biz_id = template.get("bk_biz_id")
            if not template_biz_id and template.get("metadata") and template["metadata"].get("label"):
                template_biz_id = template["metadata"]["label"].get("bk_biz_id")
            # 转换为整数
            if template_biz_id is not None:
                try:
                    template_biz_id = int(template_biz_id)
                except:
                    template_biz_id = 0
            
            # 根据业务ID过滤
            if bk_biz_id <= 0 or template_biz_id == bk_biz_id:
                filtered_templates.append(template)
        
        # 移除_id字段，转换数据格式
        result = []
        for template in filtered_templates:
            # 获取业务ID
            template_biz_id = template.get("bk_biz_id")
            if not template_biz_id and template.get("metadata") and template["metadata"].get("label"):
                template_biz_id = template["metadata"]["label"].get("bk_biz_id")
            if template_biz_id is not None:
                try:
                    template_biz_id = int(template_biz_id)
                except:
                    template_biz_id = 0
            
            item = {
                "id": template.get("id"),
                "name": template.get("name"),
                "bk_biz_id": template_biz_id,
                "bk_supplier_account": template.get("bk_supplier_account"),
                "bk_service_category_id": template.get("service_category_id"),
                "creator": template.get("creator", "system"),
                "modifier": template.get("modifier", "system"),
                "create_time": template.get("create_time"),
                "last_time": template.get("last_time")
            }
            result.append(item)
        
        return make_response(data={"info": result, "count": len(result)})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


# 服务模板同步状态查询API
@admin_bp.route('/api/v3/findmany/proc/service_template/sync_status/biz/<int:bk_biz_id>', methods=['POST'])
@admin_bp.route('/findmany/proc/service_template/sync_status/biz/<int:bk_biz_id>', methods=['POST'])
@admin_bp.route('/api/v3/findmany/proc/service_template_sync_status/bk_biz_id/<int:bk_biz_id>', methods=['POST'])
@admin_bp.route('/findmany/proc/service_template_sync_status/bk_biz_id/<int:bk_biz_id>', methods=['POST'])
def find_service_template_sync_status(bk_biz_id):
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
        
        is_partial = req_data.get('is_partial', False)
        service_template_ids = req_data.get('service_template_ids', [])
        
        try:
            # 尝试从MongoDB查询服务模板
            collection = get_mongo_collection('cc_ServiceTemplate')
            
            # 查询所有数据，然后在代码中过滤
            templates = list(collection.find({}))
            
            # 过滤数据，处理bk_biz_id（可能直接在字段中，或者在metadata.label中）
            filtered_templates = []
            for template in templates:
                # 获取业务ID
                template_biz_id = template.get("bk_biz_id")
                if not template_biz_id and template.get("metadata") and template["metadata"].get("label"):
                    template_biz_id = template["metadata"]["label"].get("bk_biz_id")
                # 转换为整数
                if template_biz_id is not None:
                    try:
                        template_biz_id = int(template_biz_id)
                    except:
                        template_biz_id = 0
                
                # 根据业务ID过滤
                if bk_biz_id <= 0 or template_biz_id == bk_biz_id:
                    filtered_templates.append(template)
            
            # 如果指定了服务模板ID列表，进行进一步过滤
            if service_template_ids and len(service_template_ids) > 0:
                filtered_templates = [t for t in filtered_templates if t.get("id") in service_template_ids]
            
            # 构造同步状态结果
            result = []
            for template in filtered_templates:
                template_id = template.get("id", 0)
                template_name = template.get("name", "")
                
                item = {
                    "id": template_id,
                    "name": template_name,
                    "bk_biz_id": bk_biz_id,
                    "sync_status": "synced",
                    "last_sync_time": template.get("last_time", "2024-01-01T00:00:00Z"),
                    "sync_error": ""
                }
                result.append(item)
            
            return make_response(data={"info": result, "count": len(result)})
        except Exception as db_error:
            print(f"MongoDB查询失败，使用fallback数据: {db_error}")
            # fallback：直接从 cmdb 实例读取 cc_ServiceTemplate（项目统一数据源）
            all_templates = list(get_mongo_collection('cc_ServiceTemplate').find({}, {'_id': 0}))

            # 过滤数据
            filtered_templates = []
            for template in all_templates:
                # 获取业务ID
                template_biz_id = template.get("bk_biz_id")
                if not template_biz_id and template.get("metadata") and template["metadata"].get("label"):
                    template_biz_id = template["metadata"]["label"].get("bk_biz_id")
                # 转换为整数
                if template_biz_id is not None:
                    try:
                        template_biz_id = int(template_biz_id)
                    except:
                        template_biz_id = 0
                
                # 根据业务ID过滤
                if bk_biz_id <= 0 or template_biz_id == bk_biz_id:
                    filtered_templates.append(template)
            
            # 如果指定了服务模板ID列表，进行进一步过滤
            if service_template_ids and len(service_template_ids) > 0:
                filtered_templates = [t for t in filtered_templates if t.get("id") in service_template_ids]
            
            # 构造同步状态结果
            result = []
            for template in filtered_templates:
                template_id = template.get("id", 0)
                template_name = template.get("name", "")
                
                item = {
                    "id": template_id,
                    "name": template_name,
                    "bk_biz_id": bk_biz_id,
                    "sync_status": "synced",
                    "last_sync_time": template.get("last_time", "2024-01-01T00:00:00Z"),
                    "sync_error": ""
                }
                result.append(item)
            
            return make_response(data={"info": result, "count": len(result)})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


# 对象模型API
@admin_bp.route('/api/v3/find/object', methods=['POST'])
@admin_bp.route('/find/object', methods=['POST'])
def find_object():
    """查询对象模型定义（兼容前端旧版调用，委托给 model_routes 的核心逻辑）。"""
    from app.core import model as core
    try:
        req_data = request.get_json() or {}
        result = core.search_model(req_data)
        # 保持旧版格式：data.info + 补全前端需要的字段
        info = []
        for doc in (result.get("info") or []):
            info.append({
                "id": doc.get("id"),
                "bk_obj_id": doc.get("bk_obj_id"),
                "bk_obj_name": doc.get("bk_obj_name"),
                "bk_classification_id": doc.get("bk_classification_id"),
                "bk_supplier_account": doc.get("bk_supplier_account"),
                "bk_obj_icon": doc.get("bk_obj_icon"),
                "is_built-in": doc.get("ispre"),
                "is_pre": doc.get("is_pre"),
                "bk_ispaused": doc.get("bk_ispaused", False),
            })
        return make_response(data={"info": info, "count": len(info)})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))
        return make_response(result=False, code=500, message=str(e))


# 主机搜索API
@admin_bp.route('/api/v3/hosts/search', methods=['POST'])
@admin_bp.route('/hosts/search', methods=['POST'])
def hosts_search():
    """主机搜索：支持 bk_biz_id / set / module / host 字段条件、分页与下一页。

    请求体：{ bk_biz_id, condition:[{bk_obj_id, condition:[{field,operator,value}]}],
             page:{start,limit,sort} }
    响应：{ info:[{host, module, set, biz}], count }
    下一页：调用方令 start += limit，直至 start >= count。
    """
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        req_data = request.get_json() or {}
        page = req_data.get('page', {}) or {}
        start = page.get('start', 0)
        limit = page.get('limit', 20)
        sort = page.get('sort', 'bk_host_id')

        # 解析搜索条件（bk_biz_id / set / module / host 字段）
        host_q = _build_host_search_query(conn, req_data)

        collection = conn['cc_HostBase']
        total_count = collection.count_documents(host_q)

        # 排序
        cursor = collection.find(host_q)
        if sort:
            sort_dir = -1 if sort.startswith('-') else 1
            sort_field = sort[1:] if sort.startswith('-') else sort
            cursor = cursor.sort(sort_field, sort_dir)

        # 分页
        cursor = cursor.skip(start).limit(limit)

        # 收集主机ID用于关联查询
        host_id_list = [doc.get('bk_host_id') for doc in cursor]

        result_info = []
        if host_id_list:
            host_relations = list(conn.cc_ModuleHostConfig.find({"bk_host_id": {"$in": host_id_list}}))

            module_ids = list(set([r.get('bk_module_id') for r in host_relations if r.get('bk_module_id')]))
            set_ids = list(set([r.get('bk_set_id') for r in host_relations if r.get('bk_set_id')]))
            biz_ids = list(set([r.get('bk_biz_id') for r in host_relations if r.get('bk_biz_id')]))

            module_map = {}
            if module_ids:
                for m in conn.cc_ModuleBase.find({"bk_module_id": {"$in": module_ids}}):
                    m.pop('_id', None)
                    module_map[m.get('bk_module_id')] = m

            set_map = {}
            if set_ids:
                for s in conn.cc_SetBase.find({"bk_set_id": {"$in": set_ids}}):
                    s.pop('_id', None)
                    set_map[s.get('bk_set_id')] = s

            biz_map = {}
            if biz_ids:
                for b in conn.cc_ApplicationBase.find({"bk_biz_id": {"$in": biz_ids}}):
                    b.pop('_id', None)
                    biz_map[b.get('bk_biz_id')] = b

            host_module_map = {}
            host_set_map = {}
            host_biz_map = {}
            for rel in host_relations:
                hid = rel.get('bk_host_id')
                host_module_map.setdefault(hid, [])
                if rel.get('bk_module_id') not in host_module_map[hid]:
                    host_module_map[hid].append(rel.get('bk_module_id'))
                host_set_map.setdefault(hid, [])
                if rel.get('bk_set_id') not in host_set_map[hid]:
                    host_set_map[hid].append(rel.get('bk_set_id'))
                host_biz_map[hid] = rel.get('bk_biz_id')

            for doc in collection.find({"bk_host_id": {"$in": host_id_list}}):
                doc.pop('_id', None)
                hid = doc.get('bk_host_id')
                item = {'host': _normalize_host_doc(doc)}
                item['module'] = [module_map[mid].copy() for mid in host_module_map.get(hid, []) if mid in module_map]
                item['set'] = [set_map[sid].copy() for sid in host_set_map.get(hid, []) if sid in set_map]
                hbiz = host_biz_map.get(hid)
                item['biz'] = [biz_map[hbiz].copy()] if (hbiz and hbiz in biz_map) else []
                result_info.append(item)

        return make_response(data={"info": result_info, "count": total_count})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


# 批量更新/删除主机时，从请求体中剔除的控制字段（非主机业务属性）
_HOST_BATCH_SKIP = {
    "bk_host_id", "bk_cloud_id", "metadata", "bk_supplier_account", "bk_data_status",
}


def _parse_json_body_flex():
    """兼容 JSON / raw 的请求体解析，返回 dict。"""
    req = request.get_json(silent=True)
    if req is None:
        try:
            req = json.loads(request.data or b"{}")
        except Exception:
            req = {}
    return req or {}


def _host_ids_from_raw(raw):
    """bk_host_id 可为数字或逗号分隔字符串，统一解析为 int 列表。"""
    if raw is None:
        return []
    if isinstance(raw, bool):
        return []
    if isinstance(raw, (int, float)):
        id_str = str(int(raw))
    else:
        id_str = str(raw)
    ids = []
    for x in id_str.split(","):
        x = str(x).strip()
        if x:
            try:
                ids.append(int(x))
            except ValueError:
                continue
    return ids


@admin_bp.route('/api/v3/hosts/batch', methods=['PUT'])
@admin_bp.route('/hosts/batch', methods=['PUT'])
def update_host_batch():
    """批量更新主机属性（对齐 PUT /hosts/batch）。

    前端 body: {<field>:<value>, ..., bk_host_id: "1,2,3"}（bk_host_id 可为数字或逗号字符串）。
    剔除 bk_host_id / bk_cloud_id / metadata 等控制字段后，其余字段 $set 到 cc_HostBase。
    """
    try:
        req = _parse_json_body_flex()
        ids = _host_ids_from_raw(req.get("bk_host_id"))
        if not ids:
            return make_response(result=False, code=500, message="缺少或无效的 bk_host_id")
        update_fields = {
            k: v for k, v in req.items()
            if k not in _HOST_BATCH_SKIP and not k.startswith("_")
        }
        if not update_fields:
            return make_response(data={})
        update_fields["last_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")
        conn["cc_HostBase"].update_many(
            {"bk_host_id": {"$in": ids}}, {"$set": update_fields}
        )
        return make_response(data={})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@admin_bp.route('/api/v3/hosts/batch', methods=['DELETE'])
@admin_bp.route('/hosts/batch', methods=['DELETE'])
def delete_host_batch():
    """批量删除主机（对齐 DELETE /hosts/batch）。

    前端 body: {data: {bk_host_id: "1,2,3", bk_supplier_account: "0"}} 或 {bk_host_id: "1,2,3"}。
    同步清理 cc_HostBase 与 cc_ModuleHostConfig 中的主机记录。
    """
    try:
        req = _parse_json_body_flex()
        # 兼容 {data:{...}} 包裹结构
        inner = req.get("data") if isinstance(req.get("data"), dict) else req
        raw = inner.get("bk_host_id") if isinstance(inner, dict) else None
        if raw is None:
            raw = req.get("bk_host_id")
        ids = _host_ids_from_raw(raw)
        if not ids:
            return make_response(result=False, code=500, message="缺少或无效的 bk_host_id")
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")
        conn["cc_HostBase"].delete_many({"bk_host_id": {"$in": ids}})
        conn["cc_ModuleHostConfig"].delete_many({"bk_host_id": {"$in": ids}})
        return make_response(data={})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@admin_bp.route('/api/v3/hosts/search/web', methods=['POST'])
@admin_bp.route('/hosts/search/web', methods=['POST'])
def hosts_search_web():
    """全局主机搜索（顶栏搜索）：复用与 hosts/search 一致的搜索条件解析与分页。"""
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        req_data = request.get_json() or {}
        page = req_data.get('page', {}) or {}
        start = page.get('start', 0)
        limit = page.get('limit', 20)
        sort = page.get('sort', 'bk_host_id')

        host_q = _build_host_search_query(conn, req_data)

        collection = conn['cc_HostBase']
        total_count = collection.count_documents(host_q)
        cursor = collection.find(host_q)
        if sort:
            sort_dir = -1 if sort.startswith('-') else 1
            sort_field = sort[1:] if sort.startswith('-') else sort
            cursor = cursor.sort(sort_field, sort_dir)
        cursor = cursor.skip(start).limit(limit)

        hosts = []
        for doc in cursor:
            doc.pop('_id', None)
            hosts.append(_normalize_host_doc(doc))

        return make_response(data={"info": hosts, "count": total_count})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@admin_bp.route('/hosts/<supplier_account>/<int:bk_host_id>', methods=['GET'])
def hosts_detail(supplier_account, bk_host_id):
    """主机详情：GET /hosts/{bk_supplier_account}/{bk_host_id}

    复刻 bk-cmdb 的 HostInstanceProperties 数组：
    [{bk_property_id, bk_property_name, bk_property_value}]，属性名取自 cc_ObjAttDes(bk_obj_id=host)。
    """
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        host = conn.cc_HostBase.find_one({"bk_host_id": bk_host_id})
        if not host:
            return make_response(result=False, code=404, message="主机不存在")

        host.pop('_id', None)
        # 列表字段（如 bk_host_innerip）转为逗号分隔字符串，避免前端 .split 报错
        host = _normalize_host_doc(host)

        # 主机属性定义（bk_obj_id=host）
        attrs = list(conn.cc_ObjAttDes.find({"bk_obj_id": "host"}))
        properties = []
        for a in attrs:
            pid = a.get("bk_property_id")
            if not pid:
                continue
            properties.append({
                "bk_property_id": pid,
                "bk_property_name": a.get("bk_property_name", pid),
                "bk_property_value": host.get(pid)
            })

        return make_response(data=properties)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


# ────────────────────── 实例关联 API ──────────────────────
# 参考 Go: topo_server/service/association.go
# 存储集合: get_inst_asst_collection_name(obj_id)->cc_InstAsst_0_pub_{obj_id}
# 查询分表命名对齐 GetObjectInstAsstTableName(objID, "0")


# 全量查询实例关联（列表用）—— find/instassociation
# body: {condition: {bk_obj_id?, bk_inst_id?, ...}, bk_obj_id: "..."}
# 返回: {info: [...]}
@admin_bp.route('/api/v3/find/instassociation', methods=['POST'])
@admin_bp.route('/find/instassociation', methods=['POST'])
def find_inst_association():
    # 注意：前端 model-instance/relation/list.vue 与 host-details/children/association-list.vue
    # 均对 searchInstAssociation 的返回值直接做 .map(item => ...)，
    # 因此此处必须直接返回【数组】，不能包成 {info: [...]}（否则 .map 抛错被 try/catch 吞掉，
    # 导致 this.instances 恒为空、关联 tab 不显示表格）。
    try:
        req = _parse_json_body_flex()
        cond = req.get("condition") or {}
        obj_id = req.get("bk_obj_id")
        if not obj_id:
            return make_response(data=[])
        # 类型对齐：bk_inst_id / bk_asst_inst_id 在 Mongo 分表中以 int 存储，
        # 前端 condition 中的值可能为字符串（如路由参数），需统一转为 int 才能命中。
        for _k in ("bk_inst_id", "bk_asst_inst_id"):
            if _k in cond and isinstance(cond[_k], str) and cond[_k].isdigit():
                cond[_k] = int(cond[_k])
        collection = get_mongo_collection(get_inst_asst_collection_name(obj_id))
        docs = list(collection.find(cond, {"_id": 0}))
        return make_response(data=docs)
    except Exception as e:
        import traceback; traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


# 搜索实例关联（查重用）—— search/instance_associations/object/{bk_obj_id}
# body: {bk_obj_id, conditions: {condition, rules}, page: {start, limit}}
# 返回: {info: [...]}
@admin_bp.route('/api/v3/search/instance_associations/object/<obj_id>', methods=['POST'])
@admin_bp.route('/search/instance_associations/object/<obj_id>', methods=['POST'])
def search_instance_associations(obj_id):
    try:
        req = _parse_json_body_flex()
        collection = get_mongo_collection(get_inst_asst_collection_name(obj_id))
        page = req.get("page") or {}
        start = int(page.get("start", 0))
        limit = int(page.get("limit", 200))
        # 解析 conditions.rules 规则树 → mongo query
        conditions = req.get("conditions") or {}
        rules = (conditions if isinstance(conditions, dict) else {}).get("rules", [])
        if not rules:
            rules = conditions if isinstance(conditions, list) else []
        mq = _rules_to_mongo(rules)
        docs = list(collection.find(mq, {"_id": 0}).skip(start).limit(limit))
        return make_response(data={"info": docs})
    except Exception as e:
        import traceback; traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


# 统计实例关联数（查重用）—— count/instance_associations/object/{bk_obj_id}
# body: {bk_obj_id, conditions: {condition, rules}}
# 返回: {count: N}
@admin_bp.route('/api/v3/count/instance_associations/object/<obj_id>', methods=['POST'])
@admin_bp.route('/count/instance_associations/object/<obj_id>', methods=['POST'])
def count_instance_associations(obj_id):
    try:
        req = _parse_json_body_flex()
        collection = get_mongo_collection(get_inst_asst_collection_name(obj_id))
        conditions = req.get("conditions") or {}
        rules = (conditions if isinstance(conditions, dict) else {}).get("rules", [])
        if not rules:
            rules = conditions if isinstance(conditions, list) else []
        mq = _rules_to_mongo(rules)
        mq["bk_obj_id"] = obj_id  # 对齐 Go CountInstanceAssociations 额外加 bk_obj_id
        cnt = collection.count_documents(mq)
        return make_response(data={"count": cnt})
    except Exception as e:
        import traceback; traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


# 按 Object 查询实例关联（object-common-inst.js 用）
# body: {bk_obj_id, conditions: {condition, rules}}
# 返回: {info: [...]}
@admin_bp.route('/api/v3/find/instassociation/object/<obj_id>', methods=['POST'])
@admin_bp.route('/find/instassociation/object/<obj_id>', methods=['POST'])
def find_inst_association_by_object(obj_id):
    try:
        req = _parse_json_body_flex()
        collection = get_mongo_collection(get_inst_asst_collection_name(obj_id))
        conditions = req.get("conditions") or {}
        rules = (conditions if isinstance(conditions, dict) else {}).get("rules", [])
        if not rules:
            rules = conditions if isinstance(conditions, list) else []
        mq = _rules_to_mongo(rules)
        docs = list(collection.find(mq, {"_id": 0}))
        return make_response(data={"info": docs})
    except Exception as e:
        import traceback; traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


# 新增实例关联（对齐 Go pairedInsert：正向 + 反向文档各写入 BOTH 源/目标分表）
#
# body: {bk_obj_asst_id, bk_inst_id, bk_asst_inst_id}
# 从 cc_ObjAsst 反查 bk_obj_id / bk_asst_obj_id，构造两种视角的文档：
#
#   【正向视角】bk_obj_id=源, bk_inst_id=源实例, bk_asst_obj_id=目标, bk_asst_inst_id=目标实例
#   【反向视角】bk_obj_id=目标, bk_inst_id=目标实例, bk_asst_obj_id=源, bk_asst_inst_id=源实例
#
# 前端主机详情"关联"tab 对同一张分表 CC_InstAsst_0_pub_{obj} 发两个查询：
#   - source: {bk_obj_id=当前obj, bk_inst_id=当前instId}  → 需要正向视角文档
#   - target: {bk_asst_obj_id=当前obj, bk_asst_inst_id=当前instId}  → 需要反向视角文档
# 因此必须将两种视角的文档都写入当前表，否则 target 查询命中不了。
#
# 实现：正向/反向各以独立 id 写入 BOTH cc_InstAsst_0_pub_{源} + cc_InstAsst_0_pub_{目标}。
# 返回: {id, bk_inst_id, bk_asst_inst_id}
@admin_bp.route('/api/v3/create/instassociation', methods=['POST'])
@admin_bp.route('/create/instassociation', methods=['POST'])
def create_inst_association():
    try:
        req = _parse_json_body_flex()
        bk_obj_asst_id = req.get("bk_obj_asst_id")
        bk_inst_id = req.get("bk_inst_id")
        bk_asst_inst_id = req.get("bk_asst_inst_id")
        if not all([bk_obj_asst_id, bk_inst_id is not None, bk_asst_inst_id is not None]):
            return make_response(result=False, code=500,
                                 message="bk_obj_asst_id、bk_inst_id、bk_asst_inst_id 均为必填")
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")
        # 查 cc_ObjAsst 获取关联定义
        asst_def = conn["cc_ObjAsst"].find_one({"bk_obj_asst_id": bk_obj_asst_id})
        if not asst_def:
            return make_response(result=False, code=500,
                                 message="模型关联定义不存在: " + str(bk_obj_asst_id))
        bk_obj_id = asst_def.get("bk_obj_id", "")         # 关联定义中的「源」类型
        bk_asst_obj_id = asst_def.get("bk_asst_obj_id", "")  # 关联定义中的「目标」类型
        bk_asst_id_val = asst_def.get("bk_asst_id", "")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bk_inst_id_int = int(bk_inst_id)
        bk_asst_inst_id_int = int(bk_asst_inst_id)
        supplier = "0"

        def _write_pair(table, seq, a_obj_id, a_inst, b_obj_id, b_inst):
            """向 table 写入一条关联文档（a_obj_id/a_inst → b_obj_id/b_inst）"""
            coll = get_mongo_collection(table)
            new_id = next_sequence(conn, seq)
            doc = {
                "id": new_id,
                "bk_obj_asst_id": bk_obj_asst_id,
                "bk_inst_id": a_inst,
                "bk_asst_inst_id": b_inst,
                "bk_obj_id": a_obj_id,
                "bk_asst_obj_id": b_obj_id,
                "bk_asst_id": bk_asst_id_val,
                "bk_supplier_account": supplier,
                "create_time": now_str,
                "last_time": now_str,
                "creator": "admin",
            }
            coll.insert_one(doc)
            return new_id

        src_table = get_inst_asst_collection_name(bk_obj_id)           # cc_InstAsst_0_pub_bk_switch
        dst_table = get_inst_asst_collection_name(bk_asst_obj_id)      # cc_InstAsst_0_pub_host
        src_seq = src_table
        dst_seq = dst_table

        # 正向视角：源→目标（两个实例）
        fwd_id = _write_pair(src_table, src_seq,
                              bk_obj_id, bk_inst_id_int,            # bk_obj_id=bk_switch, inst=switchId
                              bk_asst_obj_id, bk_asst_inst_id_int)  # asst_obj=host, asst_inst=hostId
        # 反向视角：目标→源（互换）
        # 无额外 id 返回，delete 走 $or 清除所有

        # 正向视角也写入目标表（让目标表的 target 查询能命中）
        _write_pair(dst_table, dst_seq,
                     bk_obj_id, bk_inst_id_int,
                     bk_asst_obj_id, bk_asst_inst_id_int)
        # 反向视角也写入源表（让源表的 target 查询能命中）
        _write_pair(src_table, src_seq,
                     bk_asst_obj_id, bk_asst_inst_id_int,
                     bk_obj_id, bk_inst_id_int)
        # 反向视角也写入目标表（让目标表的 source 查询能命中）
        _write_pair(dst_table, dst_seq,
                     bk_asst_obj_id, bk_asst_inst_id_int,
                     bk_obj_id, bk_inst_id_int)

        return make_response(data={"id": fwd_id, "bk_inst_id": bk_inst_id_int,
                                    "bk_asst_inst_id": bk_asst_inst_id_int})
    except Exception as e:
        import traceback; traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


# 删除实例关联（对齐 Go: 从 BOTH 分表清除正向 + 反向共 4 条配对文档）
# 路径: delete/instassociation/{bk_obj_id}/{association_id}
# 逻辑：
#   1. 从 cc_InstAsst_0_pub_{bk_obj_id} 找到 id=association_id 的文档
#   2. 用其 bk_obj_asst_id + 双向 inst_id 组合从 BOTH 分表执行 $or 删除
@admin_bp.route('/api/v3/delete/instassociation/<obj_id>/<asst_id>', methods=['DELETE'])
@admin_bp.route('/delete/instassociation/<obj_id>/<asst_id>', methods=['DELETE'])
def delete_inst_association(obj_id, asst_id):
    # 说明：一条逻辑关联在 MongoDB 中以 4 条配对文档存储（正向/反向视角 × 源/目标分表），
    # 但前端关联 tab / 新增关联弹出框会用「source + target」两次查询把同一条关联渲染成【两行】。
    # 删除其中任一行时，下方 delete_many($or) 会一次性清掉全部 4 条配对文档。
    # 注意：前端弹窗（cancelAssociation）传入的 objId 为当前模型，但列表行 id 可能落在
    # 【对方模型】的分表（4-doc 设计下不同视角文档存于不同分表）。因此若仅在 objId 分表找不到，
    # 需扫描所有 cc_InstAsst_0_pub_* 分表定位该 id，避免「找不到→误报成功却未删除」。
    # 仅当所有分表都无此 id 时，才视为已删除（幂等成功）。
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")
        try:
            aid = int(asst_id)
        except (ValueError, TypeError):
            return make_response(result=False, code=400,
                                 message="非法的关联ID: %s" % asst_id)
        tbl_obj = get_inst_asst_collection_name(obj_id)
        # 1. 先在当前模型分表定位参考文档
        doc = get_mongo_collection(tbl_obj).find_one({"id": aid}, {"_id": 0})
        # 2. 若未找到，扫描所有关联分表（兼容 id 落在对方分表的情况）
        if not doc:
            for cname in conn.list_collection_names():
                if cname.startswith("cc_InstAsst_0_pub_"):
                    d = get_mongo_collection(cname).find_one({"id": aid}, {"_id": 0})
                    if d:
                        doc = d
                        break
        if not doc:
            # 幂等成功：关联确实不存在（可能已被其它操作清除），目标状态已达成
            return make_response(data={})
        A, B = doc.get("bk_inst_id"), doc.get("bk_asst_inst_id")
        asst_type = doc.get("bk_obj_asst_id")
        # 3. 一条关联的全部 4 条文档分布在两张分表：cc_InstAsst_0_pub_{bk_obj_id}
        #    与 cc_InstAsst_0_pub_{bk_asst_obj_id}。必须用文档自身的这两个字段对称地
        #    确定两张表（不能只用 URL 的 obj_id 或 doc.bk_asst_obj_id 之一，否则当
        #    host 是关联「目标」(bk_asst_obj_id=host) 时，对方表会被算成同表，导致
        #    另一张分表永不清空 → 数据残留、提示成功却未真正删除）。
        q = {
            "bk_obj_asst_id": asst_type,
            "$or": [
                {"bk_inst_id": A, "bk_asst_inst_id": B},
                {"bk_inst_id": B, "bk_asst_inst_id": A},
            ]
        }
        tbl_a = get_inst_asst_collection_name(doc.get("bk_obj_id", ""))
        tbl_b = get_inst_asst_collection_name(doc.get("bk_asst_obj_id", ""))
        get_mongo_collection(tbl_a).delete_many(q)
        get_mongo_collection(tbl_b).delete_many(q)
        return make_response(data={})
    except Exception as e:
        import traceback; traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


# 保存用户自定义配置API
@admin_bp.route('/api/v3/usercustom', methods=['POST'])
@admin_bp.route('/usercustom', methods=['POST'])
@admin_bp.route('/api/v3/usercustom', methods=['POST'])
@admin_bp.route('/usercustom', methods=['POST'])
def save_usercustom():
    """保存用户自定义配置到 cc_UserCustom。
    
    前端发送: { "usercustom": { ... }, "user": "username" }
    或 { "content": {...}, "name": "default" }
    """
    try:
        req_data = {}
        if request.is_json:
            req_data = request.get_json() or {}
        user = req_data.get("user", req_data.get("bk_user", "admin"))
        
        # 尝试提取实际内容
        content = req_data.get("usercustom") or req_data.get("content") or req_data
        if isinstance(content, dict) and "user" in content and len(content) == 1:
            # 如果只有 user 字段，说明前端只传了用户名，保存空内容
            pass
        
        _usercustom_save(user, "default", content)
        return make_response(data={})
    except Exception as e:
        import traceback; traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


# 用户自定义默认配置API
@admin_bp.route('/api/v3/usercustom/default/search', methods=['POST'])
@admin_bp.route('/usercustom/default/search', methods=['POST'])
def usercustom_default_search():
    """搜索默认用户配置（列配置等）。"""
    try:
        req_data = {}
        if request.is_json:
            req_data = request.get_json() or {}
        user = req_data.get("user", req_data.get("bk_user", "admin"))
        
        # 先从已保存的用户配置中读列配置
        doc = _usercustom_load(user)
        saved_content = doc.get("content", {}) if doc else {}
        
        # 合并：已保存配置优先，否则用默认空值
        data = {
            "recently_models": saved_content.get("recently_models", []),
            "columns_config_business": saved_content.get("columns_config_business", []),
            "columns_config_host": saved_content.get("columns_config_host", []),
            "columns_config_set": saved_content.get("columns_config_set", []),
            "columns_config_module": saved_content.get("columns_config_module", []),
        }
        return make_response(data=data)
    except Exception as e:
        import traceback; traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


# 模型拓扑API
@admin_bp.route('/api/v3/find/objecttopo/scope_type/global/scope_id/0', methods=['POST'])
@admin_bp.route('/find/objecttopo/scope_type/global/scope_id/0', methods=['POST'])
def find_object_topo():
    try:
        req_data = {}
        if request.is_json:
            req_data = request.get_json() or {}
        bk_supplier_account = req_data.get('bk_supplier_account', '0')

        obj_des_coll = get_mongo_collection('cc_ObjDes')
        obj_asst_coll = get_mongo_collection('cc_ObjAsst')
        asst_des_coll = get_mongo_collection('cc_AsstDes')

        # 关联类型定义：bk_asst_id -> id（供前端 getAsstDetail 用 bk_asst_inst_id 匹配方向/名称）
        # 注意：cc_ObjAsst.id 与 cc_AsstDes.id 是两套自增序列，不能直接混用，
        # 需通过 bk_asst_id 把关联实例映射到其关联类型定义的 id。
        asst_des_docs = list(asst_des_coll.find(
            {"bk_supplier_account": bk_supplier_account}, {"_id": 0, "id": 1, "bk_asst_id": 1}
        ))
        asst_des_id_map = {d["bk_asst_id"]: d.get("id") for d in asst_des_docs}

        models = list(obj_des_coll.find(
            {"bk_supplier_account": bk_supplier_account}, {"_id": 0}
        ))
        obj_assts = list(obj_asst_coll.find(
            {"bk_supplier_account": bk_supplier_account}, {"_id": 0}
        ))
        asst_by_obj = {}
        for a in obj_assts:
            asst_by_obj.setdefault(a.get("bk_obj_id"), []).append(a)

        def extract_xy(position):
            """DB 的 position 实际以 JSON 字符串存储，如
            '{"bk_host_manage":{"x":-600,"y":-650}}'；也可能是 dict、null 或空串。
            统一提取为 {x, y} 供前端 node.position.x / node.position.y 使用。"""
            if position is None:
                return {"x": None, "y": None}
            if isinstance(position, str):
                s = position.strip()
                if not s:
                    return {"x": None, "y": None}
                try:
                    position = json.loads(s)
                except Exception:
                    return {"x": None, "y": None}
            if not isinstance(position, dict):
                return {"x": None, "y": None}
            if "x" in position and "y" in position:
                return {"x": position.get("x"), "y": position.get("y")}
            vals = [v for v in position.values() if isinstance(v, dict) and "x" in v]
            if vals:
                return {"x": vals[0].get("x"), "y": vals[0].get("y")}
            return {"x": None, "y": None}

        nodes = []
        for m in models:
            obj_id = m.get("bk_obj_id")
            position = extract_xy(m.get("position"))
            node_assts = []
            for a in asst_by_obj.get(obj_id, []):
                asst_type_id = asst_des_id_map.get(a.get("bk_asst_id"))
                node_assts.append({
                    "bk_asst_inst_id": asst_type_id,
                    "bk_obj_id": a.get("bk_asst_obj_id"),
                    "bk_inst_id": a.get("id"),
                })
            nodes.append({
                "bk_obj_id": obj_id,
                "bk_inst_id": m.get("id", 0),
                "node_name": m.get("bk_obj_name", obj_id),
                "bk_obj_icon": m.get("bk_obj_icon", ""),
                "ispre": m.get("ispre", False),
                "node_type": m.get("bk_obj_type") or "",
                "bk_classification_id": m.get("bk_classification_id", ""),
                "position": position,
                "assts": node_assts,
            })

        return make_response(data=nodes)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


# 更新模型拓扑API
@admin_bp.route('/api/v3/update/objecttopo/scope_type/global/scope_id/0', methods=['POST'])
@admin_bp.route('/update/objecttopo/scope_type/global/scope_id/0', methods=['POST'])
def update_object_topo():
    try:
        return make_response()
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


# 审计字典API
@admin_bp.route('/api/v3/find/audit_dict', methods=['GET'])
@admin_bp.route('/find/audit_dict', methods=['GET'])
def find_audit_dict():
    try:
        data = {
            "header": {
                "model": "模型",
                "operate": "操作",
                "resource_type": "资源类型"
            },
            "operation_type": [
                {"id": "create", "name": "新建"},
                {"id": "update", "name": "更新"},
                {"id": "delete", "name": "删除"},
                {"id": "archive", "name": "归档"}
            ]
        }
        return make_response(data=data)
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


# 审计列表API
@admin_bp.route('/api/v3/findmany/audit_list', methods=['POST'])
@admin_bp.route('/findmany/audit_list', methods=['POST'])
def findmany_audit_list():
    try:
        req_data = request.get_json() or {}
        page = req_data.get('page', {})
        start = page.get('start', 0)
        limit = page.get('limit', 20)
        
        data = {
            "info": [
                {
                    "id": 1,
                    "bk_biz_id": 2,
                    "bk_supplier_account": "0",
                    "operation_time": "2024-01-01 10:00:00",
                    "user": "admin",
                    "operate": "create",
                    "action": {
                        "id": "create",
                        "name": "新建"
                    },
                    "resource_type": "business",
                    "resource": {
                        "id": 123,
                        "name": "测试业务"
                    },
                    "detail": {
                        "bk_biz_name": "测试业务"
                    }
                }
            ],
            "count": 1
        }
        
        return make_response(data=data)
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


# 审计详情API
@admin_bp.route('/api/v3/find/audit', methods=['POST'])
@admin_bp.route('/find/audit', methods=['POST'])
def find_audit():
    try:
        req_data = request.get_json() or {}
        ids = req_data.get('id', [])
        
        data = []
        for i, audit_id in enumerate(ids):
            data.append({
                "id": audit_id,
                "bk_biz_id": 2,
                "bk_supplier_account": "0",
                "operation_time": "2024-01-01 10:00:00",
                "user": "admin",
                "operate": "create",
                "action": {
                    "id": "create",
                    "name": "新建"
                },
                "resource_type": "business",
                "resource": {
                    "id": audit_id,
                    "name": f"业务{audit_id}"
                },
                "detail": {}
            })
        
        return make_response(data=data)
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


# 实例审计API
@admin_bp.route('/api/v3/find/inst_audit', methods=['POST'])
@admin_bp.route('/find/inst_audit', methods=['POST'])
def find_inst_audit():
    try:
        data = {
            "info": [],
            "count": 0
        }
        return make_response(data=data)
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


# 蓝鲸修改配置API
@admin_bp.route('/api/v3/system/config/user_config/blueking_modify', methods=['POST'])
@admin_bp.route('/system/config/user_config/blueking_modify', methods=['POST'])
def blueking_modify():
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
        
        # 返回蓝鲸修改配置，默认返回 false 表示不可修改
        return make_response(data={"is_allow_to_modify": False})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


# 进程服务分类统计API
@admin_bp.route('/api/v3/findmany/proc/service_category/with_statistics', methods=['POST'])
@admin_bp.route('/findmany/proc/service_category/with_statistics', methods=['POST'])
def find_service_category_with_statistics():
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
        
        bk_biz_id = req_data.get('bk_biz_id', 0)
        
        if bk_biz_id == 0:
            return make_response(result=False, code=400, message="business id can't be empty")
        
        collection = get_mongo_collection('cc_ServiceCategory')
        
        # 查询条件：支持两种形式的 bk_biz_id 存在
        query = {
            "$or": [
                {"bk_biz_id": {"$in": [bk_biz_id, 0]}},
                {"metadata.label.bk_biz_id": {"$in": [str(bk_biz_id), "0"]}}
            ]
        }
        
        categories = list(collection.find(query).sort("name"))
        
        category_ids = [cat.get("id") for cat in categories]
        
        usage_map = {cid: 0 for cid in category_ids}
        
        service_template_collection = get_mongo_collection('cc_ServiceTemplate')
        template_filter = {
            "service_category_id": {"$in": category_ids},
            "$or": [
                {"bk_biz_id": bk_biz_id},
                {"metadata.label.bk_biz_id": str(bk_biz_id)}
            ]
        }
        service_templates = list(service_template_collection.find(template_filter))
        for tpl in service_templates:
            cid = tpl.get("service_category_id")
            if cid in usage_map:
                usage_map[cid] = usage_map.get(cid, 0) + 1
        
        module_collection = get_mongo_collection('cc_BaseModule')
        module_filter = {
            "service_category_id": {"$in": category_ids},
            "$or": [
                {"bk_biz_id": bk_biz_id},
                {"metadata.label.bk_biz_id": str(bk_biz_id)}
            ]
        }
        modules = list(module_collection.find(module_filter))
        for mod in modules:
            cid = mod.get("service_category_id")
            if cid in usage_map:
                usage_map[cid] = usage_map.get(cid, 0) + 1
        
        result = []
        for category in categories:
            clean_category = {k: v for k, v in category.items() if k != '_id'}
            # 确保返回的数据有 bk_biz_id 字段
            if 'bk_biz_id' not in clean_category:
                if 'metadata' in clean_category and 'label' in clean_category['metadata'] and 'bk_biz_id' in clean_category['metadata']['label']:
                    try:
                        clean_category['bk_biz_id'] = int(clean_category['metadata']['label']['bk_biz_id'])
                    except:
                        clean_category['bk_biz_id'] = 0
                else:
                    clean_category['bk_biz_id'] = 0
            
            usage_amount = usage_map.get(category.get("id"), 0)
            
            result.append({
                "usage_amount": usage_amount,
                "category": clean_category
            })
        
        return make_response(data={"info": result, "count": len(result)})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


# 服务分类查找API
@admin_bp.route('/api/v3/findmany/proc/service_category', methods=['POST'])
@admin_bp.route('/findmany/proc/service_category', methods=['POST'])
def find_service_category():
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
        
        bk_biz_id = req_data.get('bk_biz_id', 0)
        
        collection = get_mongo_collection('cc_ServiceCategory')
        
        # 查询条件：支持两种形式的 bk_biz_id 存在
        query = {
            "$or": [
                {"bk_biz_id": {"$in": [bk_biz_id, 0]}},
                {"metadata.label.bk_biz_id": {"$in": [str(bk_biz_id), "0"]}}
            ]
        }
        
        categories = list(collection.find(query).sort("name"))
        
        result = []
        for category in categories:
            item = {k: v for k, v in category.items() if k != '_id'}
            # 确保返回的数据有 bk_biz_id 字段
            if 'bk_biz_id' not in item:
                if 'metadata' in item and 'label' in item['metadata'] and 'bk_biz_id' in item['metadata']['label']:
                    try:
                        item['bk_biz_id'] = int(item['metadata']['label']['bk_biz_id'])
                    except:
                        item['bk_biz_id'] = 0
                else:
                    item['bk_biz_id'] = 0
            result.append(item)
        
        return make_response(data={"info": result, "count": len(result)})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


# 服务分类创建API
@admin_bp.route('/api/v3/create/proc/service_category', methods=['POST'])
@admin_bp.route('/create/proc/service_category', methods=['POST'])
def create_service_category():
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
        
        bk_biz_id = req_data.get('bk_biz_id', 0)
        name = req_data.get('name', '').strip()
        bk_parent_id = req_data.get('bk_parent_id', req_data.get('parent_id', 0))
        
        if not name:
            return make_response(result=False, code=400, message="name can't be empty")
        
        if len(name) > 128:
            return make_response(result=False, code=400, message="name too long, max length is 128")
        
        import re
        if not re.match(r'^[a-zA-Z0-9\u4e00-\u9fa5_\-]+$', name):
            return make_response(result=False, code=400, message="只能包含数字、字母、下划线、横线和中文")
        
        collection = get_mongo_collection('cc_ServiceCategory')
        
        biz_filter = []
        if bk_biz_id > 0:
            biz_filter = [bk_biz_id]
        
        parent_filter = bk_parent_id if bk_parent_id > 0 else {"$ne": 0} if bk_parent_id == 0 else bk_parent_id
        
        unique_filter = {
            "name": name,
            "bk_parent_id": parent_filter,
            "$or": [
                {"bk_biz_id": bk_biz_id},
                {"bk_biz_id": {"$in": biz_filter + [0]}}
            ]
        }
        
        if bk_parent_id == 0:
            unique_filter["bk_parent_id"] = 0
        else:
            unique_filter["bk_parent_id"] = {"$ne": 0}
        
        existing = list(collection.find(unique_filter))
        if len(existing) > 0:
            return make_response(result=False, code=1408003, message=f"service category name duplicated: {name}")
        
        # 全局原子自增 ID（对齐 Go NextSequence("cc_ServiceCategory")）
        new_id = next_sequence(conn, "cc_ServiceCategory")
        bk_root_id = new_id
        if bk_parent_id > 0:
            parent = collection.find_one({"id": bk_parent_id})
            if parent:
                bk_root_id = parent.get("bk_root_id", bk_parent_id)
            else:
                return make_response(result=False, code=400, message="parent category not found")
        
        new_category = {
            "id": new_id,
            "bk_biz_id": bk_biz_id,
            "bk_root_id": bk_root_id,
            "bk_parent_id": bk_parent_id,
            "name": name,
            "bk_supplier_account": "0",
            "is_built_in": False,
            "creator": "admin",
            "modifier": "admin",
            "create_time": "2024-01-01T00:00:00Z",
            "last_time": "2024-01-01T00:00:00Z",
            "metadata": {"label": {"bk_biz_id": str(bk_biz_id)}}
        }
        
        collection.insert_one(new_category)
        
        result = {k: v for k, v in new_category.items() if k != '_id'}
        
        return make_response(data=result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


# 服务分类更新API
@admin_bp.route('/api/v3/update/proc/service_category', methods=['PUT', 'POST'])
@admin_bp.route('/update/proc/service_category', methods=['PUT', 'POST'])
@admin_bp.route('/api/v3/update/proc/service_category/<int:category_id>', methods=['PUT', 'POST'])
@admin_bp.route('/update/proc/service_category/<int:category_id>', methods=['PUT', 'POST'])
def update_service_category(category_id=None):
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
        
        if category_id is None:
            category_id = req_data.get('id', 0)
        
        if not category_id:
            return make_response(result=False, code=400, message="id is required")
        
        collection = get_mongo_collection('cc_ServiceCategory')
        category = collection.find_one({"id": category_id})
        
        if not category:
            return make_response(result=False, code=404, message="service category not found")
        
        if category.get('is_built_in', False):
            return make_response(result=False, code=1202500, message="forbidden update built-in category")
        
        name = req_data.get('name', '').strip()
        if name:
            if len(name) > 128:
                return make_response(result=False, code=400, message="name too long, max length is 128")
            
            import re
            if not re.match(r'^[a-zA-Z0-9\u4e00-\u9fa5_\-]+$', name):
                return make_response(result=False, code=400, message="只能包含数字、字母、下划线、横线和中文")
            
            unique_filter = {
                "name": name,
                "bk_parent_id": category.get("bk_parent_id"),
                "_id": {"$ne": category_id},
                "$or": [
                    {"bk_biz_id": category.get("bk_biz_id")},
                    {"bk_biz_id": {"$in": [category.get("bk_biz_id"), 0]}}
                ]
            }
            
            existing = list(collection.find(unique_filter))
            if len(existing) > 0:
                return make_response(result=False, code=1408003, message=f"service category name duplicated: {name}")
            
            update_data = {
                "name": name,
                "modifier": "admin",
                "last_time": "2024-01-01T00:00:00Z"
            }
            
            collection.update_one({"id": category_id}, {"$set": update_data})
        
        updated_category = collection.find_one({"id": category_id})
        result = {k: v for k, v in updated_category.items() if k != '_id'}
        
        return make_response(data=result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


# 服务分类删除API
@admin_bp.route('/api/v3/delete/proc/service_category', methods=['DELETE', 'POST'])
@admin_bp.route('/delete/proc/service_category', methods=['DELETE', 'POST'])
@admin_bp.route('/api/v3/delete/proc/service_category/<int:category_id>', methods=['DELETE', 'POST'])
@admin_bp.route('/delete/proc/service_category/<int:category_id>', methods=['DELETE', 'POST'])
def delete_service_category(category_id=None):
    try:
        req_data = {}
        if request.is_json:
            req_data = request.get_json() or {}
        elif request.form:
            req_data = req_data.form.to_dict()
        elif request.data:
            try:
                import json
                req_data = json.loads(request.data)
            except:
                req_data = {}
        
        if category_id is None:
            category_id = req_data.get('id', 0)
        
        if not category_id:
            return make_response(result=False, code=400, message="id is required")
        
        collection = get_mongo_collection('cc_ServiceCategory')
        category = collection.find_one({"id": category_id})
        
        if not category:
            return make_response(result=False, code=404, message="service category not found")
        
        children_filter = {
            "bk_parent_id": category_id,
            "id": {"$ne": category_id}
        }
        children_count = collection.count_documents(children_filter)
        if children_count > 0:
            return make_response(result=False, code=1202500, message="forbidden delete category has children node")
        
        service_template_collection = get_mongo_collection('cc_ServiceTemplate')
        template_filter = {"service_category_id": category_id}
        template_count = service_template_collection.count_documents(template_filter)
        if template_count > 0:
            return make_response(result=False, code=1202500, message="forbidden delete category be referenced by service template")
        
        module_collection = get_mongo_collection('cc_BaseModule')
        module_filter = {"service_category_id": category_id}
        module_count = module_collection.count_documents(module_filter)
        if module_count > 0:
            return make_response(result=False, code=1202500, message="forbidden delete category be referenced by module")
        
        collection.delete_one({"id": category_id})
        
        return make_response(data={"deleted_count": 1})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


# 服务分类获取单个API
@admin_bp.route('/api/v3/find/proc/service_category/<int:category_id>', methods=['GET'])
@admin_bp.route('/find/proc/service_category/<int:category_id>', methods=['GET'])
def get_service_category(category_id):
    try:
        if not category_id:
            return make_response(result=False, code=400, message="id is required")
        
        collection = get_mongo_collection('cc_ServiceCategory')
        category = collection.find_one({"id": category_id})
        
        if not category:
            return make_response(result=False, code=404, message="service category not found")
        
        result = {k: v for k, v in category.items() if k != '_id'}
        
        return make_response(data=result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


# 服务分类获取默认API
@admin_bp.route('/api/v3/find/proc/default_service_category', methods=['GET'])
@admin_bp.route('/find/proc/default_service_category', methods=['GET'])
def get_default_service_category():
    try:
        collection = get_mongo_collection('cc_ServiceCategory')
        
        default_filter = {
            "name": "Default",
            "bk_parent_id": {"$ne": 0},
            "bk_biz_id": 0
        }
        category = collection.find_one(default_filter)
        
        if not category:
            return make_response(result=False, code=404, message="default service category not found")
        
        result = {k: v for k, v in category.items() if k != '_id'}
        
        return make_response(data=result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))
