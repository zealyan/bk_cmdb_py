import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

from flask import Blueprint, request, jsonify, session as flask_session, g
from functools import wraps
from app.models.db import db, get_db_connection
from app.auth import hash_password, verify_password
from app.auth.session import session_manager
from app.config import Config

user_bp = Blueprint('user', __name__)


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


def require_auth(f):
    """登录验证装饰器
    
    检查请求中的 Token 或 HTTP 头用户信息是否有效，用于保护需要登录才能访问的接口。
    支持以下认证方式（按优先级）：
    1. HTTP 头中的 BK_User (原项目标准)
    2. Cookie 中的 bk_token
    3. Authorization Bearer Token
    
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
        bk_user = None
        supplier_account = None
        
        headers_dict = dict(request.headers)
        headers_lower = {k.lower().replace('-', '_'): v for k, v in request.headers}
        
        logger.debug(f"All headers: {headers_dict}")
        logger.debug(f"Headers lower: {headers_lower}")
        
        if 'bk_user' in headers_lower:
            bk_user = headers_lower['bk_user']
            logger.debug(f"Found BK_User: {bk_user}")
        
        if 'http_blueking_supplier_id' in headers_lower:
            supplier_account = headers_lower['http_blueking_supplier_id']
        elif 'blueking_supplier_id' in headers_lower:
            supplier_account = headers_lower['blueking_supplier_id']
        
        logger.debug(f"bk_user={bk_user}, supplier_account={supplier_account}, SKIP_LOGIN={Config.SKIP_LOGIN}")
        
        if bk_user:
            conn = get_db_connection()
            if conn:
                user = conn.users.find_one({"username": bk_user})
                if user:
                    g.current_user = bk_user
                    g.user_info = {
                        'display_name': user.get('display_name', bk_user),
                        'role': user.get('role', 'user')
                    }
                    g.supplier_account = supplier_account or '0'
                    return f(*args, **kwargs)
                else:
                    g.current_user = bk_user
                    g.user_info = {
                        'display_name': bk_user,
                        'role': 'admin'
                    }
                    g.supplier_account = supplier_account or '0'
                    return f(*args, **kwargs)
        
        if Config.SKIP_LOGIN:
            g.current_user = Config.SKIP_LOGIN_USER
            g.user_info = {
                'display_name': 'Administrator',
                'role': 'admin'
            }
            g.supplier_account = '0'
            return f(*args, **kwargs)
        
        token = request.cookies.get('bk_token')
        
        if not token:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header[7:]
        
        if not token:
            print(f"[Auth Debug] No auth found. BK_User={bk_user}, Token={token}, Headers={dict(request.headers)}")
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
        g.supplier_account = supplier_account or '0'
        
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

        # 优先从 MongoDB 的 users 集合查找（仅当该集合存在时）
        user = None
        try:
            if conn and 'users' in conn.list_collection_names():
                user = conn.users.find_one({"username": username})
        except Exception:
            user = None

        # 内置 internal 管理员兜底：与 bk-cmdb common.yaml
        # webServer.session.userInfo: admin:admin 一致。
        # 不写入 MongoDB（项目只保留 initdb 原生数据），仅用于运行时鉴权。
        if user is None and Config.is_superuser(username):
            if password == Config.ADMIN_PASSWORD:
                user = {
                    "_builtin": True,
                    "username": Config.ADMIN_USERNAME,
                    "display_name": "Administrator",
                    "role": "admin",
                }
            else:
                return make_response(
                    result=False,
                    code=1100000,
                    message="用户名或密码错误"
                )

        if user is None:
            return make_response(
                result=False,
                code=1100000,
                message="用户名或密码错误"
            )

        # 密码校验：内置管理员走明文比对；Mongo 用户走哈希校验
        if not user.get('_builtin'):
            stored_password = user.get('password', '')
            if not verify_password(password, stored_password):
                print(f"[DEBUG] 密码验证失败")
                return make_response(
                    result=False,
                    code=1100000,
                    message="用户名或密码错误"
                )

        print(f"[DEBUG] 密码验证成功（用户: {username}）")
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
@user_bp.route('/user/list', methods=['GET', 'POST'])
def user_list():
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        # 兼容多种请求数据格式（POST 为 JSON/form/body；GET 参数在 query string）
        req_data = {}
        if request.method == 'GET':
            req_data = request.args.to_dict()
        elif request.is_json:
            req_data = request.get_json() or {}
        elif request.form:
            req_data = request.form.to_dict()
        elif request.data:
            try:
                import json
                req_data = json.loads(request.data)
            except Exception:
                req_data = {}
        page = req_data.get('page', {}) if isinstance(req_data.get('page'), dict) else {}
        start = int(page.get('start', 0) or 0)
        limit = int(page.get('limit', 10) or 10)
        fuzzy = str(req_data.get('fuzzy_lookups') or req_data.get('fuzzy_lookups') or '').strip().lower()

        # 最小系统无独立用户目录，以内置超级管理员 admin 作为唯一账户兜底
        admin_user = {
            "bk_username": Config.ADMIN_USERNAME,
            "username": Config.ADMIN_USERNAME,
            "bk_role": 1,
            "role": "admin",
            "language": "zh",
        }
        users = list(conn.users.find())
        for u in users:
            u.pop('_id', None)
            u.pop('password', None)
        if not users:
            users = [admin_user]

        # 模糊匹配（bk-cmdb 行为）
        if fuzzy:
            users = [
                u for u in users
                if fuzzy in str(u.get('bk_username', '')).lower()
                or fuzzy in str(u.get('username', '')).lower()
            ]

        count = len(users)
        paged = users[start:start + limit] if limit else users
        return make_response(data={"count": count, "info": paged})
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


@user_bp.route('/proxy/get/usermanage/api/c/compapi/v2/usermanage/fs_list_users/', methods=['GET', 'POST'])
@user_bp.route('/api/c/compapi/v2/usermanage/fs_list_users/', methods=['GET', 'POST'])
@user_bp.route('/proxy/get/usermanage/api/c/compapi/v2/usermanage/list_users/', methods=['GET', 'POST'])
def usermanage_list_users():
    """蓝鲸用户管理API - 获取用户列表
    
    支持蓝鲸用户选择器组件调用，提供用户搜索和列表功能。
    
    Query Parameters (GET) or Request Body (POST):
        fuzzy_lookups: 模糊搜索关键词
        page: 页码
        page_size: 每页数量
        exact_lookups: 精确匹配用户名列表
    
    Response (JSON):
        {
            "code": 0,
            "message": "success",
            "result": true,
            "data": {
                "count": 3,
                "results": [
                    {
                        "id": 1,
                        "username": "admin",
                        "display_name": "Administrator",
                        "domain": "default.local",
                        "logo": null,
                        "category_id": 1,
                        "category_name": "默认目录"
                    }
                ]
            }
        }
    """
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({
                "code": 500,
                "message": "数据库连接失败",
                "result": False,
                "data": {"count": 0, "results": []}
            })
        
        # 获取请求参数（同时支持 GET 和 POST）
        params = {}
        if request.method == 'GET':
            params = request.args.to_dict()
        elif request.is_json:
            params = request.get_json() or {}
        elif request.form:
            params = request.form.to_dict()
        elif request.data:
            try:
                import json
                params = json.loads(request.data)
            except:
                pass
        
        # 解析分页参数
        page = int(params.get('page', 1))
        page_size = int(params.get('page_size', 20))
        start = (page - 1) * page_size
        
        # 构建查询条件
        query = {}
        
        # 支持模糊搜索
        fuzzy_lookups = params.get('fuzzy_lookups', '')
        if fuzzy_lookups:
            import re
            regex = re.compile(fuzzy_lookups, re.IGNORECASE)
            query['$or'] = [
                {'username': {'$regex': regex}},
                {'display_name': {'$regex': regex}}
            ]
        
        # 支持精确搜索（逗号分隔的用户名列表）
        exact_lookups = params.get('exact_lookups', '')
        if exact_lookups:
            usernames = [u.strip() for u in exact_lookups.split(',') if u.strip()]
            if usernames:
                query['username'] = {'$in': usernames}
        
        # 查询用户数据
        users = list(conn.users.find(query).skip(start).limit(page_size))
        total_count = conn.users.count_documents(query)
        
        # 转换为蓝鲸用户管理API格式
        results = []
        for idx, user in enumerate(users):
            results.append({
                "id": idx + 1,
                "username": user.get('username', ''),
                "display_name": user.get('display_name', user.get('username', '')),
                "domain": "default.local",
                "logo": None,
                "category_id": 1,
                "category_name": "默认目录"
            })
        
        # 检查是否有 JSONP 回调
        callback = request.args.get('callback')
        response_data = {
            "code": 0,
            "message": "success",
            "result": True,
            "data": {
                "count": total_count,
                "results": results
            }
        }
        
        if callback:
            # 返回 JSONP 格式
            import json
            return f"{callback}({json.dumps(response_data, ensure_ascii=False)})", 200, {
                'Content-Type': 'application/javascript; charset=utf-8'
            }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"获取用户列表失败: {e}")
        import traceback
        traceback.print_exc()
        error_response = {
            "code": 500,
            "message": f"获取用户列表失败: {str(e)}",
            "result": False,
            "data": {"count": 0, "results": []}
        }
        
        callback = request.args.get('callback')
        if callback:
            import json
            return f"{callback}({json.dumps(error_response, ensure_ascii=False)})", 200, {
                'Content-Type': 'application/javascript; charset=utf-8'
            }
        
        return jsonify(error_response)


@user_bp.route('/admin/find/system_config/platform_setting/current', methods=['GET'])
@user_bp.route('/api/v3/admin/find/system_config/platform_setting/current', methods=['GET'])
@require_auth
def get_current_config():
    """获取当前用户的全局设置"""
    # 导入 Base64 编码
    import base64
    
    # 默认全局配置，包含验证规则（按照前端期望的格式）
    config = {
        "backend": {
            "max_biz_topo_level": 0,
            "snapshot_biz_name": "蓝鲸"
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
            "businessTopoInstNames": {
                "value": base64.b64encode(b"^[^|/:*,<>\"?# ]*$").decode('utf-8'),
                "i18n": {
                    "cn": "格式不正确，不能包含特殊字符 | / : * , < > \" ? #及空格",
                    "en": "Invalid format, cannot contain special characters | / : * , < > \" ? # or spaces"
                }
            }
        },
        "set": "空闲机池",
        "idle_pool": {
            "idle": "空闲机",
            "fault": "故障机",
            "recycle": "待回收",
            "user_modules": []
        }
    }
    return make_response(data=config)


@user_bp.route('/admin/find/system_config/platform_setting/initial', methods=['GET'])
@user_bp.route('/api/v3/admin/find/system_config/platform_setting/initial', methods=['GET'])
@require_auth
def get_default_config():
    """获取默认的全局设置"""
    import base64
    
    config = {
        "backend": {
            "max_biz_topo_level": 0,
            "snapshot_biz_name": "蓝鲸"
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
            "businessTopoInstNames": {
                "value": base64.b64encode(b"^[^|/:*,<>\"?# ]*$").decode('utf-8'),
                "i18n": {
                    "cn": "格式不正确，不能包含特殊字符 | / : * , < > \" ? #及空格",
                    "en": "Invalid format, cannot contain special characters | / : * , < > \" ? # or spaces"
                }
            }
        },
        "set": "空闲机池",
        "idle_pool": {
            "idle": "空闲机",
            "fault": "故障机",
            "recycle": "待回收",
            "user_modules": []
        }
    }
    return make_response(data=config)


@user_bp.route('/api/v3/site/config', methods=['GET'])
@user_bp.route('/site/config', methods=['GET'])
def site_config():
    """获取站点配置信息
    
    返回前端需要的站点配置信息，包括登录方式等。
    
    Response (JSON):
        {
            "result": true,
            "code": 0,
            "message": "success",
            "data": {
                "login": "skip-login" | "internal" | "",
                "authscheme": "internal" | "iam",
                "userManage": "http://localhost:8080/api/c/compapi/v2/usermanage/fs_list_users/"
            }
        }
    """
    login_version = "skip-login" if Config.SKIP_LOGIN else ""
    
    return make_response(data={
        "login": login_version,
        "authscheme": "internal",
        "userManage": "/api/c/compapi/v2/usermanage/fs_list_users/"
    })
