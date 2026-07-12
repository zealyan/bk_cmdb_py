"""
业务拓扑 - 集群（Set）路由模块
提供集群的 CRUD 操作接口
"""

from flask import Blueprint, jsonify, request
from app.models.db import db, get_db_connection, next_sequence
from datetime import datetime

set_bp = Blueprint('set', __name__)


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


@set_bp.route('/api/v3/set/<int:biz_id>', methods=['POST'])
@set_bp.route('/set/<int:biz_id>', methods=['POST'])
def create_set(biz_id):
    """
    创建集群
    POST /set/{bkBizId}
    
    请求体:
    {
        "bk_set_name": "集群名称",
        "bk_supplier_account": "0",
        "description": "描述",
        "bk_service_status": "1",
        "bk_set_env": "3"
    }
    
    响应:
    {
        "result": true,
        "code": 0,
        "message": "success",
        "data": {"bk_set_id": 123}
    }
    """
    try:
        req_data = request.get_json() or {}
        
        bk_set_name = req_data.get('bk_set_name')
        if not bk_set_name:
            return make_response(result=False, code=400, message="集群名称不能为空")
        
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")
        
        bk_supplier_account = req_data.get('bk_supplier_account', '0')
        
        # 全局原子自增 ID（对齐 Go NextSequence("cc_SetBase")）
        new_id = next_sequence(conn, "cc_SetBase")
        
        set_doc = {
            "bk_set_id": new_id,
            "bk_set_name": bk_set_name,
            "bk_biz_id": biz_id,
            "bk_supplier_account": bk_supplier_account,
            "bk_parent_id": 0,
            "bk_parent_obj": "biz",
            "description": req_data.get('description', ''),
            "bk_service_status": req_data.get('bk_service_status', '1'),
            "bk_set_env": req_data.get('bk_set_env', '3'),
            "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "bk_data_status": "enabled"
        }
        
        conn.cc_SetBase.insert_one(set_doc)
        
        return make_response(data={"bk_set_id": new_id})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@set_bp.route('/api/v3/set/<int:biz_id>/batch', methods=['POST'])
@set_bp.route('/set/<int:biz_id>/batch', methods=['POST'])
def create_sets_batch(biz_id):
    """
    批量创建集群
    POST /set/{bkBizId}/batch
    
    请求体:
    {
        "sets": [
            {"bk_set_name": "集群1", "description": "..."},
            {"bk_set_name": "集群2", "description": "..."}
        ]
    }
    
    响应:
    {
        "result": true,
        "code": 0,
        "message": "success",
        "data": [
            {"bk_set_id": 123, "bk_set_name": "集群1"},
            {"bk_set_id": 124, "bk_set_name": "集群2"}
        ]
    }
    """
    try:
        req_data = request.get_json() or {}
        sets_data = req_data.get('sets', [])
        
        if not sets_data:
            return make_response(result=False, code=400, message="sets 列表不能为空")
        
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")
        
        created_sets = []
        
        for set_data in sets_data:
            bk_set_name = set_data.get('bk_set_name')
            if not bk_set_name:
                continue
            
            bk_supplier_account = set_data.get('bk_supplier_account', '0')
            
            # 全局原子自增 ID（对齐 Go NextSequence("cc_SetBase")）
            new_id = next_sequence(conn, "cc_SetBase")
            
            set_doc = {
                "bk_set_id": new_id,
                "bk_set_name": bk_set_name,
                "bk_biz_id": biz_id,
                "bk_supplier_account": bk_supplier_account,
                "bk_parent_id": 0,
                "bk_parent_obj": "biz",
                "description": set_data.get('description', ''),
                "bk_service_status": set_data.get('bk_service_status', '1'),
                "bk_set_env": set_data.get('bk_set_env', '3'),
                "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "bk_data_status": "enabled"
            }
            
            conn.cc_SetBase.insert_one(set_doc)
            created_sets.append({"bk_set_id": new_id, "bk_set_name": bk_set_name})
        
        return make_response(data=created_sets)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@set_bp.route('/api/v3/set/search/<supplier_account>/<int:biz_id>', methods=['POST'])
@set_bp.route('/set/search/<supplier_account>/<int:biz_id>', methods=['POST'])
def search_set(supplier_account, biz_id):
    """
    查询集群列表
    POST /set/search/{bkSupplierAccount}/{bkBizId}
    
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
                "bk_set_id": 1,
                "bk_set_name": "集群名称",
                "bk_biz_id": 2,
                ...
            }
        ]
    }
    """
    try:
        req_data = request.get_json() or {}
        
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")
        
        filter_query = {
            "bk_biz_id": biz_id,
            "bk_supplier_account": supplier_account,
            "bk_data_status": {"$ne": "disabled"}
        }
        
        sets = list(conn.cc_SetBase.find(filter_query))
        
        result = []
        for s in sets:
            result.append({
                "bk_set_id": s.get("bk_set_id"),
                "bk_set_name": s.get("bk_set_name"),
                "bk_biz_id": s.get("bk_biz_id"),
                "bk_supplier_account": s.get("bk_supplier_account"),
                "bk_parent_id": s.get("bk_parent_id"),
                "bk_parent_obj": s.get("bk_parent_obj"),
                "description": s.get("description"),
                "bk_service_status": s.get("bk_service_status"),
                "bk_set_env": s.get("bk_set_env"),
                "create_time": s.get("create_time"),
                "last_time": s.get("last_time")
            })
        
        return make_response(data=result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@set_bp.route('/api/v3/set/<int:biz_id>/<int:set_id>', methods=['PUT'])
@set_bp.route('/set/<int:biz_id>/<int:set_id>', methods=['PUT'])
def update_set(biz_id, set_id):
    """
    更新集群信息
    PUT /set/{bkBizId}/{bkSetId}
    
    请求体:
    {
        "bk_set_name": "新名称",
        "description": "新描述",
        "bk_service_status": "1",
        "bk_set_env": "3"
    }
    
    响应:
    {
        "result": true,
        "code": 0,
        "message": "success",
        "data": {"bk_set_id": 123}
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
        
        for field in ["bk_set_name", "description", "bk_service_status", "bk_set_env"]:
            if field in req_data and req_data[field] is not None:
                update_fields[field] = req_data[field]
        
        result = conn.cc_SetBase.update_one(
            {"bk_set_id": set_id, "bk_biz_id": biz_id},
            {"$set": update_fields}
        )
        
        if result.modified_count > 0 or result.matched_count > 0:
            return make_response(data={"bk_set_id": set_id})
        else:
            return make_response(result=False, code=404, message="集群不存在")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@set_bp.route('/api/v3/set/<int:biz_id>/<int:set_id>', methods=['DELETE'])
@set_bp.route('/set/<int:biz_id>/<int:set_id>', methods=['DELETE'])
def delete_set(biz_id, set_id):
    """
    删除集群（级联删除集群下的所有模块）
    DELETE /set/{bkBizId}/{bkSetId}
    
    响应:
    {
        "result": true,
        "code": 0,
        "message": "success",
        "data": {"bk_set_id": 123}
    }
    """
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        conn.cc_ModuleBase.delete_many({"bk_set_id": set_id, "bk_biz_id": biz_id})
        
        result = conn.cc_SetBase.delete_one({
            "bk_set_id": set_id,
            "bk_biz_id": biz_id
        })
        
        if result.deleted_count > 0:
            return make_response(data={"bk_set_id": set_id})
        else:
            return make_response(result=False, code=404, message="集群不存在")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))
