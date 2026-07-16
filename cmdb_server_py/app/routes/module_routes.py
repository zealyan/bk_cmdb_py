"""
业务拓扑 - 模块（Module）路由模块
提供模块的 CRUD 操作接口
"""

from flask import Blueprint, jsonify, request
from app.models.db import db, get_db_connection, next_sequence
from datetime import datetime

module_bp = Blueprint('module', __name__)


def make_response(result=True, code=0, message="success", data=None, **kwargs):
    """统一响应格式（兼容 bk-cmdb 前端 bk_error_code 判定）"""
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
    response.update(kwargs)
    return jsonify(response)


@module_bp.route('/api/v3/module/<int:biz_id>/<int:set_id>', methods=['POST'])
@module_bp.route('/module/<int:biz_id>/<int:set_id>', methods=['POST'])
def create_module(biz_id, set_id):
    """
    创建模块
    POST /module/{bkBizId}/{bkSetId}
    
    请求体:
    {
        "bk_module_name": "模块名称",
        "bk_supplier_account": "0",
        "bk_service_category_id": 1
    }
    
    响应:
    {
        "result": true,
        "code": 0,
        "message": "success",
        "data": {"bk_module_id": 123}
    }
    """
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        req_data = request.get_json() or {}
        
        bk_module_name = req_data.get('bk_module_name')
        if not bk_module_name:
            return make_response(result=False, code=400, message="模块名称不能为空")
        
        bk_supplier_account = req_data.get('bk_supplier_account', '0')
        
        # 全局原子自增 ID（对齐 Go NextSequence("cc_ModuleBase")）
        new_id = next_sequence(conn, "cc_ModuleBase")
        
        module_doc = {
            "bk_module_id": new_id,
            "bk_module_name": bk_module_name,
            "bk_set_id": set_id,
            "bk_biz_id": biz_id,
            "bk_supplier_account": bk_supplier_account,
            "bk_parent_id": set_id,
            "bk_parent_obj": "set",
            "bk_service_category_id": req_data.get('bk_service_category_id', req_data.get('service_category_id', 1)),
            "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "bk_data_status": "enabled",
        }
        # 拓扑树实例标识字段（与 bk_module_id/bk_module_name 对齐）。
        # 业务拓扑“新建模块”走 handleCreateNode，会把响应直接合并进节点对象，
        # 必须返回 bk_inst_id/bk_inst_name 节点才能正确渲染。
        module_doc["bk_inst_id"] = new_id
        module_doc["bk_inst_name"] = bk_module_name

        conn.cc_ModuleBase.insert_one(module_doc)
        module_doc.pop("_id", None)

        return make_response(data=module_doc)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@module_bp.route('/api/v3/module/search/<supplier_account>/<int:biz_id>/<int:set_id>', methods=['POST'])
@module_bp.route('/module/search/<supplier_account>/<int:biz_id>/<int:set_id>', methods=['POST'])
def search_module(supplier_account, biz_id, set_id):
    """
    查询模块列表
    POST /module/search/{bkSupplierAccount}/{bkBizId}/{bkSetId}

    请求体:
    {
        "condition": {"bk_module_id": 7},
        "fields": [],
        "page": {"start": 0, "limit": 20}
    }

    响应（bk-cmdb 标准 {count, info} 信封）:
    {
        "result": true, "code": 0, "message": "success",
        "data": {
            "count": 1,
            "info": [{"bk_module_id": 7, "bk_module_name": "...", "bk_inst_id": 7, "bk_inst_name": "...", ...}]
        }
    }

    说明:
    前端 getModuleInstance / addModulesInSetTemplate 等统一读取 response.data.info
    （见 1077.*.js 的 n.info[0] 与 r.info.forEach），因此必须返回 {count, info} 信封；
    同时合并 condition 精确过滤，确保点击模块节点取到的是该模块而非列表首条。
    """
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        req_data = request.get_json() or {}

        # 基础过滤（set_id 取自 URL 路径）
        filter_query = {
            "bk_biz_id": biz_id,
            "bk_set_id": set_id,
            "bk_supplier_account": supplier_account,
            "bk_data_status": {"$ne": "disabled"},
        }

        # 合并请求体 condition（支持裸值 / {$eq: x} / 其它 Mongo 操作符）
        for k, v in (req_data.get("condition") or {}).items():
            if isinstance(v, dict) and "$eq" in v:
                filter_query[k] = v["$eq"]
            else:
                filter_query[k] = v

        page = req_data.get("page") or {}
        start = int(page.get("start", 0) or 0)
        limit = int(page.get("limit", 20) or 20)

        total = conn.cc_ModuleBase.count_documents(filter_query)
        modules = list(conn.cc_ModuleBase.find(filter_query).skip(start).limit(limit))

        info = []
        for m in modules:
            info.append({
                "bk_module_id": m.get("bk_module_id"),
                "bk_module_name": m.get("bk_module_name"),
                "bk_set_id": m.get("bk_set_id"),
                "bk_biz_id": m.get("bk_biz_id"),
                "bk_supplier_account": m.get("bk_supplier_account"),
                "bk_parent_id": m.get("bk_parent_id"),
                "bk_parent_obj": m.get("bk_parent_obj"),
                # 前端 FormServiceCategory / node-extra-info-service-template 读取服务分类时
                # 用的是 instance.service_category_id（见 form-service-category.vue setupValue），
                # 而数据库存储字段为 bk_service_category_id。两者需同时返回：bk_service_category_id
                # 用于内部透传，service_category_id 用于前端显示/编辑初始化。
                "bk_service_category_id": m.get("bk_service_category_id"),
                "service_category_id": m.get("bk_service_category_id"),
                # 拓扑树实例标识字段：与 bk_module_id/bk_module_name 对齐
                "bk_inst_id": m.get("bk_inst_id", m.get("bk_module_id")),
                "bk_inst_name": m.get("bk_inst_name", m.get("bk_module_name")),
                "create_time": m.get("create_time"),
                "last_time": m.get("last_time")
            })

        return make_response(data={"count": total, "info": info})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@module_bp.route('/api/v3/module/<int:biz_id>/<int:set_id>/<int:module_id>', methods=['PUT'])
@module_bp.route('/module/<int:biz_id>/<int:set_id>/<int:module_id>', methods=['PUT'])
def update_module(biz_id, set_id, module_id):
    """
    更新模块信息
    PUT /module/{bkBizId}/{bkSetId}/{bkModuleId}
    
    请求体:
    {
        "bk_module_name": "新名称",
        "bk_service_category_id": 2
    }
    
    响应:
    {
        "result": true,
        "code": 0,
        "message": "success",
        "data": {"bk_module_id": 123}
    }
    """
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        req_data = request.get_json() or {}
        
        update_fields = {
            "last_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 服务分类字段：前端编辑模块表单使用 service_category_id，
        # 存储字段为 bk_service_category_id（对齐 cc_ModuleBase）。两者都接受。
        svc_cat = req_data.get("bk_service_category_id", req_data.get("service_category_id"))
        if svc_cat is not None:
            update_fields["bk_service_category_id"] = svc_cat
        
        if "bk_module_name" in req_data and req_data["bk_module_name"] is not None:
            update_fields["bk_module_name"] = req_data["bk_module_name"]
        
        result = conn.cc_ModuleBase.update_one(
            {
                "bk_module_id": module_id,
                "bk_set_id": set_id,
                "bk_biz_id": biz_id
            },
            {"$set": update_fields}
        )
        
        if result.modified_count > 0 or result.matched_count > 0:
            return make_response(data={"bk_module_id": module_id})
        else:
            return make_response(result=False, code=404, message="模块不存在")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@module_bp.route('/api/v3/module/<int:biz_id>/<int:set_id>/<int:module_id>', methods=['DELETE'])
@module_bp.route('/module/<int:biz_id>/<int:set_id>/<int:module_id>', methods=['DELETE'])
def delete_module(biz_id, set_id, module_id):
    """
    删除模块
    DELETE /module/{bkBizId}/{bkSetId}/{bkModuleId}
    
    响应:
    {
        "result": true,
        "code": 0,
        "message": "success",
        "data": {"bk_module_id": 123}
    }
    """
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        result = conn.cc_ModuleBase.delete_one({
            "bk_module_id": module_id,
            "bk_set_id": set_id,
            "bk_biz_id": biz_id
        })
        
        if result.deleted_count > 0:
            return make_response(data={"bk_module_id": module_id})
        else:
            return make_response(result=False, code=404, message="模块不存在")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))
