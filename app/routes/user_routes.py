from flask import Blueprint, request, jsonify, session as flask_session, g
from functools import wraps
from app.models.db import db, get_db_connection, INIT_DATA, init_mock_data
from app.auth import hash_password, verify_password
from app.auth.session import session_manager
from app.config import Config

user_bp = Blueprint('user', __name__)


def make_response(result=True, code=0, message="success", data=None):
    return jsonify({
        "result": result,
        "code": code,
        "message": message,
        "data": data
    })


def require_auth(f):
    """登录验证装饰器
    
    检查请求中的 Token 是否有效，用于保护需要登录才能访问的接口。
    当 SKIP_LOGIN 配置启用时，自动使用管理员账户。
    
    Args:
        f: 被装饰的函数
        
    Returns:
        装饰后的函数
        
    Raises:
        401: Token 无效或已过期（仅在未启用 skip login 时）
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        # Skip Login 模式：自动使用配置的用户
        if Config.SKIP_LOGIN:
            g.current_user = Config.SKIP_LOGIN_USER
            g.user_info = {
                'display_name': 'Administrator',
                'role': 'admin'
            }
            return f(*args, **kwargs)
        
        token = request.cookies.get('bk_token')
        
        if not token:
            token = request.headers.get('Authorization')
            if token and token.startswith('Bearer '):
                token = token[7:]
        
        if not token:
            return make_response(
                result=False,
                code=401,
                message="缺少认证信息"
            )
        
        session_data = session_manager.validate_token(token)
        if not session_data:
            return make_response(
                result=False,
                code=401,
                message="Token 无效或已过期"
            )
        
        g.current_user = session_data['username']
        g.user_info = session_data.get('user_info', {})
        
        return f(*args, **kwargs)
    
    return wrapper


@user_bp.route('/api/v3/user/auth', methods=['POST'])
@user_bp.route('/user/auth', methods=['POST'])
@user_bp.route('/api/user/login', methods=['POST'])
def user_auth():
    """用户登录认证
    
    验证用户名和密码，成功返回登录 Token。
    密码使用 bcrypt 加密验证，Token 用于后续请求认证。
    
    当 SKIP_LOGIN 配置启用时，自动使用管理员账户登录，无需验证凭证。
    
    Request Body (JSON):
        {
            "bk_username": "admin",      # 用户名
            "bk_password": "admin"       # 密码（明文）
        }
    
    Response (JSON):
        {
            "result": true,
            "code": 0,
            "message": "success",
            "data": {
                "bk_token": "xxx",       # 登录 Token
                "username": "admin",     # 用户名
                "display_name": "Administrator" # 显示名称
            }
        }
    
    Error Codes:
        1100000: 用户名或密码错误
        400: 请求参数错误
    
    Examples:
        POST /user/auth
        Body: {"bk_username": "admin", "bk_password": "admin"}
        
        Response:
        {
            "result": true,
            "code": 0,
            "message": "success",
            "data": {
                "bk_token": "abc123...",
                "username": "admin",
                "display_name": "Administrator"
            }
        }
    """
    try:
        print(f"[DEBUG] 登录请求路径: {request.path}")
        print(f"[DEBUG] SKIP_LOGIN 配置: {Config.SKIP_LOGIN}")
        
        # Skip Login 模式：自动登录配置的用户，无需请求体
        if Config.SKIP_LOGIN:
            username = Config.SKIP_LOGIN_USER
            user_info = {
                'display_name': 'Administrator',
                'role': 'admin'
            }
            print(f"[DEBUG] Skip Login 模式：自动登录用户 {username}")
            
            token = session_manager.generate_token(
                username=username,
                user_info=user_info
            )
            
            response = make_response(data={
                "bk_token": token,
                "username": username,
                "display_name": user_info['display_name']
            })
            
            response.set_cookie(
                'bk_token',
                token,
                max_age=86400,
                httponly=True,
                samesite='Lax'
            )
            
            return response
        
        # 非 Skip Login 模式下解析请求体
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
        print(f"[DEBUG] 请求数据: {req_data}")
        
        username = req_data.get('bk_username', '').strip() or req_data.get('username', '').strip()
        password = req_data.get('bk_password', '') or req_data.get('password', '')
        print(f"[DEBUG] 用户名: {username}, 密码长度: {len(password)}")
        
        if not username or not password:
            return make_response(
                result=False,
                code=400,
                message="用户名和密码不能为空"
            )
        
        conn = get_db_connection()

        
        if conn is None:
            return make_response(
                result=False,
                code=500,
                message="数据库连接失败"
            )
        
        user = conn.users.find_one({"username": username})
        print(f"[DEBUG] 从MongoDB找到用户: {user is not None}")
        
        if not user:
            return make_response(
                result=False,
                code=1100000,
                message="用户名或密码错误"
            )
        
        stored_password = user.get('password', '')
        
        if verify_password(password, stored_password):
            print(f"[DEBUG] 密码验证成功")
            token = session_manager.generate_token(
                username=username,
                user_info={
                    'display_name': user.get('display_name', ''),
                    'role': user.get('role', 'user')
                }
            )
            print(f"[DEBUG] 生成 Token: {token[:10]}...")
            
            # 设置 Cookie
            response = make_response(data={
                "bk_token": token,
                "username": username,
                "display_name": user.get('display_name', username)
            })
            
            # 设置 24 小时过期的 Cookie
            response.set_cookie(
                'bk_token',
                token,
                max_age=86400,  # 24 hours
                httponly=True,  # 防止 XSS
                samesite='Lax'
            )
            
            return response
        else:
            print(f"[DEBUG] 密码验证失败")
            return make_response(
                result=False,
                code=1100000,
                message="用户名或密码错误"
            )
            
    except Exception as e:
        print(f"[DEBUG] 登录异常: {e}")
        import traceback
        traceback.print_exc()
        return make_response(
            result=False,
            code=500,
            message=f"登录失败: {str(e)}"
        )


@user_bp.route('/logout', methods=['POST'])
@user_bp.route('/api/v3/user/logout', methods=['POST'])
def user_logout():
    """用户登出
    
    使当前 Token 失效，退出登录状态。
    
    Request Headers:
        Cookie: bk_token=xxx  # 可选，通过 Cookie 或参数传递
    
    Response (JSON):
        {
            "result": true,
            "code": 0,
            "message": "success",
            "data": {
                "url": "/login"  # 退出后跳转地址
            }
        }
    
    Examples:
        POST /logout
        Headers: Cookie: bk_token=abc123...
        
        Response:
        {
            "result": true,
            "code": 0,
            "message": "success",
            "data": {"url": "/login"}
        }
    """
    try:
        token = request.cookies.get('bk_token')
        if not token:
            token = flask_session.get('bk_token')
        
        if token:
            session_manager.invalidate_token(token)
        
        # 清除 Cookie
        response = make_response(data={"url": "/login"})
        response.delete_cookie('bk_token')
        
        return response
        
    except Exception as e:
        return make_response(
            result=False,
            code=500,
            message=f"登出失败: {str(e)}"
        )


@user_bp.route('/proxy/user/list', methods=['POST'])
@user_bp.route('/user/list', methods=['POST'])
def user_list():
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
        page = req_data.get('page', {})
        start = page.get('start', 0)
        limit = page.get('limit', 10)

        users = list(conn.users.find().skip(start).limit(limit))
        count = conn.users.count_documents({})

        # 移除密码字段
        for user in users:
            user.pop('_id', None)
            user.pop('password', None)

        return make_response(data={"count": count, "info": users})
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


@user_bp.route('/proxy/user/detail', methods=['POST'])
@user_bp.route('/user/detail', methods=['POST'])
def user_detail():
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
        username = req_data.get('username', '')

        user = conn.users.find_one({"username": username})

        if user:
            user.pop('_id', None)
            user.pop('password', None)
            return make_response(data=user)
        else:
            return make_response(result=False, code=404, message="用户不存在")
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))


@user_bp.route('/api/v3/user/info', methods=['GET'])
@user_bp.route('/user/info', methods=['GET'])
@require_auth
def user_info():
    """获取当前用户信息
    
    获取当前登录用户的详细信息，用于页面刷新后恢复登录状态。
    
    Request Headers:
        Cookie: bk_token=xxx
        
    Response (JSON):
        {
            "result": true,
            "code": 0,
            "message": "success",
            "data": {
                "username": "admin",
                "display_name": "Administrator",
                "role": "admin"
            }
        }
    """
    try:
        username = g.current_user
        user_info = g.user_info
        
        return make_response(data={
            "username": username,
            "display_name": user_info.get('display_name', username),
            "role": user_info.get('role', 'user'),
            "admin": user_info.get('role') == 'admin'
        })
    except Exception as e:
        return make_response(result=False, code=500, message=str(e))
