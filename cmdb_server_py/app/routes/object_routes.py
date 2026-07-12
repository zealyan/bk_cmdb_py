import json
from datetime import datetime
from flask import Blueprint, jsonify, request, g
from app.models.db import db, get_db_connection, get_mongo_collection, next_sequence
from app.config import Config

object_bp = Blueprint('object', __name__)

# 原项目权限错误码
PERMISSION_DENIED_CODE = 9900403


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
    """对齐 bk-cmdb：实例搜索/拓扑响应始终附带 bk_inst_id（真实主键字段的别名）。

    前端编辑实例时按 `instState.bk_inst_id` 拼出
    PUT /update/instance/object/{obj}/inst/{id} 的 URL。host 的真实主键是 bk_host_id、
    通用对象是 bk_inst_id，若响应里不补 bk_inst_id，前端拿到 undefined → URL 变成
    inst/undefined → 更新 404。真实 bk-cmdb 的搜索层会补这个字段，这里对齐。
    """
    if not doc:
        return doc
    id_field = get_inst_id_field(obj_id)
    if "bk_inst_id" not in doc and id_field in doc:
        doc["bk_inst_id"] = doc[id_field]
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


@object_bp.route('/find/objectassociation', methods=['POST'])
def find_object_association():
    try:
        conn = get_db_connection()

        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")
        
        associations = [
            {
                "bk_asst_obj_id": "set",
                "bk_obj_id": "biz",
                "bk_next_obj": "set",
                "bk_supplier_account": "0",
                "is_built_in": True,
                "is_pre": True
            },
            {
                "bk_asst_obj_id": "module",
                "bk_obj_id": "set",
                "bk_next_obj": "module",
                "bk_supplier_account": "0",
                "is_built_in": True,
                "is_pre": True
            },
            {
                "bk_asst_obj_id": "host",
                "bk_obj_id": "module",
                "bk_next_obj": "host",
                "bk_supplier_account": "0",
                "is_built_in": True,
                "is_pre": True
            },
            {
                "bk_asst_obj_id": "process",
                "bk_obj_id": "host",
                "bk_next_obj": "process",
                "bk_supplier_account": "0",
                "is_built_in": True,
                "is_pre": True
            }
        ]
        return make_response(data=associations)
    except Exception as e:
        import traceback
        traceback.print_exc()
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
            "ispre": doc.get("is_pre", False),
            "isrequired": doc.get("is_required", False),
            "isreadonly": doc.get("isreadonly", doc.get("is_readonly", False)),
            "isonly": doc.get("is_only", False),
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
    """获取拓扑主线模型"""
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
        
        # 查询业务拓扑分类下的所有对象模型（业务、集群、模块）
        topo_data = []
        
        # 查询业务拓扑主线对象定义。
        # 注意：bk-cmdb 的主线对象由 bk_obj_id 决定（而非按 bk_classification_id 过滤），
        # host/process 等内置对象的分类在真实 bk-cmdb 中归属 bk_host_manage，
        # 但仍必须出现在业务拓扑主线中。
        # 修复：对象模型定义由 initdb 写入 cc_ObjDes（共 11 个），cc_ObjectBase（无 supplier 后缀）
        # 是空集合；之前误读 cc_ObjectBase 导致业务拓扑主线返回空列表。
        collection = get_mongo_collection('cc_ObjDes')
        mainline_obj_ids = ['biz', 'set', 'module', 'host', 'process', 'bk_biz_set_obj']
        topo_objects = list(collection.find(
            {"bk_obj_id": {"$in": mainline_obj_ids}},
            {'_id': 0}
        ))
        
        # 定义对象的下一级关系
        next_obj_map = {
            "biz": "set",
            "set": "module",
            "module": "host"
        }
        
        for obj in topo_objects:
            obj_node = {
                "bk_obj_id": obj.get("bk_obj_id"),
                "bk_obj_name": obj.get("bk_obj_name"),
                "bk_supplier_account": bk_supplier_account,
                "is_built-in": obj.get("ispre", True),
                "default": 0,
                "bk_next_obj": next_obj_map.get(obj.get("bk_obj_id"))
            }
            topo_data.append(obj_node)
        
        return make_response(data=topo_data)
    except Exception as e:
        print(f"获取拓扑主线模型失败: {e}")
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
                "is_pre": doc.get("is_pre")
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

        # 空闲机池模块的 default 值映射（按名称兜底，因部分数据缺失 bk_default 字段）
        idle_module_default = {"空闲机": 1, "故障机": 2, "待回收": 3}

        # 定位空闲机池集群：优先 bk_default==1，其次按名称“空闲机池”
        idle_set = conn.cc_SetBase.find_one({
            "bk_biz_id": bk_biz_id,
            "bk_data_status": {"$ne": "disabled"},
            "$or": [{"bk_default": 1}, {"bk_set_name": "空闲机池"}]
        })
        if not idle_set:
            idle_set = conn.cc_SetBase.find_one({
                "bk_biz_id": bk_biz_id,
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
        host_relations = list(conn.cc_ModuleHostConfig.find({
            "bk_biz_id": bk_biz_id, "bk_set_id": idle_set_id
        }))

        modules = list(conn.cc_ModuleBase.find({
            "bk_biz_id": bk_biz_id,
            "bk_set_id": idle_set_id,
            "bk_data_status": {"$ne": "disabled"}
        }))

        module_list = []
        for m in modules:
            mid = m.get("bk_module_id")
            mname = m.get("bk_module_name", "")
            default = m.get("bk_default")
            if default is None:
                default = idle_module_default.get(mname, 0)
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
        conditions = req_data.get('conditions', {})
        
        start = page.get('start', 0)
        limit = page.get('limit', 20)
        sort = page.get('sort', 'bk_inst_id')
        
        try:
            collection_name = get_inst_collection_name(obj_id)
            query = conditions if conditions else {}
            
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
        
        conditions = req_data.get('conditions', {})
        
        count = 0
        try:
            collection_name = get_inst_collection_name(obj_id)
            query = conditions if conditions else {}
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
        
        # 查询主机-模块关系（含空闲机池，用于业务节点总数统计）
        host_relations = list(conn.cc_ModuleHostConfig.find({"bk_biz_id": business.get("bk_biz_id")}))

        # 查询该业务下的所有集群
        sets = list(conn.cc_SetBase.find({"bk_biz_id": business.get("bk_biz_id"), "bk_data_status": {"$ne": "disabled"}}))

        # 查询该业务下的所有模块
        modules = list(conn.cc_ModuleBase.find({"bk_biz_id": business.get("bk_biz_id"), "bk_data_status": {"$ne": "disabled"}}))

        # 判断是否为空闲机池：bk_default==1 或名为“空闲机池”
        # 业务拓扑接口须排除空闲机池，否则会与 /topo/internal 接口返回并前置的空闲机池重复。
        def _is_idle_pool(s):
            return s.get("bk_default") == 1 or s.get("bk_set_name") == "空闲机池"

        # 构建集群节点（排除空闲机池）
        set_nodes = []
        for s in sets:
            if _is_idle_pool(s):
                continue
            set_id = s.get("bk_set_id")
            # 查找该集群下的所有模块
            set_modules = [m for m in modules if m.get("bk_set_id") == set_id]

            # 构建模块节点
            module_nodes = []
            set_host_count = 0
            for m in set_modules:
                module_id = m.get("bk_module_id")
                # 统计该模块下的主机数
                module_hosts = [r for r in host_relations if r.get("bk_module_id") == module_id]
                host_count = len(module_hosts)
                set_host_count += host_count

                module_node = {
                    "bk_obj_id": "module",
                    "bk_obj_name": "模块",
                    "bk_inst_id": m.get("bk_module_id"),
                    "bk_inst_name": m.get("bk_module_name"),
                    "default": m.get("bk_default", 0),
                    "child": [],
                    "host_count": host_count,
                    "service_instance_count": 0
                }
                module_nodes.append(module_node)

            # 构建集群节点
            set_node = {
                "bk_obj_id": "set",
                "bk_obj_name": "集群",
                "bk_inst_id": s.get("bk_set_id"),
                "bk_inst_name": s.get("bk_set_name"),
                "default": s.get("bk_default", 0),
                "child": module_nodes,
                "host_count": set_host_count,
                "service_instance_count": 0
            }
            set_nodes.append(set_node)

        # 业务节点主机总数 = 该业务下全部主机（含空闲机池），符合 bk-cmdb 语义
        total_host_count = len(host_relations)

        # 构建业务拓扑结构
        biz_node = {
            "bk_obj_id": "biz",
            "bk_obj_name": "业务",
            "bk_inst_id": business.get("bk_biz_id"),
            "bk_inst_name": business.get("bk_biz_name"),
            "default": business.get("bk_default", 0),
            "child": set_nodes,
            "host_count": total_host_count,
            "service_instance_count": 0
        }

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
        
        # 查询主机-模块关系
        host_relations = list(conn.cc_ModuleHostConfig.find({"bk_biz_id": biz_id}))
        
        # 为每个节点返回统计数据
        result = []
        for node in conditions:
            bk_obj_id = node.get('bk_obj_id')
            bk_inst_id = node.get('bk_inst_id')
            
            host_count = 0
            if bk_obj_id == "module":
                # 统计模块下的主机
                host_count = len([r for r in host_relations if r.get("bk_module_id") == bk_inst_id])
            elif bk_obj_id == "set":
                # 统计集群下的主机
                host_count = len([r for r in host_relations if r.get("bk_set_id") == bk_inst_id])
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


@object_bp.route('/create/instance/object/<obj_id>', methods=['POST'])
def create_instance(obj_id):
    """创建对象实例"""
    try:
        req_data = _parse_body()

        # 后端必填校验（兜底，前端 v-validate 已拦截；此处防止绕过）：
        # 仅校验 cc_ObjAttDes 中 is_required=true 且非「后端自动生成 ID 字段」的属性。
        id_field = get_inst_id_field(obj_id)
        auto_id_props = {
            "bk_biz_id", "bk_set_id", "bk_module_id", "bk_inst_id",
            "bk_host_id", "bk_process_id", "bk_cloud_id", "bk_biz_set_id",
        }
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
            val = req_data.get(pid)
            if val is None or (isinstance(val, str) and val.strip() == ""):
                missing.append(a.get("bk_property_name") or pid)
        if missing:
            return make_response(
                result=False, code=500,
                message="以下必填项不能为空: " + "、".join(missing),
            )

        # 获取实例数据，过滤掉 None 值但保留空字符串和 0
        instance_data = {k: v for k, v in req_data.items() if v is not None}

        collection_name = get_inst_collection_name(obj_id)
        collection = get_mongo_collection(collection_name)

        # 全局原子自增 ID（对齐 Go NextSequence, redirectTable 自动处理分表→主表）
        conn = get_db_connection()
        next_id = next_sequence(conn, collection_name)

        # 用真实主键字段写入（host->bk_host_id，通用对象->bk_inst_id …）
        instance_data[id_field] = next_id
        instance_data.setdefault("bk_supplier_account", "0")
        instance_data.setdefault("bk_data_status", "active")
        instance_data.setdefault("create_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        instance_data.setdefault("last_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        result = collection.insert_one(instance_data)

        if result.inserted_id:
            return make_response(data={
                "bk_inst_id": next_id,
                id_field: next_id,
                "id": next_id,
            })
        else:
            return make_response(result=False, code=500, message="创建实例失败")

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

        # 构建拓扑结构
        topo_result = []
        
        # 添加业务节点
        biz_node = {
            "bk_inst_id": biz_id,
            "bk_inst_name": biz_name,
            "bk_obj_id": "biz",
            "bk_obj_name": "业务",
            "children": []
        }
        
        # 查询该业务下的所有集群
        sets = list(conn.cc_SetBase.find({
            "bk_biz_id": biz_id,
            "bk_data_status": {"$ne": "disabled"}
        }).sort("bk_set_name", 1))
        
        for s in sets:
            set_node = {
                "bk_inst_id": s.get("bk_set_id"),
                "bk_inst_name": s.get("bk_set_name", ""),
                "bk_obj_id": "set",
                "bk_obj_name": "集群",
                "children": []
            }
            
            # 查询该集群下的所有模块
            modules = list(conn.cc_ModuleBase.find({
                "bk_set_id": s.get("bk_set_id"),
                "bk_biz_id": biz_id,
                "bk_data_status": {"$ne": "disabled"}
            }).sort("bk_module_name", 1))
            
            for m in modules:
                module_node = {
                    "bk_inst_id": m.get("bk_module_id"),
                    "bk_inst_name": m.get("bk_module_name", ""),
                    "bk_obj_id": "module",
                    "bk_obj_name": "模块",
                    "children": []
                }
                set_node["children"].append(module_node)
            
            biz_node["children"].append(set_node)
        
        topo_result.append(biz_node)
        
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
        resource_pool_biz = conn.cc_ApplicationBase.find_one({"bk_default": 1})
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
