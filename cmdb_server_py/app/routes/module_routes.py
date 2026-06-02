"""
业务拓扑 - 模块（Module）路由模块
提供模块的 CRUD 操作接口
"""

from flask import Blueprint, jsonify, request
from app.models.db import db, get_db_connection
from datetime import datetime

module_bp = Blueprint('module', __name__)


def make_response(result=True, code=0, message="success", data=None):
    """统一响应格式"""
    return jsonify({
        "result": result,
        "code": code,
        "message": message,
        "data": data
    })


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
        
        max_id_doc = conn.cc_ModuleBase.find_one(sort=[("bk_module_id", -1)])
        new_id = (max_id_doc.get("bk_module_id", 0) + 1) if max_id_doc else 1
        
        module_doc = {
            "bk_module_id": new_id,
            "bk_module_name": bk_module_name,
            "bk_set_id": set_id,
            "bk_biz_id": biz_id,
            "bk_supplier_account": bk_supplier_account,
            "bk_parent_id": set_id,
            "bk_parent_obj": "set",
            "bk_service_category_id": req_data.get('bk_service_category_id', 1),
            "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "bk_data_status": "enabled"
        }
        
        conn.cc_ModuleBase.insert_one(module_doc)
        
        return make_response(data={"bk_module_id": new_id})
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
        "condition": {},
        "fields": [],
        "page": {"start": 0, "limit": 20}
    }
    
    响应:
    {
        "result": true,
        "code": 0,
        "message": "success",
        "data": [
            {
                "bk_module_id": 1,
                "bk_module_name": "模块名称",
                "bk_set_id": 1,
                "bk_biz_id": 2,
                ...
            }
        ]
    }
    """
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        req_data = request.get_json() or {}
        
        filter_query = {
            "bk_biz_id": biz_id,
            "bk_set_id": set_id,
            "bk_supplier_account": supplier_account,
            "bk_data_status": {"$ne": "disabled"}
        }
        
        modules = list(conn.cc_ModuleBase.find(filter_query))
        
        result = []
        for m in modules:
            result.append({
                "bk_module_id": m.get("bk_module_id"),
                "bk_module_name": m.get("bk_module_name"),
                "bk_set_id": m.get("bk_set_id"),
                "bk_biz_id": m.get("bk_biz_id"),
                "bk_supplier_account": m.get("bk_supplier_account"),
                "bk_parent_id": m.get("bk_parent_id"),
                "bk_parent_obj": m.get("bk_parent_obj"),
                "bk_service_category_id": m.get("bk_service_category_id"),
                "create_time": m.get("create_time"),
                "last_time": m.get("last_time")
            })
        
        return make_response(data=result)
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
        
        for field in ["bk_module_name", "bk_service_category_id"]:
            if field in req_data and req_data[field] is not None:
                update_fields[field] = req_data[field]
        
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
