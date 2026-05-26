from flask import Blueprint, jsonify, request
from app.models.db import db, get_db_connection, get_mongo_collection

object_bp = Blueprint('object', __name__)


def make_response(result=True, code=0, message="success", data=None):
    return jsonify({
        "result": result,
        "code": code,
        "message": message,
        "data": data
    })


@object_bp.route('/api/v3/find/objectclassification', methods=['POST'])
@object_bp.route('/find/objectclassification', methods=['POST'])
def find_object_classification():
    try:
        collection = get_mongo_collection('cc_ObjClassification')
        classifications = list(collection.find({}, {'_id': 0}))
        return make_response(data={"info": classifications})
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
        return make_response(data={"info": associations})
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
        
        groups = list(conn.cc_ObjAttGroup.find({}, {'_id': 0}))
        return make_response(data={"info": groups})
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
                all_attributes.append(attr)
        
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
        return make_response(data={"info": class_data})
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
            collection_name = f"cc_InstBase_{obj_id}"
            collection = get_mongo_collection(collection_name)
            
            query = {}
            if conditions:
                query = conditions
            
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

        # 查询业务数据
        business = conn.cc_ApplicationBase.find_one({"bk_biz_id": bk_biz_id})
        if not business:
            # 如果没有找到指定业务，返回第一个启用的业务
            business = conn.cc_ApplicationBase.find_one({"bk_data_status": {"$ne": "disabled"}})
        
        if not business:
            # 如果没有任何业务，返回空结构
            return make_response(data=[])
        
        # 查询该业务下的所有集群
        sets = list(conn.cc_SetBase.find({"bk_biz_id": business.get("bk_biz_id"), "bk_data_status": {"$ne": "disabled"}}))
        
        # 查询该业务下的所有模块
        modules = list(conn.cc_ModuleBase.find({"bk_biz_id": business.get("bk_biz_id"), "bk_data_status": {"$ne": "disabled"}}))
        
        # 构建集群节点
        set_nodes = []
        for s in sets:
            set_id = s.get("bk_set_id")
            # 查找该集群下的所有模块
            set_modules = [m for m in modules if m.get("bk_set_id") == set_id]
            
            # 构建模块节点
            module_nodes = []
            for m in set_modules:
                module_node = {
                    "bk_obj_id": "module",
                    "bk_obj_name": "模块",
                    "bk_inst_id": m.get("bk_module_id"),
                    "bk_inst_name": m.get("bk_module_name"),
                    "default": 0,
                    "child": [],
                    "host_count": 0,
                    "service_instance_count": 0
                }
                module_nodes.append(module_node)
            
            # 构建集群节点
            set_node = {
                "bk_obj_id": "set",
                "bk_obj_name": "集群",
                "bk_inst_id": s.get("bk_set_id"),
                "bk_inst_name": s.get("bk_set_name"),
                "default": 0,
                "child": module_nodes,
                "host_count": 0,
                "service_instance_count": 0
            }
            set_nodes.append(set_node)
        
        # 构建业务拓扑结构
        biz_node = {
            "bk_obj_id": "biz",
            "bk_obj_name": "业务",
            "bk_inst_id": business.get("bk_biz_id"),
            "bk_inst_name": business.get("bk_biz_name"),
            "default": 0,
            "child": set_nodes,
            "host_count": 0,
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
        
        # 为每个节点返回统计数据（当前返回默认值）
        result = []
        for node in conditions:
            result.append({
                "bk_obj_id": node.get('bk_obj_id'),
                "bk_inst_id": node.get('bk_inst_id'),
                "host_count": 0,
                "service_instance_count": 0
            })
        
        return make_response(data=result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))
