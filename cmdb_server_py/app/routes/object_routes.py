from datetime import datetime
from flask import Blueprint, jsonify, request, g
from app.models.db import db, get_db_connection, get_mongo_collection

object_bp = Blueprint('object', __name__)

# 原项目权限错误码
PERMISSION_DENIED_CODE = 9900403


def make_response(result=True, code=0, message="success", data=None, **kwargs):
    response = {
        "result": result,
        "code": code,
        "message": message
    }
    if data is not None:
        response["data"] = data
    # 添加额外的字段到响应顶层
    response.update(kwargs)
    return jsonify(response)


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
    
    user_biz_list = list(conn.user_business.find(
        {'username': username},
        {'bk_biz_id': 1, '_id': 0}
    ))
    
    return [ub['bk_biz_id'] for ub in user_biz_list]


@object_bp.route('/api/v3/find/objectclassification', methods=['POST'])
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


@object_bp.route('/api/v3/find/objectassociation', methods=['POST'])
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


@object_bp.route('/api/v3/find/objectattgroup', methods=['POST'])
@object_bp.route('/find/objectattgroup', methods=['POST'])
def find_object_att_group():
    try:
        conn = get_db_connection()

        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")
        
        docs = conn.cc_ObjAttGroup.find({}, {'_id': 0})
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


@object_bp.route('/api/v3/find/objectattgroup/object/<obj_id>', methods=['POST'])
def find_object_att_group_by_obj(obj_id):
    try:
        groups = []
        collection = get_mongo_collection('cc_ObjAttGroup')
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


@object_bp.route('/api/v3/find/objectattr', methods=['POST'])
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

        # 从数据库读取属性数据
        all_attributes = []
        seen_prop_ids = set()  # 用于去重，避免重复的 bk_property_id
        
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
        
        if obj_ids:
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
        
        return make_response(data=all_attributes)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/api/v3/find/topomodelmainline', methods=['POST'])
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
        
        # 查询业务拓扑分类下的对象定义
        collection = get_mongo_collection('cc_ObjectBase')
        topo_objects = list(collection.find(
            {"bk_classification_id": "bk_biz_topo"},
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
                "is_built-in": obj.get("is_built_in", True),
                "default": 0,
                "bk_next_obj": next_obj_map.get(obj.get("bk_obj_id"))
            }
            topo_data.append(obj_node)
        
        return make_response(data=topo_data)
    except Exception as e:
        print(f"获取拓扑主线模型失败: {e}")
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/api/v3/find/classificationobject', methods=['POST'])
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
        collection_obj = get_mongo_collection('cc_ObjectBase')
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
                "is_built-in": doc.get("is_built_in"),
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


@object_bp.route('/api/v3/topoinstchild/object/<obj_id>/biz/<int:biz_id>/inst/<int:inst_id>', methods=['GET'])
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


@object_bp.route('/api/v3/find/topopath/biz/<int:biz_id>', methods=['POST'])
@object_bp.route('/find/topopath/biz/<int:biz_id>', methods=['POST'])
def find_topo_path(biz_id):
    """获取拓扑路径"""
    try:
        req_data = request.get_json() or {}
        # 返回从根节点到目标节点的路径
        return make_response(data=[])
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/api/v3/find/biz_set/topo_path', methods=['POST'])
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


@object_bp.route('/api/v3/topo/internal/<supplier_account>/<int:bk_biz_id>/with_statistics', methods=['GET'])
@object_bp.route('/topo/internal/<supplier_account>/<int:bk_biz_id>/with_statistics', methods=['GET'])
def topo_internal_with_statistics_new(supplier_account, bk_biz_id):
    """获取内部拓扑及统计信息（新参数格式）"""
    try:
        # 返回空闲池拓扑结构
        result = {
            "bk_set_id": 0,
            "bk_set_name": "空闲机池",
            "default": 1,
            "module": [
                {
                    "bk_module_id": 0,
                    "bk_module_name": "空闲机",
                    "default": 1,
                    "host_count": 0,
                    "service_instance_count": 0
                },
                {
                    "bk_module_id": 1,
                    "bk_module_name": "故障机",
                    "default": 2,
                    "host_count": 0,
                    "service_instance_count": 0
                }
            ]
        }
        return make_response(data=result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/api/v3/object/count', methods=['POST'])
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
                if obj_id == 'biz':
                    collection = get_mongo_collection('cc_ApplicationBase')
                    count = collection.count_documents({"bk_data_status": {"$ne": "disabled"}})
                elif obj_id == 'host':
                    collection = get_mongo_collection('cc_HostBase')
                    count = collection.count_documents({})
                elif obj_id == 'set':
                    collection = get_mongo_collection('cc_SetBase')
                    count = collection.count_documents({})
                elif obj_id == 'module':
                    collection = get_mongo_collection('cc_ModuleBase')
                    count = collection.count_documents({})
                elif obj_id == 'biz_set':
                    count = 0
                elif obj_id == 'cloud_area':
                    collection = get_mongo_collection('cc_PlatBase')
                    count = collection.count_documents({})
                elif obj_id == 'process':
                    count = 0
                elif obj_id in ['bk_switch', 'bk_router', 'bk_load_balance', 'bk_firewall']:
                    inst_collection_name = f"cc_InstBase_{obj_id}"
                    collection = get_mongo_collection(inst_collection_name)
                    count = collection.count_documents({})
                else:
                    count = 0
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


@object_bp.route('/api/v3/search/instances/object/<obj_id>', methods=['POST'])
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
            if obj_id == 'biz':
                collection_name = 'cc_ApplicationBase'
                query = conditions if conditions else {"bk_data_status": {"$ne": "disabled"}}
            elif obj_id == 'set':
                collection_name = 'cc_SetBase'
                query = conditions if conditions else {}
            elif obj_id == 'module':
                collection_name = 'cc_ModuleBase'
                query = conditions if conditions else {}
            elif obj_id == 'host':
                collection_name = 'cc_HostBase'
                query = conditions if conditions else {}
            elif obj_id == 'cloud_area':
                collection_name = 'cc_PlatBase'
                query = conditions if conditions else {}
            else:
                collection_name = f"cc_InstBase_{obj_id}"
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


@object_bp.route('/api/v3/count/instances/object/<obj_id>', methods=['POST'])
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
            if obj_id == 'biz':
                collection = get_mongo_collection('cc_ApplicationBase')
                query = {}
                if conditions:
                    query = conditions
                else:
                    query = {"bk_data_status": {"$ne": "disabled"}}
                count = collection.count_documents(query)
            elif obj_id == 'set':
                collection = get_mongo_collection('cc_SetBase')
                count = collection.count_documents(conditions if conditions else {})
            elif obj_id == 'module':
                collection = get_mongo_collection('cc_ModuleBase')
                count = collection.count_documents(conditions if conditions else {})
            elif obj_id == 'host':
                collection = get_mongo_collection('cc_HostBase')
                count = collection.count_documents(conditions if conditions else {})
            elif obj_id == 'biz_set':
                count = 0
            elif obj_id == 'cloud_area':
                collection = get_mongo_collection('cc_PlatBase')
                count = collection.count_documents(conditions if conditions else {})
            elif obj_id == 'process':
                count = 0
            elif obj_id in ['bk_switch', 'bk_router', 'bk_load_balance', 'bk_firewall']:
                # 网络设备实例数量统计
                # 查找对应的实例集合
                inst_collection_name = f"cc_InstBase_{obj_id}"
                collection = get_mongo_collection(inst_collection_name)
                count = collection.count_documents(conditions if conditions else {})
            else:
                count = 0
        except Exception as e:
            print(f"统计 {obj_id} 实例数量失败: {e}")
            count = 0
        
        return make_response(data={"count": count})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/api/v3/find/topoinst_with_statistics/biz/<int:bk_biz_id>', methods=['POST'])
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
        
        # 查询主机-模块关系
        host_relations = list(conn.cc_HostModuleRelation.find({"bk_biz_id": business.get("bk_biz_id")}))
        
        # 查询该业务下的所有集群
        sets = list(conn.cc_SetBase.find({"bk_biz_id": business.get("bk_biz_id"), "bk_data_status": {"$ne": "disabled"}}))
        
        # 查询该业务下的所有模块
        modules = list(conn.cc_ModuleBase.find({"bk_biz_id": business.get("bk_biz_id"), "bk_data_status": {"$ne": "disabled"}}))
        
        # 构建集群节点
        set_nodes = []
        total_host_count = 0
        
        for s in sets:
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
            total_host_count += set_host_count
            set_node = {
                "bk_obj_id": "set",
                "bk_obj_name": "集群",
                "bk_inst_id": s.get("bk_set_id"),
                "bk_inst_name": s.get("bk_set_name"),
                "default": 0,
                "child": module_nodes,
                "host_count": set_host_count,
                "service_instance_count": 0
            }
            set_nodes.append(set_node)
        
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







@object_bp.route('/api/v3/find/topoinstnode/host_serviceinst_count/<int:biz_id>', methods=['POST'])
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
        host_relations = list(conn.cc_HostModuleRelation.find({"bk_biz_id": biz_id}))
        
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


@object_bp.route('/api/v3/create/instance/object/<obj_id>', methods=['POST'])
@object_bp.route('/create/instance/object/<obj_id>', methods=['POST'])
def create_instance(obj_id):
    """创建对象实例"""
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
        
        # 获取实例数据
        instance_data = req_data
        
        # 过滤掉None值，但保留空字符串和0
        instance_data = {k: v for k, v in instance_data.items() if v is not None}
        
        # 获取下一个实例ID
        collection_name = f"cc_InstBase_{obj_id}"
        collection = get_mongo_collection(collection_name)
        
        # 获取当前最大ID
        max_doc = collection.find_one(sort=[("bk_inst_id", -1)])
        next_id = 1 if max_doc is None else max_doc.get("bk_inst_id", 0) + 1
        
        # 设置实例ID和基础字段
        instance_data["bk_inst_id"] = next_id
        instance_data.setdefault("bk_supplier_account", "0")
        instance_data.setdefault("bk_data_status", "active")
        instance_data.setdefault("create_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        instance_data.setdefault("last_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        # 插入数据库
        result = collection.insert_one(instance_data)
        
        if result.inserted_id:
            return make_response(data={
                "bk_inst_id": next_id,
                "id": next_id
            })
        else:
            return make_response(result=False, code=500, message="创建实例失败")
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))




@object_bp.route('/api/v3/find/topoinst/biz/<int:bk_biz_id>', methods=['POST'])
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


@object_bp.route('/api/v3/findmany/resource/directory', methods=['POST'])
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
        host_relations = list(conn.cc_HostModuleRelation.find({"bk_biz_id": biz_id}))
        
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


@object_bp.route('/api/v3/find/module/host/relation/<int:bk_biz_id>', methods=['POST'])
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
            host_relations = list(conn.cc_HostModuleRelation.find({
                "bk_biz_id": bk_biz_id,
                "bk_module_id": {"$in": module_ids}
            }))
        else:
            host_relations = list(conn.cc_HostModuleRelation.find({
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


@object_bp.route('/api/v3/usercustom/user/search', methods=['POST'])
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


@object_bp.route('/api/v3/usercustom/default/model', methods=['POST'])
@object_bp.route('/usercustom/default/model', methods=['POST'])
def usercustom_default_model():
    """用户自定义默认模型"""
    try:
        return make_response(data={})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@object_bp.route('/api/v3/find/topoinst/biz_set/<int:biz_set_id>', methods=['POST'])
@object_bp.route('/find/topoinst/biz_set/<int:biz_set_id>', methods=['POST'])
def find_biz_set_topo_inst(biz_set_id):
    """获取业务集拓扑实例"""
    try:
        return make_response(data=[])
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))
