"""权限装饰器模块

提供用于权限检查的装饰器，简化权限验证逻辑。

Functions:
    require_permission: 权限检查装饰器
    require_login: 登录验证装饰器
"""

from functools import wraps
from flask import request, jsonify, g
from typing import List, Optional
from app.auth.permission import permission_checker
from app.auth.session import session_manager


def require_login(f):
    """登录验证装饰器
    
    检查请求中的 Token 是否有效。
    
    Args:
        f: 被装饰的函数
        
    Returns:
        装饰后的函数
        
    Raises:
        401: Token 无效或缺失
        
    Examples:
        >>> @app.route('/api/user/info')
        ... @require_login
        ... def get_user_info():
        ...     return jsonify({"username": g.current_user})
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = request.cookies.get('bk_token')
        
        if not token:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]
        
        if not token:
            return jsonify({
                "result": False,
                "code": 401,
                "message": "缺少认证信息"
            }), 401
        
        session = session_manager.validate_token(token)
        if not session:
            return jsonify({
                "result": False,
                "code": 401,
                "message": "Token 无效或已过期"
            }), 401
        
        g.current_user = session['username']
        g.user_info = session.get('user_info', {})
        
        return f(*args, **kwargs)
    
    return wrapper


def require_permission(obj: str, act: str):
    """权限检查装饰器
    
    检查用户是否具有指定资源类型的指定动作权限。
    
    Args:
        obj: 资源类型
        act: 动作类型
        
    Returns:
        装饰器函数
        
    Raises:
        401: 未登录
        403: 无权限
        
    Examples:
        >>> @app.route('/api/biz/create', methods=['POST'])
        ... @require_login
        ... @require_permission('biz', 'create')
        ... def create_business():
        ...     return jsonify({"result": True})
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not hasattr(g, 'current_user'):
                token = request.cookies.get('bk_token')
                if not token:
                    auth_header = request.headers.get('Authorization', '')
                    if auth_header.startswith('Bearer '):
                        token = auth_header[7:]
                
                if not token:
                    return jsonify({
                        "result": False,
                        "code": 401,
                        "message": "缺少认证信息"
                    }), 401
                
                session = session_manager.validate_token(token)
                if not session:
                    return jsonify({
                        "result": False,
                        "code": 401,
                        "message": "Token 无效或已过期"
                    }), 401
                
                g.current_user = session['username']
                g.user_info = session.get('user_info', {})
            
            username = g.current_user
            
            if not permission_checker.check_permission(username, obj, act):
                return jsonify({
                    "result": False,
                    "code": 403,
                    "message": f"无权限: 需要 {obj}:{act} 权限"
                }), 403
            
            return f(*args, **kwargs)
        
        return wrapper
    return decorator


def require_any_permission(obj: str):
    """检查用户是否拥有资源的任意权限
    
    Args:
        obj: 资源类型
        
    Returns:
        装饰器函数
        
    Raises:
        401: 未登录
        403: 无权限
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not hasattr(g, 'current_user'):
                token = request.cookies.get('bk_token')
                if not token:
                    return jsonify({
                        "result": False,
                        "code": 401,
                        "message": "缺少认证信息"
                    }), 401
                
                session = session_manager.validate_token(token)
                if not session:
                    return jsonify({
                        "result": False,
                        "code": 401,
                        "message": "Token 无效或已过期"
                    }), 401
                
                g.current_user = session['username']
            
            username = g.current_user
            
            if not permission_checker.has_any_permission(username, obj):
                return jsonify({
                    "result": False,
                    "code": 403,
                    "message": f"无权限: 需要 {obj} 相关权限"
                }), 403
            
            return f(*args, **kwargs)
        
        return wrapper
    return decorator
