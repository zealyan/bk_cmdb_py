"""权限管理 API 路由

提供权限查询、授权等 REST API。

Routes:
    GET /auth/permissions - 获取用户权限列表
    POST /auth/verify - 验证权限（兼容 IAM 格式）
    POST /auth/check - 检查权限
    POST /auth/grant - 授予权限
    POST /auth/revoke - 撤销权限
"""

from flask import Blueprint, request, jsonify, g
from app.auth.decorators import require_login, require_permission
from app.auth.permission import permission_checker
from app.auth.policies import (
    get_all_policies,
    get_user_policies,
    init_admin_super_permission,
    RESOURCE_TYPES,
    ACTION_TYPES
)

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/permissions', methods=['GET'])
@require_login
def get_my_permissions():
    """获取当前用户权限列表
    
    Response (JSON):
        {
            "result": true,
            "code": 0,
            "message": "success",
            "data": {
                "username": "admin",
                "permissions": [
                    {"obj": "biz", "act": "create", "name": "创建业务"},
                    {"obj": "biz", "act": "view", "name": "查看业务"}
                ],
                "resource_types": {...},
                "action_types": {...}
            }
        }
    """
    username = g.current_user
    
    permissions = permission_checker.get_user_permissions(username)
    
    perm_list = []
    for p in permissions:
        obj_name = RESOURCE_TYPES.get(p['obj'], p['obj'])
        act_name = ACTION_TYPES.get(p['act'], p['act'])
        perm_list.append({
            'obj': p['obj'],
            'act': p['act'],
            'name': f"{obj_name}:{act_name}"
        })
    
    return jsonify({
        "result": True,
        "code": 0,
        "message": "success",
        "data": {
            "username": username,
            "permissions": perm_list,
            "resource_types": RESOURCE_TYPES,
            "action_types": ACTION_TYPES
        }
    })


@auth_bp.route('/verify', methods=['POST'])
@require_login
def verify_permission():
    """验证权限（兼容前端 IAM 格式）
    
    Request Body (JSON):
        {
            "resources": [
                {
                    "type": "biz",
                    "action": "create",
                    "bk_biz_id": 1,
                    "resource_id": 123
                }
            ]
        }
        
    Response (JSON):
        {
            "result": true,
            "code": 0,
            "data": {
                "permission": {
                    "system_id": "bk_cmdb",
                    "actions": [
                        {
                            "id": "biz_create",
                            "type": "biz",
                            "is_allowed": true,
                            "related_resource_types": [...]
                        }
                    ]
                }
            }
        }
    """
    data = request.get_json() or {}
    resources = data.get('resources', [])
    username = g.current_user
    
    actions_result = []
    for resource in resources:
        obj = resource.get('type', '')
        act = resource.get('action', '')
        
        allowed = permission_checker.check_permission(username, obj, act)
        
        action_id = f"{obj}_{act}"
        
        related_resource_types = []
        if resource.get('resource_id'):
            related_resource_types.append({
                "type": obj,
                "system_id": "bk_cmdb",
                "instances": [{
                    "id": str(resource.get('resource_id')),
                    "type": obj
                }]
            })
        
        actions_result.append({
            "id": action_id,
            "type": obj,
            "is_allowed": allowed,
            "related_resource_types": related_resource_types
        })
    
    return jsonify({
        "result": True,
        "code": 0,
        "message": "success",
        "data": {
            "permission": {
                "system_id": "bk_cmdb",
                "actions": actions_result
            }
        }
    })


@auth_bp.route('/check', methods=['POST'])
@require_login
def check_permission():
    """检查权限
    
    Request Body (JSON):
        {
            "obj": "biz",
            "act": "create"
        }
        
    Response (JSON):
        {
            "result": true,
            "code": 0,
            "message": "success",
            "data": {
                "allowed": true,
                "obj": "biz",
                "act": "create"
            }
        }
    """
    data = request.get_json() or {}
    obj = data.get('obj', '')
    act = data.get('act', '')
    
    if not obj or not act:
        return jsonify({
            "result": False,
            "code": 400,
            "message": "缺少 obj 或 act 参数"
        }), 400
    
    username = g.current_user
    allowed = permission_checker.check_permission(username, obj, act)
    
    return jsonify({
        "result": True,
        "code": 0,
        "message": "success",
        "data": {
            "allowed": allowed,
            "obj": obj,
            "act": act
        }
    })


@auth_bp.route('/grant', methods=['POST'])
@require_permission('model', 'edit')
def grant_permission():
    """授予权限
    
    仅管理员可以授权。
    
    Request Body (JSON):
        {
            "username": "tom",
            "obj": "biz",
            "act": "create",
            "obj_id": "123"  // 可选，实例级别权限
        }
        
    Response (JSON):
        {
            "result": true,
            "code": 0,
            "message": "success"
        }
    """
    data = request.get_json() or {}
    username = data.get('username', '')
    obj = data.get('obj', '')
    act = data.get('act', '')
    obj_id = data.get('obj_id', None)
    
    if not username or not obj or not act:
        return jsonify({
            "result": False,
            "code": 400,
            "message": "缺少必要参数"
        }), 400
    
    success = permission_checker.add_permission(username, obj, act, obj_id)
    
    if success:
        return jsonify({
            "result": True,
            "code": 0,
            "message": "权限授予成功"
        })
    else:
        return jsonify({
            "result": False,
            "code": 400,
            "message": "权限已存在或授权失败"
        })


@auth_bp.route('/revoke', methods=['POST'])
@require_permission('model', 'edit')
def revoke_permission():
    """撤销权限
    
    仅管理员可以撤销权限。
    
    Request Body (JSON):
        {
            "username": "tom",
            "obj": "biz",
            "act": "create",
            "obj_id": "123"  // 可选，实例级别权限
        }
        
    Response (JSON):
        {
            "result": true,
            "code": 0,
            "message": "success"
        }
    """
    data = request.get_json() or {}
    username = data.get('username', '')
    obj = data.get('obj', '')
    act = data.get('act', '')
    obj_id = data.get('obj_id', None)
    
    if not username or not obj or not act:
        return jsonify({
            "result": False,
            "code": 400,
            "message": "缺少必要参数"
        }), 400
    
    success = permission_checker.remove_permission(username, obj, act, obj_id)
    
    if success:
        return jsonify({
            "result": True,
            "code": 0,
            "message": "权限撤销成功"
        })
    else:
        return jsonify({
            "result": False,
            "code": 400,
            "message": "权限不存在或撤销失败"
        })


@auth_bp.route('/init', methods=['POST'])
def init_permissions():
    """初始化权限
    
    初始化 admin 超级权限和默认策略。
    
    Response (JSON):
        {
            "result": true,
            "code": 0,
            "message": "success",
            "data": {
                "admin_policies": 40,
                "default_policies": 5
            }
        }
    """
    init_admin_super_permission()
    
    return jsonify({
        "result": True,
        "code": 0,
        "message": "权限初始化成功"
    })
