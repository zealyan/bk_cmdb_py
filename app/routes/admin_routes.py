from flask import Blueprint, jsonify, request
from app.models.db import get_mongo_collection, get_db_connection

admin_bp = Blueprint('admin', __name__)


def make_response(result=True, code=0, message="success", data=None):
    return jsonify({
        "result": result,
        "code": code,
        "message": message,
        "data": data
    })


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
@admin_bp.route('/api/v3/findmany/biz_set/simplify', methods=['GET', 'POST'])
@admin_bp.route('/findmany/biz_set/simplify', methods=['GET', 'POST'])
def biz_set_reduced():
    try:
        return make_response(data={"info": DEFAULT_BIZ_SETS})
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
    try:
        return make_response(data={"info": []})
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


@admin_bp.route('/api/v3/usercustom/default/model', methods=['POST'])
def usercustom_default_model():
    try:
        return make_response(data={})
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


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
    try:
        return make_response(data={"info": []})
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


@admin_bp.route('/api/v3/search/usercustom', methods=['POST'])
@admin_bp.route('/search/usercustom', methods=['POST'])
def search_usercustom():
    try:
        return make_response(data={"info": []})
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
            # 使用INIT_DATA作为fallback
            from app.models.db import INIT_DATA, get_db_connection
            all_templates = INIT_DATA.get('cc_ServiceTemplate', [])
            
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
    try:
        req_data = request.get_json() or {}
        bk_obj_id = req_data.get('bk_obj_id', '')
        
        objects = []
        collection = get_mongo_collection('cc_ObjectBase')
        docs = collection.find({})
        # 简单的排序
        docs_sorted = sorted(docs, key=lambda x: x.get("id", 0))
        for doc in docs_sorted:
            objects.append({
                "id": doc.get("id"),
                "bk_classification_id": doc.get("bk_classification_id"),
                "bk_obj_id": doc.get("bk_obj_id"),
                "bk_obj_name": doc.get("bk_obj_name"),
                "bk_supplier_account": doc.get("bk_supplier_account"),
                "bk_obj_icon": doc.get("bk_obj_icon"),
                "is_built-in": doc.get("is_built_in"),
                "is_pre": doc.get("is_pre")
            })
        
        return make_response(data={"info": objects})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


# 主机搜索API
@admin_bp.route('/api/v3/hosts/search', methods=['POST'])
@admin_bp.route('/hosts/search', methods=['POST'])
def hosts_search():
    try:
        from app.models.db import get_db_connection
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        # 获取请求数据
        req_data = request.get_json() or {}
        page = req_data.get('page', {})
        start = page.get('start', 0)
        limit = page.get('limit', 20)
        sort = page.get('sort', 'bk_host_id')
        conditions = req_data.get('condition', [])
        
        # 查询条件处理
        query = {}
        host_ids_filter = None
        
        # 如果有条件，处理条件
        if conditions and len(conditions) > 0:
            # 查找资源池业务条件
            biz_condition = None
            for cond in conditions:
                if cond.get('bk_obj_id') == 'biz':
                    biz_condition = cond
                    break
            
            # 如果有资源池条件，并且是默认业务，查询所有主机
            if biz_condition:
                biz_filter = biz_condition.get('condition', [])
                for f in biz_filter:
                    if f.get('field') == 'default' and f.get('value') == 1:
                        # 查询资源池下的所有主机
                        host_relations = list(conn.cc_HostModuleRelation.find({"bk_biz_id": 1}))
                        host_ids_filter = [r.get('bk_host_id') for r in host_relations]
                        if host_ids_filter:
                            query = {"bk_host_id": {"$in": host_ids_filter}}
        
        # 查询主机数据
        collection = conn['cc_HostBase']
        cursor = collection.find(query)
        
        # 排序
        if sort:
            sort_dir = 1
            if sort.startswith('-'):
                sort_dir = -1
                sort = sort[1:]
            cursor = cursor.sort(sort, sort_dir)
        
        # 总数
        total_count = collection.count_documents(query)
        
        # 分页
        cursor = cursor.skip(start).limit(limit)
        
        # 处理结果，构建符合前端期望的数据结构
        result_info = []
        host_id_list = []
        
        for doc in cursor:
            doc.pop('_id', None)
            host_id = doc.get('bk_host_id')
            host_id_list.append(host_id)
            result_info.append({
                "host": doc,
                "topo": []
            })
        
        # 如果有主机，查询它们的主机-模块关系
        if host_id_list:
            # 查询主机-模块关系
            if host_ids_filter:
                host_relations = list(conn.cc_HostModuleRelation.find({
                    "bk_host_id": {"$in": host_id_list}
                }))
            else:
                host_relations = list(conn.cc_HostModuleRelation.find({
                    "bk_host_id": {"$in": host_id_list}
                }))
            
            # 获取所有涉及的模块ID
            module_ids = list(set([r.get('bk_module_id') for r in host_relations if r.get('bk_module_id')]))
            
            # 查询模块信息
            modules = {}
            if module_ids:
                module_docs = list(conn.cc_ModuleBase.find({"bk_module_id": {"$in": module_ids}}))
                for m in module_docs:
                    m.pop('_id', None)
                    modules[m.get('bk_module_id')] = m
            
            # 获取所有涉及的集群ID
            set_ids = list(set([r.get('bk_set_id') for r in host_relations if r.get('bk_set_id')]))
            
            # 查询集群信息
            sets = {}
            if set_ids:
                set_docs = list(conn.cc_SetBase.find({"bk_set_id": {"$in": set_ids}}))
                for s in set_docs:
                    s.pop('_id', None)
                    sets[s.get('bk_set_id')] = s
            
            # 构建主机-模块-集群映射
            host_set_module_map = {}
            for rel in host_relations:
                host_id = rel.get('bk_host_id')
                set_id = rel.get('bk_set_id')
                module_id = rel.get('bk_module_id')
                
                if host_id not in host_set_module_map:
                    host_set_module_map[host_id] = {}
                
                if set_id not in host_set_module_map[host_id]:
                    host_set_module_map[host_id][set_id] = []
                
                host_set_module_map[host_id][set_id].append(module_id)
            
            # 为每个主机填充topo信息
            for host_info in result_info:
                host_id = host_info['host'].get('bk_host_id')
                topo_map = host_set_module_map.get(host_id, {})
                
                topo_list = []
                for set_id, module_ids in topo_map.items():
                    set_info = sets.get(set_id, {})
                    module_list = []
                    for module_id in module_ids:
                        module_info = modules.get(module_id, {})
                        module_list.append(module_info)
                    
                    topo_list.append({
                        "bk_set_id": set_id,
                        "bk_set_name": set_info.get('bk_set_name', ''),
                        "module": module_list
                    })
                
                host_info['topo'] = topo_list
        
        return make_response(data={"info": result_info, "count": total_count})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@admin_bp.route('/api/v3/hosts/search/web', methods=['POST'])
@admin_bp.route('/hosts/search/web', methods=['POST'])
def hosts_search_web():
    try:
        from app.models.db import get_db_connection
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        # 获取请求数据
        req_data = request.get_json() or {}
        page = req_data.get('page', {})
        start = page.get('start', 0)
        limit = page.get('limit', 20)
        sort = page.get('sort', 'bk_host_id')
        conditions = req_data.get('condition', [])
        
        # 查询条件处理
        query = {}
        
        # 如果有条件，处理条件
        if conditions and len(conditions) > 0:
            # 查找资源池业务条件
            biz_condition = None
            for cond in conditions:
                if cond.get('bk_obj_id') == 'biz':
                    biz_condition = cond
                    break
            
            # 如果有资源池条件，并且是默认业务，查询所有主机
            if biz_condition:
                biz_filter = biz_condition.get('condition', [])
                for f in biz_filter:
                    if f.get('field') == 'default' and f.get('value') == 1:
                        # 查询资源池下的所有主机
                        host_relations = list(conn.cc_HostModuleRelation.find({"bk_biz_id": 1}))
                        host_ids = [r.get('bk_host_id') for r in host_relations]
                        if host_ids:
                            query = {"bk_host_id": {"$in": host_ids}}
        
        # 查询主机数据
        collection = conn['cc_HostBase']
        cursor = collection.find(query)
        
        # 排序
        if sort:
            sort_dir = 1
            if sort.startswith('-'):
                sort_dir = -1
                sort = sort[1:]
            cursor = cursor.sort(sort, sort_dir)
        
        # 总数
        total_count = collection.count_documents(query)
        
        # 分页
        cursor = cursor.skip(start).limit(limit)
        
        # 处理结果
        hosts = []
        for doc in cursor:
            doc.pop('_id', None)
            hosts.append(doc)
        
        return make_response(data={"info": hosts, "count": total_count})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


# 实例关联API
@admin_bp.route('/api/v3/find/instassociation', methods=['POST'])
@admin_bp.route('/find/instassociation', methods=['POST'])
def find_inst_association():
    try:
        return make_response(data={"info": []})
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


# 关联类型API
@admin_bp.route('/api/v3/find/associationtype', methods=['POST'])
@admin_bp.route('/find/associationtype', methods=['POST'])
def find_association_type():
    try:
        data = {
            "info": [
                {
                    "id": 1,
                    "bk_asst_id": "belong",
                    "bk_asst_name": "属于",
                    "bk_asst_type": "special",
                    "src_type": "module",
                    "dst_type": "set",
                    "direction": "src_to_dst"
                },
                {
                    "id": 2,
                    "bk_asst_id": "contain",
                    "bk_asst_name": "包含",
                    "bk_asst_type": "special",
                    "src_type": "set",
                    "dst_type": "module",
                    "direction": "src_to_dst"
                }
            ]
        }
        return make_response(data=data)
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


# 拓扑关联类型API
@admin_bp.route('/api/v3/find/topoassociationtype', methods=['POST'])
@admin_bp.route('/find/topoassociationtype', methods=['POST'])
def find_topo_association_type():
    try:
        data = {
            "info": [
                {
                    "id": 1,
                    "bk_asst_id": "topo",
                    "bk_asst_name": "拓扑关联",
                    "bk_asst_type": "topology",
                    "src_type": "biz",
                    "dst_type": "set",
                    "direction": "src_to_dst"
                }
            ]
        }
        return make_response(data=data)
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


# 保存用户自定义配置API
@admin_bp.route('/api/v3/usercustom', methods=['POST'])
@admin_bp.route('/usercustom', methods=['POST'])
def save_usercustom():
    try:
        return make_response(data={})
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


# 用户自定义默认配置API
@admin_bp.route('/api/v3/usercustom/default/search', methods=['POST'])
@admin_bp.route('/usercustom/default/search', methods=['POST'])
def usercustom_default_search():
    try:
        data = {
            "recently_models": [],
            "columns_config_business": [],
            "columns_config_host": [],
            "columns_config_set": [],
            "columns_config_module": []
        }
        return make_response(data=data)
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


# 模型拓扑API
@admin_bp.route('/api/v3/find/objecttopo/scope_type/global/scope_id/0', methods=['POST'])
@admin_bp.route('/find/objecttopo/scope_type/global/scope_id/0', methods=['POST'])
def find_object_topo():
    try:
        data = {
            "info": [
                {
                    "bk_obj_id": "biz",
                    "bk_inst_id": 0,
                    "bk_inst_name": "业务",
                    "children": [
                        {
                            "bk_obj_id": "set",
                            "bk_inst_id": 0,
                            "bk_inst_name": "集群",
                            "children": [
                                {
                                    "bk_obj_id": "module",
                                    "bk_inst_id": 0,
                                    "bk_inst_name": "模块",
                                    "children": []
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        return make_response(data=data)
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
        
        try:
            # 尝试从MongoDB查询服务分类
            collection = get_mongo_collection('cc_ServiceCategory')
            
            # 构建查询条件
            query = {}
            if bk_biz_id > 0:
                # 搜索metadata.label.bk_biz_id字段
                query["metadata.label.bk_biz_id"] = str(bk_biz_id)
            
            # 查询数据
            categories = list(collection.find(query))
            
            # 构建返回数据 - 按照前端期望的格式
            result = []
            for category in categories:
                # 移除_id字段
                clean_category = {}
                for key, value in category.items():
                    if key != '_id':
                        clean_category[key] = value
                
                result.append({
                    "usage_amount": 0,
                    "category": clean_category
                })
            
            return make_response(data={"info": result, "count": len(result)})
        except Exception as db_error:
            print(f"MongoDB查询失败，使用fallback数据: {db_error}")
            # 使用INIT_DATA作为fallback
            from app.models.db import INIT_DATA, get_db_connection
            all_categories = INIT_DATA.get('cc_ServiceCategory', [])
            
            # 过滤数据
            result = []
            for cat in all_categories:
                cat_bk_biz_id = cat.get('bk_biz_id')
                # 处理metadata中的bk_biz_id
                if not cat_bk_biz_id and 'metadata' in cat:
                    if 'label' in cat['metadata']:
                        cat_bk_biz_id = cat['metadata']['label'].get('bk_biz_id')
                # 转换为整数进行比较
                try:
                    if cat_bk_biz_id:
                        cat_bk_biz_id = int(cat_bk_biz_id)
                except:
                    cat_bk_biz_id = 0
                # 根据业务ID过滤
                if bk_biz_id == 0 or cat_bk_biz_id == bk_biz_id:
                    result.append({
                        "usage_amount": 0,
                        "category": cat
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
        
        try:
            # 尝试从MongoDB查询服务分类
            collection = get_mongo_collection('cc_ServiceCategory')
            
            # 构建查询条件
            query = {}
            if bk_biz_id > 0:
                # 搜索metadata.label.bk_biz_id字段
                query["metadata.label.bk_biz_id"] = str(bk_biz_id)
            
            # 查询数据
            categories = list(collection.find(query))
            
            # 移除_id字段，转换数据格式
            result = []
            for category in categories:
                item = {}
                for key, value in category.items():
                    if key != '_id':
                        item[key] = value
                result.append(item)
            
            return make_response(data={"info": result, "count": len(result)})
        except Exception as db_error:
            print(f"MongoDB查询失败，使用fallback数据: {db_error}")
            # 使用INIT_DATA作为fallback
            from app.models.db import INIT_DATA, get_db_connection
            all_categories = INIT_DATA.get('cc_ServiceCategory', [])
            
            # 过滤数据
            result = []
            for cat in all_categories:
                cat_bk_biz_id = cat.get('bk_biz_id')
                # 处理metadata中的bk_biz_id
                if not cat_bk_biz_id and 'metadata' in cat:
                    if 'label' in cat['metadata']:
                        cat_bk_biz_id = cat['metadata']['label'].get('bk_biz_id')
                # 转换为整数进行比较
                try:
                    if cat_bk_biz_id:
                        cat_bk_biz_id = int(cat_bk_biz_id)
                except:
                    cat_bk_biz_id = 0
                # 根据业务ID过滤
                if bk_biz_id == 0 or cat_bk_biz_id == bk_biz_id:
                    result.append(cat)
            
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
        name = req_data.get('name', '')
        parent_id = req_data.get('parent_id', 0)
        
        # 从MongoDB查询当前最大ID
        collection = get_mongo_collection('cc_ServiceCategory')
        max_id_doc = collection.find_one(sort=[("id", -1)])
        new_id = (max_id_doc.get("id", 0) + 1) if max_id_doc else 1
        
        # 创建新服务分类
        new_category = {
            "id": new_id,
            "bk_biz_id": bk_biz_id,
            "name": name,
            "parent_id": parent_id,
            "creator": "admin",
            "modifier": "admin",
            "create_time": "2024-01-01T00:00:00Z",
            "last_time": "2024-01-01T00:00:00Z"
        }
        
        # 插入数据库
        collection.insert_one(new_category)
        
        # 返回结果，移除_id字段
        result = {k: v for k, v in new_category.items() if k != '_id'}
        
        return make_response(data=result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


# 服务分类更新API
@admin_bp.route('/api/v3/update/proc/service_category', methods=['PUT', 'POST'])
@admin_bp.route('/update/proc/service_category', methods=['PUT', 'POST'])
def update_service_category():
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
        
        category_id = req_data.get('id', 0)
        if not category_id:
            return make_response(result=False, code=400, message="id is required")
        
        # 从MongoDB查询服务分类
        collection = get_mongo_collection('cc_ServiceCategory')
        category = collection.find_one({"id": category_id})
        
        if not category:
            return make_response(result=False, code=404, message="service category not found")
        
        # 准备更新数据
        update_data = {}
        if 'name' in req_data:
            update_data['name'] = req_data['name']
        if 'parent_id' in req_data:
            update_data['parent_id'] = req_data['parent_id']
        
        update_data['modifier'] = 'admin'
        update_data['last_time'] = '2024-01-01T00:00:00Z'
        
        # 更新数据
        collection.update_one({"id": category_id}, {"$set": update_data})
        
        # 获取更新后的数据
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
def delete_service_category():
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
        
        category_id = req_data.get('id', 0)
        
        # 从MongoDB删除服务分类
        collection = get_mongo_collection('cc_ServiceCategory')
        
        # 构建查询条件
        query = {}
        if category_id > 0:
            query["id"] = category_id
        
        # 执行删除
        result = collection.delete_many(query)
        
        return make_response(data={"deleted_count": result.deleted_count})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))
