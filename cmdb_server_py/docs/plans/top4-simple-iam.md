# TOP4: 简易授权 IAM Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现简易的基于 Casbin 的权限管理模块，包括权限检查、admin 超级权限初始化、权限中间件基础框架

**Architecture:** 采用 Casbin RBAC 模型 + MongoDB 策略存储 + Flask 中间件

**Tech Stack:** Casbin, Flask, MongoDB

---

## 需求分析（前置参考）

### 原 Go 项目授权机制

| 功能 | 原项目路径 | 实现方式 |
|------|------------|----------|
| IAM 类型定义 | `ac/iam/types.go` | 资源类型、动作定义 |
| 权限元数据 | `ac/meta/meta.go` | 资源属性、动作类型 |
| 认证配置 | `ac/iam/types.go` | AuthConfig、连接配置 |
| 策略数据 | `ac/meta/resource.go` | 资源、权限关联 |

**原项目特点：**
- 使用外部 IAM（bk_iam）进行权限管理
- 定义了完整的资源类型和动作
- 支持 RBAC（基于角色的访问控制）
- 资源层级结构

**简化策略：**
- 本实现采用本地 Casbin，无需外部 IAM 服务
- 使用简化的 RBAC 模型
- 支持资源-动作-主体权限模型
- 预置 admin 超级权限

### 当前 Python 项目状态

| 组件 | 当前状态 | 需要实现 |
|------|----------|----------|
| 用户认证 | 已完成 (TOP3) | Token 验证 |
| 权限框架 | 无 | Casbin 集成 |
| 权限策略 | 无 | MongoDB 存储 |
| 中间件 | 无 | 权限检查中间件 |

---

## 文件结构规划

| 动作 | 文件路径 | 说明 |
|------|---------|------|
| 添加 | `requirements.txt` | 添加 casbin 依赖 |
| 创建 | `app/auth/casbin_adapter.py` | Casbin MongoDB 适配器 |
| 创建 | `app/auth/permission.py` | 权限检查核心逻辑 |
| 创建 | `app/auth/policies.py` | 权限策略管理 |
| 创建 | `app/auth/decorators.py` | 权限装饰器 |
| 创建 | `app/routes/auth_routes.py` | 权限 API 路由 |
| 修改 | `app/models/db.py` | 添加策略集合 |
| 创建 | `scripts/init_admin_policy.py` | 初始化 admin 权限 |
| 创建 | `test_iam.py` | IAM 功能测试 |

---

## 权限模型设计

### 资源类型定义

```python
# 资源类型常量
RESOURCE_TYPES = {
    'biz': '业务',
    'host': '主机',
    'module': '模块',
    'set': '集群',
    'process': '进程',
    'cloud_area': '云区域',
    'model': '模型',
    'custom_query': '自定义查询',
}
```

### 动作类型定义

```python
# 动作类型常量
ACTION_TYPES = {
    'create': '创建',
    'view': '查看',
    'edit': '编辑',
    'delete': '删除',
    'list': '列表',
}
```

### 权限策略格式

```python
# Casbin 策略格式 (sub, obj, act)
# 示例: ("admin", "biz", "create") 表示 admin 可以创建业务

# MongoDB 存储格式
{
    "_id": ObjectId,
    "sub": "admin",           # 主体（用户名或角色）
    "sub_type": "user",       # 主体类型: user/role
    "obj": "biz",             # 资源类型
    "act": "create",          # 动作
    "obj_id": None,           # 具体资源ID（None表示所有资源）
    "effect": "allow",        # 权限效果: allow/deny
    "created_at": datetime,
    "updated_at": datetime,
}
```

### 超级管理员规则

```python
# admin 用户拥有所有权限
ADMIN_RULES = [
    ("admin", "*", "*"),      # admin 可以对所有资源执行所有动作
]

# 普通用户权限
USER_ROLES = {
    "operator": [
        ("tom", "biz", "view"),
        ("tom", "host", "view"),
        ("tom", "host", "edit"),
    ],
}
```

---

## 任务分解

---

### Task 1: 添加 Casbin 依赖

**Files:**
- 修改: `requirements.txt`

- [ ] **Step 1: 添加 casbin 依赖**

```bash
# 在 requirements.txt 添加
casbin>=1.16.0
pyyaml>=6.0
```

```txt
# requirements.txt 完整内容
Flask==2.3.3
Flask-Cors==4.0.0
Flask-SQLAlchemy==3.1.1
bcrypt>=4.1.0
Flask-Session>=0.5.0
casbin>=1.16.0
pyyaml>=6.0
```

- [ ] **Step 2: 安装依赖**

```bash
pip install casbin pyyaml
```

---

### Task 2: 创建 Casbin MongoDB 适配器

**Files:**
- 创建: `app/auth/casbin_adapter.py`

- [ ] **Step 1: 创建 Casbin 适配器**

```python
# app/auth/casbin_adapter.py
"""Casbin MongoDB 适配器

将 Casbin 的策略存储适配到 MongoDB。
实现 Casbin 的 Adapter 接口，支持策略的增删改查。

Class:
    Adapter: Casbin MongoDB 适配器
"""

import casbin
from typing import List, Tuple, Optional
from datetime import datetime
from app.models.db import db, is_mongo_available


class Adapter:
    """Casbin MongoDB 适配器
    
    将策略存储在 MongoDB 的 auth_policies 集合中。
    
    Attributes:
        collection_name: MongoDB 集合名称
    """
    
    def __init__(self, collection_name: str = "auth_policies"):
        """初始化适配器
        
        Args:
            collection_name (str): MongoDB 集合名称，默认 auth_policies
        """
        self.collection_name = collection_name
        self._db = db
    
    def _get_collection(self):
        """获取 MongoDB 集合
        
        Returns:
            Collection: MongoDB 集合对象
        """
        if not is_mongo_available():
            raise RuntimeError("MongoDB 不可用")
        return self._db[self.collection_name]
    
    def load_policy(self, model: casbin.Model) -> None:
        """加载策略到 Casbin 模型
        
        Args:
            model (casbin.Model): Casbin 模型对象
        """
        if not is_mongo_available():
            return
        
        collection = self._get_collection()
        
        policies = collection.find({"effect": "allow"})
        
        for policy in policies:
            sub = policy.get('sub', '')
            obj = policy.get('obj', '')
            act = policy.get('act', '')
            
            if sub and obj and act:
                model.add_policy("p", "p", [sub, obj, act])
    
    def save_policy(self, model: casbin.Model) -> None:
        """保存策略到 MongoDB
        
        Args:
            model (casbin.Model): Casbin 模型对象
        """
        if not is_mongo_available():
            return
        
        collection = self._get_collection()
        
        collection.delete_many({})
        
        policies = model.get_policy("p", "p")
        
        for policy in policies:
            if len(policy) >= 3:
                collection.insert_one({
                    'sub': policy[0],
                    'obj': policy[1],
                    'act': policy[2],
                    'effect': 'allow',
                    'created_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow()
                })
    
    def add_policy(self, sub: str, obj: str, act: str) -> bool:
        """添加单条策略
        
        Args:
            sub (str): 主体
            obj (str): 资源
            act (str): 动作
            
        Returns:
            bool: 添加成功返回 True
        """
        if not is_mongo_available():
            return False
        
        collection = self._get_collection()
        
        existing = collection.find_one({'sub': sub, 'obj': obj, 'act': act})
        if existing:
            return False
        
        collection.insert_one({
            'sub': sub,
            'obj': obj,
            'act': act,
            'effect': 'allow',
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        })
        
        return True
    
    def remove_policy(self, sub: str, obj: str, act: str) -> bool:
        """删除单条策略
        
        Args:
            sub (str): 主体
            obj (str): 资源
            act (str): 动作
            
        Returns:
            bool: 删除成功返回 True
        """
        if not is_mongo_available():
            return False
        
        collection = self._get_collection()
        
        result = collection.delete_one({'sub': sub, 'obj': obj, 'act': act})
        return result.deleted_count > 0
    
    def clear_policy(self) -> bool:
        """清空所有策略
        
        Returns:
            bool: 清空成功返回 True
        """
        if not is_mongo_available():
            return False
        
        collection = self._get_collection()
        collection.delete_many({})
        return True


def get_casbin_enforcer() -> casbin.Enforcer:
    """获取 Casbin 执行器
    
    创建并返回配置好的 Casbin 执行器。
    
    Returns:
        casbin.Enforcer: Casbin 执行器
        
    Examples:
        >>> e = get_casbin_enforcer()
        >>> e.enforce("admin", "biz", "create")
        True
    """
    adapter = Adapter()
    
    model_text = """
[request_definition]
r = sub, obj, act

[policy_definition]
p = sub, obj, act

[role_definition]
g = _, _

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = r.sub == p.sub && r.obj == p.obj && r.act == p.act
"""
    
    e = casbin.Enforcer(model_text, adapter)
    
    return e
```

---

### Task 3: 创建权限检查核心模块

**Files:**
- 创建: `app/auth/permission.py`

- [ ] **Step 1: 创建权限检查核心模块**

```python
# app/auth/permission.py
"""权限检查核心模块

提供权限验证的核心功能，包括权限检查、角色管理等。
使用 Casbin 作为权限验证引擎。

Class:
    PermissionChecker: 权限检查器
"""

import casbin
from typing import Optional, List, Dict, Any
from app.auth.casbin_adapter import get_casbin_enforcer


class PermissionChecker:
    """权限检查器
    
    管理权限验证和策略的集中管理类。
    使用单例模式确保全局只有一个检查器实例。
    
    Attributes:
        _enforcer: Casbin 执行器
        _initialized: 初始化状态
    """
    
    _instance = None
    _enforcer = None
    _initialized = False
    
    def __new__(cls):
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化权限检查器"""
        if not self._initialized:
            self._initialize()
            self._initialized = True
    
    def _initialize(self):
        """初始化 Casbin 执行器"""
        try:
            self._enforcer = get_casbin_enforcer()
        except Exception as e:
            print(f"权限检查器初始化失败: {e}")
            self._enforcer = None
    
    def reload(self):
        """重新加载策略"""
        if self._enforcer:
            self._enforcer.load_policy()
    
    def check_permission(self, username: str, obj: str, act: str) -> bool:
        """检查用户权限
        
        Args:
            username (str): 用户名
            obj (str): 资源类型
            act (str): 动作
            
        Returns:
            bool: 有权限返回 True，否则返回 False
            
        Examples:
            >>> checker = PermissionChecker()
            >>> checker.check_permission("admin", "biz", "create")
            True
            >>> checker.check_permission("tom", "biz", "create")
            False
        """
        if not self._enforcer:
            return False
        
        if username == "admin":
            return True
        
        try:
            return self._enforcer.enforce(username, obj, act)
        except Exception:
            return False
    
    def add_permission(self, username: str, obj: str, act: str) -> bool:
        """添加用户权限
        
        Args:
            username (str): 用户名
            obj (str): 资源类型
            act (str): 动作
            
        Returns:
            bool: 添加成功返回 True
        """
        if not self._enforcer:
            return False
        
        try:
            self._enforcer.add_policy(username, obj, act)
            self._enforcer.save_policy()
            return True
        except Exception:
            return False
    
    def remove_permission(self, username: str, obj: str, act: str) -> bool:
        """删除用户权限
        
        Args:
            username (str): 用户名
            obj (str): 资源类型
            act (str): 动作
            
        Returns:
            bool: 删除成功返回 True
        """
        if not self._enforcer:
            return False
        
        try:
            self._enforcer.remove_policy(username, obj, act)
            self._enforcer.save_policy()
            return True
        except Exception:
            return False
    
    def get_user_permissions(self, username: str) -> List[Dict[str, str]]:
        """获取用户所有权限
        
        Args:
            username (str): 用户名
            
        Returns:
            List[Dict]: 权限列表，每个元素包含 obj 和 act
            
        Examples:
            >>> checker = PermissionChecker()
            >>> perms = checker.get_user_permissions("tom")
            >>> print(perms)
            [{'obj': 'biz', 'act': 'view'}, {'obj': 'host', 'act': 'view'}]
        """
        if not self._enforcer:
            return []
        
        try:
            policies = self._enforcer.get_policy(username)
            return [{'obj': p[1], 'act': p[2]} for p in policies]
        except Exception:
            return []
    
    def has_any_permission(self, username: str, obj: str) -> bool:
        """检查用户是否拥有资源的任意权限
        
        Args:
            username (str): 用户名
            obj (str): 资源类型
            
        Returns:
            bool: 拥有任意权限返回 True
        """
        if username == "admin":
            return True
        
        perms = self.get_user_permissions(username)
        return any(p['obj'] == obj for p in perms)


# 全局权限检查器实例
permission_checker = PermissionChecker()
```

---

### Task 4: 创建权限策略管理模块

**Files:**
- 创建: `app/auth/policies.py`

- [ ] **Step 1: 创建权限策略管理模块**

```python
# app/auth/policies.py
"""权限策略管理模块

提供权限策略的初始化和管理功能。
包含 admin 超级权限的初始化逻辑。

Functions:
    init_default_policies: 初始化默认策略
    init_admin_super_permission: 初始化 admin 超级权限
    get_all_policies: 获取所有策略
"""

from typing import List, Dict, Any
from app.models.db import db, is_mongo_available
from app.auth.casbin_adapter import Adapter


RESOURCE_TYPES = {
    'biz': '业务',
    'host': '主机',
    'module': '模块',
    'set': '集群',
    'process': '进程',
    'cloud_area': '云区域',
    'model': '模型',
    'custom_query': '自定义查询',
}

ACTION_TYPES = {
    'create': '创建',
    'view': '查看',
    'edit': '编辑',
    'delete': '删除',
    'list': '列表',
}


def init_admin_super_permission() -> bool:
    """初始化 admin 超级权限
    
    admin 用户对所有资源拥有所有权限。
    
    Returns:
        bool: 初始化成功返回 True
        
    Examples:
        >>> init_admin_super_permission()
        True
    """
    if not is_mongo_available():
        print("MongoDB 不可用，跳过 admin 权限初始化")
        return False
    
    collection = db['auth_policies']
    
    collection.delete_many({'sub': 'admin'})
    
    policies = []
    for obj in RESOURCE_TYPES.keys():
        for act in ACTION_TYPES.keys():
            policies.append({
                'sub': 'admin',
                'sub_type': 'user',
                'obj': obj,
                'act': act,
                'obj_id': None,
                'effect': 'allow',
            })
    
    if policies:
        collection.insert_many(policies)
    
    print(f"Admin 超级权限初始化完成，共 {len(policies)} 条策略")
    return True


def init_default_policies() -> bool:
    """初始化默认权限策略
    
    为普通用户初始化基础权限。
    
    Returns:
        bool: 初始化成功返回 True
    """
    if not is_mongo_available():
        return False
    
    collection = db['auth_policies']
    
    default_policies = [
        {'sub': 'tom', 'obj': 'biz', 'act': 'view'},
        {'sub': 'tom', 'obj': 'host', 'act': 'view'},
        {'sub': 'tom', 'obj': 'host', 'act': 'edit'},
        {'sub': 'jelly', 'obj': 'biz', 'act': 'view'},
        {'sub': 'jelly', 'obj': 'biz', 'act': 'list'},
    ]
    
    for policy in default_policies:
        existing = collection.find_one({
            'sub': policy['sub'],
            'obj': policy['obj'],
            'act': policy['act']
        })
        
        if not existing:
            collection.insert_one({
                **policy,
                'sub_type': 'user',
                'obj_id': None,
                'effect': 'allow',
            })
    
    print(f"默认权限策略初始化完成，共 {len(default_policies)} 条")
    return True


def get_all_policies() -> List[Dict[str, Any]]:
    """获取所有权限策略
    
    Returns:
        List[Dict]: 策略列表
        
    Examples:
        >>> policies = get_all_policies()
        >>> print(len(policies))
        45
    """
    if not is_mongo_available():
        return []
    
    collection = db['auth_policies']
    return list(collection.find({}))


def get_user_policies(username: str) -> List[Dict[str, Any]]:
    """获取指定用户的权限策略
    
    Args:
        username (str): 用户名
        
    Returns:
        List[Dict]: 策略列表
        
    Examples:
        >>> policies = get_user_policies("admin")
        >>> print(len(policies))
        40
    """
    if not is_mongo_available():
        return []
    
    collection = db['auth_policies']
    return list(collection.find({'sub': username}))
```

---

### Task 5: 创建权限装饰器

**Files:**
- 创建: `app/auth/decorators.py`

- [ ] **Step 1: 创建权限装饰器**

```python
# app/auth/decorators.py
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
        obj (str): 资源类型
        act (str): 动作类型
        
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
        obj (str): 资源类型
        
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
```

---

### Task 6: 创建权限 API 路由

**Files:**
- 创建: `app/routes/auth_routes.py`

- [ ] **Step 1: 创建权限 API 路由**

```python
# app/routes/auth_routes.py
"""权限管理 API 路由

提供权限查询、授权等 REST API。

Routes:
    GET /auth/permissions - 获取用户权限列表
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
            "act": "create"
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
    
    if not username or not obj or not act:
        return jsonify({
            "result": False,
            "code": 400,
            "message": "缺少必要参数"
        }), 400
    
    success = permission_checker.add_permission(username, obj, act)
    
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
            "act": "create"
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
    
    if not username or not obj or not act:
        return jsonify({
            "result": False,
            "code": 400,
            "message": "缺少必要参数"
        }), 400
    
    success = permission_checker.remove_permission(username, obj, act)
    
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
```

---

### Task 7: 创建权限初始化脚本

**Files:**
- 创建: `scripts/init_admin_policy.py`

- [ ] **Step 1: 创建权限初始化脚本**

```python
# scripts/init_admin_policy.py
"""权限策略初始化脚本

初始化 admin 超级权限和默认权限策略。

Usage:
    python scripts/init_admin_policy.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.auth.policies import (
    init_admin_super_permission,
    init_default_policies,
    get_all_policies
)
from app.models.db import is_mongo_available


def main():
    """主函数"""
    print("=" * 60)
    print("权限策略初始化")
    print("=" * 60)
    
    if not is_mongo_available():
        print("错误: MongoDB 不可用")
        return
    
    print("\n[1] 初始化 admin 超级权限...")
    init_admin_super_permission()
    
    print("\n[2] 初始化默认权限...")
    init_default_policies()
    
    print("\n[3] 验证权限策略...")
    policies = get_all_policies()
    print(f"共初始化 {len(policies)} 条权限策略")
    
    print("\n" + "=" * 60)
    print("权限初始化完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
```

---

### Task 8: 更新数据库初始化

**Files:**
- 修改: `app/models/db.py`

- [ ] **Step 1: 添加权限策略集合初始化**

```python
# 在 INIT_DATA 中添加 auth_policies
INIT_DATA = {
    # ... 保持其他集合不变 ...
    
    "auth_policies": [
        # Admin 超级权限由 scripts/init_admin_policy.py 初始化
    ],
}
```

- [ ] **Step 2: 添加集合创建**

```python
# 添加集合创建
if 'auth_policies' not in db.list_collection_names():
    db.create_collection('auth_policies')
    print("创建 auth_policies 集合")
```

---

### Task 9: 测试 IAM 功能

**Files:**
- 创建: `test_iam.py`

- [ ] **Step 1: 创建 IAM 测试脚本**

```python
# test_iam.py
"""IAM 功能测试脚本

测试权限检查、授予、撤销等功能。

Usage:
    python test_iam.py
"""

import sys
import requests

BASE_URL = "http://localhost:8080"


def test_admin_permissions():
    """测试 admin 超级权限"""
    print("\n=== 测试 Admin 超级权限 ===")
    
    admin_token = get_token("admin", "admin")
    if not admin_token:
        print("✗ 无法获取 admin token")
        return
    
    print(f"Admin Token: {admin_token[:30]}...")
    
    response = requests.get(
        f"{BASE_URL}/auth/permissions",
        cookies={"bk_token": admin_token}
    )
    
    data = response.json()
    
    if data.get("result"):
        perms = data.get("data", {}).get("permissions", [])
        print(f"✓ Admin 拥有 {len(perms)} 条权限")
        
        resource_types = data.get("data", {}).get("resource_types", {})
        print(f"✓ 支持 {len(resource_types)} 种资源类型")
    else:
        print(f"✗ 获取权限失败: {data.get('message')}")


def test_user_permissions():
    """测试普通用户权限"""
    print("\n=== 测试普通用户权限 ===")
    
    tom_token = get_token("tom", "tom123")
    if not tom_token:
        print("✗ 无法获取 tom token")
        return
    
    print(f"Tom Token: {tom_token[:30]}...")
    
    response = requests.get(
        f"{BASE_URL}/auth/permissions",
        cookies={"bk_token": tom_token}
    )
    
    data = response.json()
    
    if data.get("result"):
        perms = data.get("data", {}).get("permissions", [])
        print(f"✓ Tom 拥有 {len(perms)} 条权限")
        
        for p in perms:
            print(f"  - {p['name']}")
    else:
        print(f"✗ 获取权限失败: {data.get('message')}")


def test_permission_check():
    """测试权限检查"""
    print("\n=== 测试权限检查 ===")
    
    admin_token = get_token("admin", "admin")
    tom_token = get_token("tom", "tom123")
    
    test_cases = [
        {"user": "admin", "token": admin_token, "obj": "biz", "act": "create", "expected": True},
        {"user": "tom", "token": tom_token, "obj": "biz", "act": "create", "expected": False},
        {"user": "tom", "token": tom_token, "obj": "host", "act": "view", "expected": True},
    ]
    
    for test in test_cases:
        response = requests.post(
            f"{BASE_URL}/auth/check",
            json={"obj": test["obj"], "act": test["act"]},
            cookies={"bk_token": test["token"]}
        )
        
        data = response.json()
        allowed = data.get("data", {}).get("allowed", False)
        
        if allowed == test["expected"]:
            print(f"✓ {test['user']} {test['obj']}:{test['act']} = {allowed}")
        else:
            print(f"✗ {test['user']} {test['obj']}:{test['act']} 预期 {test['expected']}，实际 {allowed}")


def test_permission_grant():
    """测试权限授予"""
    print("\n=== 测试权限授予 ===")
    
    admin_token = get_token("admin", "admin")
    
    response = requests.post(
        f"{BASE_URL}/auth/grant",
        json={"username": "tom", "obj": "biz", "act": "create"},
        cookies={"bk_token": admin_token}
    )
    
    data = response.json()
    
    if data.get("result"):
        print("✓ 权限授予成功")
    else:
        print(f"✗ 权限授予失败: {data.get('message')}")


def get_token(username, password):
    """获取登录 Token"""
    response = requests.post(
        f"{BASE_URL}/user/auth",
        json={"bk_username": username, "bk_password": password}
    )
    
    data = response.json()
    return data.get("data", {}).get("bk_token")


if __name__ == "__main__":
    print("=" * 60)
    print("IAM 权限管理功能测试")
    print("=" * 60)
    
    try:
        test_admin_permissions()
        test_user_permissions()
        test_permission_check()
        test_permission_grant()
    except requests.exceptions.ConnectionError:
        print("\n⚠ 服务器未启动，跳过 API 测试")
        print("请先启动服务器: python app/app.py")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
```

- [ ] **Step 2: 运行测试**

```bash
# 1. 初始化权限
cd /workspace/bk_cmdb_py
source venv/bin/activate
python scripts/init_admin_policy.py

# 2. 启动服务器
python app/app.py

# 3. 运行测试
python test_iam.py
```

---

### Task 10: 集成到应用

**Files:**
- 修改: `app/app.py`

- [ ] **Step 1: 注册权限蓝图**

```python
# 在 app.py 中添加
from app.routes.auth_routes import auth_bp

app.register_blueprint(auth_bp)
```

- [ ] **Step 2: 启动时初始化权限**

```python
# 在应用启动时
from app.auth.policies import init_admin_super_permission, init_default_policies

with app.app_context():
    init_admin_super_permission()
    init_default_policies()
```

---

## 完成检查清单

在完成 TOP4 后，确认：

- [ ] `requirements.txt` 包含 casbin 依赖
- [ ] `app/auth/casbin_adapter.py` Casbin MongoDB 适配器已创建
- [ ] `app/auth/permission.py` 权限检查核心模块已创建
- [ ] `app/auth/policies.py` 权限策略管理已创建
- [ ] `app/auth/decorators.py` 权限装饰器已创建
- [ ] `app/routes/auth_routes.py` 权限 API 已创建
- [ ] admin 超级权限已初始化
- [ ] 权限检查装饰器可正常工作
- [ ] 权限 API 测试通过
- [ ] 集成到 Flask 应用

---

## 下一步

完成 TOP4 后，继续执行后续开发任务：

- **TOP5**: 业务 API（主机管理、业务管理）

---

## 附录：API 响应格式

### 获取权限列表

```json
{
    "result": true,
    "code": 0,
    "message": "success",
    "data": {
        "username": "admin",
        "permissions": [
            {"obj": "biz", "act": "create", "name": "业务:创建"},
            {"obj": "host", "act": "view", "name": "主机:查看"}
        ],
        "resource_types": {
            "biz": "业务",
            "host": "主机"
        },
        "action_types": {
            "create": "创建",
            "view": "查看"
        }
    }
}
```

### 权限检查

```json
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
```

### 无权限响应

```json
{
    "result": false,
    "code": 403,
    "message": "无权限: 需要 biz:create 权限",
    "data": null
}
```
