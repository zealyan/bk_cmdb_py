# TOP3: 登录认证模块 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现完整的用户登录认证系统，包括密码加密（bcrypt）和 Session 管理，完善 user_routes.py 中的登录接口

**Architecture:** 采用 Flask 会话管理 + bcrypt 密码加密 + MongoDB 用户存储

**Tech Stack:** Flask-Session, bcrypt, MongoDB

---

## 需求分析（前置参考）

### 原 Go 项目认证机制

| 功能 | 原项目路径 | 实现方式 |
|------|------------|----------|
| API Basic Auth | `apiserver/middleware/auth.go` | 用户名密码验证 |
| 用户认证 | `web_server/middleware/user/user.go` | 登录接口抽象 |
| 认证开关 | `common/auth/auth.go` | EnableAuth 配置 |

**原项目特点：**
- 使用 BasicAuth 进行 API 认证
- 用户信息存储在 MongoDB
- 无内置密码加密（明文存储）
- 登录成功后返回 token

### 当前 Python 项目状态

| 文件 | 当前状态 | 需要改进 |
|------|----------|----------|
| `app/routes/user_routes.py` | 明文密码比较 | 需要 bcrypt 加密 |
| `app/models/db.py` | 明文密码存储 | 需要密码加密存储 |
| `requirements.txt` | 无认证依赖 | 需要添加 bcrypt、Flask-Session |

---

## 文件结构规划

| 动作 | 文件路径 | 说明 |
|------|---------|------|
| 修改 | `requirements.txt` | 添加 bcrypt、Flask-Session 依赖 |
| 创建 | `app/auth/__init__.py` | 认证工具模块（bcrypt 加密） |
| 创建 | `app/auth/session.py` | Session 管理工具 |
| 修改 | `app/routes/user_routes.py` | 完善登录接口（bcrypt + Session） |
| 创建 | `test_login.py` | 登录功能测试脚本 |
| 修改 | `app/app.py` | 集成 Session 配置 |
| 参考 | `app/models/db.py` | 用户数据模型 |

---

## 任务分解

---

### Task 1: 添加认证依赖

**Files:**
- 修改: `requirements.txt`

- [ ] **Step 1: 添加 bcrypt 和 Flask-Session 依赖**

```bash
# 在 requirements.txt 添加
bcrypt>=4.1.0
Flask-Session>=0.5.0
```

```txt
# requirements.txt 完整内容
Flask==2.3.3
Flask-Cors==4.0.0
Flask-SQLAlchemy==3.1.1
bcrypt>=4.1.0
Flask-Session>=0.5.0
```

- [ ] **Step 2: 安装依赖**

```bash
pip install bcrypt Flask-Session
```

---

### Task 2: 创建认证工具模块

**Files:**
- 创建: `app/auth/__init__.py`
- 创建: `app/auth/password.py`

- [ ] **Step 1: 创建密码加密工具**

```python
# app/auth/password.py
import bcrypt
from typing import Optional


def hash_password(password: str) -> str:
    """密码哈希加密
    
    使用 bcrypt 对明文密码进行加密存储
    
    Args:
        password (str): 明文密码
        
    Returns:
        str: 加密后的密码哈希字符串
        
    Examples:
        >>> hashed = hash_password("admin123")
        >>> print(hashed)
        $2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.LdMH7TI
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码
    
    使用 bcrypt 验证明文密码与哈希密码是否匹配
    
    Args:
        plain_password (str): 明文密码
        hashed_password (str): 数据库中存储的哈希密码
        
    Returns:
        bool: 密码匹配返回 True，否则返回 False
        
    Examples:
        >>> hashed = hash_password("admin123")
        >>> verify_password("admin123", hashed)
        True
        >>> verify_password("wrong_password", hashed)
        False
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'), 
            hashed_password.encode('utf-8')
        )
    except Exception:
        return False


def upgrade_password_hash(password: str, old_hash: str) -> Optional[str]:
    """升级旧密码哈希
    
    当密码算法升级时，将旧哈希升级为新算法
    
    Args:
        password (str): 明文密码
        old_hash (str): 旧的哈希值
        
    Returns:
        Optional[str]: 成功返回新哈希，失败返回 None
    """
    if verify_password(password, old_hash):
        return hash_password(password)
    return None
```

- [ ] **Step 2: 创建 app/auth/__init__.py**

```python
"""Authentication Module

提供用户认证相关的工具函数，包括密码加密、Session 管理等。

Exports:
    - hash_password: 密码哈希加密
    - verify_password: 密码验证
    - upgrade_password_hash: 密码哈希升级
"""

from app.auth.password import (
    hash_password,
    verify_password,
    upgrade_password_hash
)

__all__ = [
    'hash_password',
    'verify_password',
    'upgrade_password_hash',
]
```

---

### Task 3: 创建 Session 管理工具

**Files:**
- 创建: `app/auth/session.py`

- [ ] **Step 1: 创建 Session 管理工具**

```python
# app/auth/session.py
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any


class SessionManager:
    """Session 管理器
    
    管理用户登录会话，支持 Token 生成和验证。
    采用简单的 Token 方案，存储在内存中。
    
    Attributes:
        _sessions: 存储会话的字典 {token: session_data}
        _token_expiry: Token 过期时间（小时）
    """
    
    def __init__(self, token_expiry_hours: int = 24):
        """初始化 Session 管理器
        
        Args:
            token_expiry_hours (int): Token 过期时间，默认 24 小时
        """
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._token_expiry = token_expiry_hours
    
    def generate_token(self, username: str, user_info: Optional[Dict] = None) -> str:
        """生成登录 Token
        
        Args:
            username (str): 用户名
            user_info (Dict, optional): 用户附加信息
            
        Returns:
            str: 生成的 Token 字符串
            
        Examples:
            >>> manager = SessionManager()
            >>> token = manager.generate_token("admin")
            >>> print(len(token))
            64
        """
        timestamp = datetime.now().isoformat()
        random_data = secrets.token_hex(16)
        raw_token = f"{username}:{timestamp}:{random_data}"
        
        token = hashlib.sha256(raw_token.encode()).hexdigest()
        
        expiry = datetime.now() + timedelta(hours=self._token_expiry)
        
        self._sessions[token] = {
            'username': username,
            'user_info': user_info or {},
            'created_at': timestamp,
            'expires_at': expiry.isoformat()
        }
        
        return token
    
    def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """验证 Token 有效性
        
        Args:
            token (str): 待验证的 Token
            
        Returns:
            Optional[Dict]: Token 有效返回会话数据，否则返回 None
            
        Examples:
            >>> manager = SessionManager()
            >>> token = manager.generate_token("admin")
            >>> session = manager.validate_token(token)
            >>> print(session['username'])
            admin
        """
        if token not in self._sessions:
            return None
        
        session = self._sessions[token]
        
        expires_at = datetime.fromisoformat(session['expires_at'])
        if datetime.now() > expires_at:
            del self._sessions[token]
            return None
        
        return session
    
    def get_username(self, token: str) -> Optional[str]:
        """从 Token 获取用户名
        
        Args:
            token (str): Token 字符串
            
        Returns:
            Optional[str]: 用户名，Token 无效返回 None
        """
        session = self.validate_token(token)
        return session['username'] if session else None
    
    def invalidate_token(self, token: str) -> bool:
        """使 Token 失效（登出）
        
        Args:
            token (str): 要失效的 Token
            
        Returns:
            bool: 成功返回 True，Token 不存在返回 False
        """
        if token in self._sessions:
            del self._sessions[token]
            return True
        return False
    
    def cleanup_expired(self) -> int:
        """清理过期会话
        
        Returns:
            int: 清理的会话数量
        """
        now = datetime.now()
        expired_tokens = [
            token for token, session in self._sessions.items()
            if datetime.fromisoformat(session['expires_at']) < now
        ]
        
        for token in expired_tokens:
            del self._sessions[token]
        
        return len(expired_tokens)


# 全局 Session 管理器实例
session_manager = SessionManager()
```

---

### Task 4: 完善登录接口

**Files:**
- 修改: `app/routes/user_routes.py`

- [ ] **Step 1: 导入必要模块**

```python
from flask import Blueprint, request, jsonify, session
from app.auth import hash_password, verify_password
from app.auth.session import session_manager
from app.models.db import db
```

- [ ] **Step 2: 重写登录接口**

```python
@user_bp.route('/api/v3/user/auth', methods=['POST'])
@user_bp.route('/user/auth', methods=['POST'])
def user_auth():
    """用户登录认证
    
    验证用户名和密码，成功返回登录 Token。
    密码使用 bcrypt 加密验证，Token 用于后续请求认证。
    
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
                "display_name": "管理员" # 显示名称
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
        req_data = request.get_json() or {}
        
        username = req_data.get('bk_username', '').strip()
        password = req_data.get('bk_password', '')
        
        if not username or not password:
            return make_response(
                result=False, 
                code=400, 
                message="用户名和密码不能为空"
            )
        
        user = db.users.find_one({"username": username})
        
        if not user:
            return make_response(
                result=False, 
                code=1100000, 
                message="用户名或密码错误"
            )
        
        stored_password = user.get('password', '')
        
        if verify_password(password, stored_password):
            token = session_manager.generate_token(
                username=username,
                user_info={
                    'display_name': user.get('display_name', ''),
                    'role': user.get('role', 'user')
                }
            )
            
            return make_response(data={
                "bk_token": token,
                "username": username,
                "display_name": user.get('display_name', username)
            })
        else:
            return make_response(
                result=False, 
                code=1100000, 
                message="用户名或密码错误"
            )
            
    except Exception as e:
        return make_response(
            result=False, 
            code=500, 
            message=f"登录失败: {str(e)}"
        )
```

- [ ] **Step 3: 添加登出接口**

```python
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
            token = session.get('bk_token')
        
        if token:
            session_manager.invalidate_token(token)
        
        return make_response(data={"url": "/login"})
        
    except Exception as e:
        return make_response(
            result=False, 
            code=500, 
            message=f"登出失败: {str(e)}"
        )
```

- [ ] **Step 4: 添加 Token 验证中间件**

```python
def require_auth(f):
    """登录验证装饰器
    
    检查请求中的 Token 是否有效，用于保护需要登录才能访问的接口。
    
    Args:
        f: 被装饰的函数
        
    Returns:
        装饰后的函数
        
    Raises:
        401: Token 无效或已过期
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = request.cookies.get('bk_token')
        
        if not token:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]
        
        if not token:
            return make_response(
                result=False,
                code=401,
                message="缺少认证信息"
            )
        
        session = session_manager.validate_token(token)
        if not session:
            return make_response(
                result=False,
                code=401,
                message="Token 无效或已过期"
            )
        
        g.current_user = session['username']
        g.user_info = session.get('user_info', {})
        
        return f(*args, **kwargs)
    
    return wrapper
```

---

### Task 5: 更新用户数据（密码加密）

**Files:**
- 修改: `app/models/db.py`
- 创建: `scripts/migrate_passwords.py`

- [ ] **Step 1: 更新用户数据初始化（使用加密密码）**

```python
# 更新 INIT_DATA 中的用户密码
from app.auth import hash_password

INIT_DATA = {
    # ... 其他数据保持不变 ...
    "users": [
        {
            "username": "admin", 
            "password": hash_password("admin"),  # 使用 bcrypt 加密
            "display_name": "Administrator", 
            "qq": "", 
            "phone": "", 
            "email": ""
        },
        {
            "username": "tom", 
            "password": hash_password("tom123"),  # 使用 bcrypt 加密
            "display_name": "Tom", 
            "qq": "", 
            "phone": "", 
            "email": ""
        },
        {
            "username": "jelly", 
            "password": hash_password("jelly123"),  # 使用 bcrypt 加密
            "display_name": "Jelly", 
            "qq": "", 
            "phone": "", 
            "email": ""
        }
    ],
    # ... 其他数据保持不变 ...
}
```

- [ ] **Step 2: 创建密码迁移脚本**

```python
# scripts/migrate_passwords.py
"""密码迁移脚本

将明文密码迁移为 bcrypt 加密密码。

Usage:
    python scripts/migrate_passwords.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.db import db, is_mongo_available
from app.auth import hash_password, verify_password


def migrate_passwords():
    """迁移用户密码到 bcrypt 加密"""
    
    if not is_mongo_available():
        print("MongoDB 不可用，无法迁移")
        return
    
    users_collection = db['users']
    
    users = list(users_collection.find({}))
    
    migrated_count = 0
    skipped_count = 0
    
    for user in users:
        username = user.get('username')
        current_password = user.get('password', '')
        
        if not current_password:
            print(f"跳过用户 {username}: 密码为空")
            skipped_count += 1
            continue
        
        if current_password.startswith('$2'):
            print(f"跳过用户 {username}: 已经是加密密码")
            skipped_count += 1
            continue
        
        hashed = hash_password(current_password)
        
        users_collection.update_one(
            {'username': username},
            {'$set': {'password': hashed}}
        )
        
        print(f"已迁移用户 {username}")
        migrated_count += 1
    
    print(f"\n迁移完成: 成功 {migrated_count}, 跳过 {skipped_count}")


if __name__ == "__main__":
    migrate_passwords()
```

---

### Task 6: 更新 Flask 应用配置

**Files:**
- 修改: `app/app.py`

- [ ] **Step 1: 添加 Session 配置**

```python
from flask import Flask
from flask_cors import CORS
from flask_session import Session
from app.config import Config

app = Flask(__name__)
app.config.from_object(Config)

CORS(app, supports_credentials=True)

Session(app)
```

---

### Task 7: 测试登录功能

**Files:**
- 创建: `test_login.py`

- [ ] **Step 1: 创建登录功能测试脚本**

```python
# test_login.py
"""登录功能测试脚本

测试用户登录、Token 验证、密码验证等功能。

Usage:
    python test_login.py
"""

import requests
import json
from app.auth import hash_password, verify_password

BASE_URL = "http://localhost:8080"


def test_password_hashing():
    """测试密码加密功能"""
    print("\n=== 测试密码加密 ===")
    
    password = "admin123"
    hashed = hash_password(password)
    
    print(f"原始密码: {password}")
    print(f"加密后: {hashed[:50]}...")
    
    assert verify_password(password, hashed), "密码验证失败"
    assert not verify_password("wrong_password", hashed), "错误密码不应通过验证"
    
    print("✓ 密码加密测试通过")


def test_register_user():
    """测试用户注册（初始化）"""
    print("\n=== 测试用户初始化 ===")
    
    users = [
        {"username": "admin", "password": "admin"},
        {"username": "tom", "password": "tom123"},
        {"username": "jelly", "password": "jelly123"}
    ]
    
    for user in users:
        hashed = hash_password(user['password'])
        print(f"用户 {user['username']} 密码已加密: {hashed[:50]}...")
    
    print("✓ 用户初始化测试完成")


def test_login():
    """测试登录接口"""
    print("\n=== 测试登录接口 ===")
    
    test_cases = [
        {
            "username": "admin",
            "password": "admin",
            "expected": True
        },
        {
            "username": "admin",
            "password": "wrong_password",
            "expected": False
        },
        {
            "username": "nonexistent",
            "password": "test",
            "expected": False
        }
    ]
    
    for test in test_cases:
        response = requests.post(
            f"{BASE_URL}/user/auth",
            json={
                "bk_username": test["username"],
                "bk_password": test["password"]
            },
            headers={"Content-Type": "application/json"}
        )
        
        data = response.json()
        print(f"测试 {test['username']}/{test['password']}: ", end="")
        
        if test["expected"]:
            if data.get("result"):
                print("✓ 登录成功")
            else:
                print(f"✗ 登录失败: {data.get('message')}")
        else:
            if not data.get("result"):
                print("✓ 正确拒绝无效登录")
            else:
                print(f"✗ 不应成功: {data}")
    
    print("✓ 登录接口测试完成")


def test_authenticated_request():
    """测试带 Token 的认证请求"""
    print("\n=== 测试认证请求 ===")
    
    response = requests.post(
        f"{BASE_URL}/user/auth",
        json={"bk_username": "admin", "bk_password": "admin"}
    )
    
    data = response.json()
    token = data.get("data", {}).get("bk_token")
    
    if not token:
        print("✗ 无法获取 Token")
        return
    
    print(f"获取 Token: {token[:30]}...")
    
    response = requests.post(
        f"{BASE_URL}/user/list",
        json={"page": {"start": 0, "limit": 10}},
        cookies={"bk_token": token}
    )
    
    data = response.json()
    if data.get("result"):
        print(f"✓ 认证请求成功，用户数: {data.get('data', {}).get('count', 0)}")
    else:
        print(f"✗ 认证请求失败: {data.get('message')}")


if __name__ == "__main__":
    print("=" * 60)
    print("登录认证功能测试")
    print("=" * 60)
    
    test_password_hashing()
    test_register_user()
    
    try:
        test_login()
        test_authenticated_request()
    except requests.exceptions.ConnectionError:
        print("\n⚠ 服务器未启动，跳过 API 测试")
        print("请先启动服务器: python app/app.py")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
```

- [ ] **Step 2: 运行测试**

```bash
# 1. 先初始化加密密码
cd /workspace/bk_cmdb_py
source venv/bin/activate

# 迁移现有密码（如果需要）
python scripts/migrate_passwords.py

# 2. 启动服务器
python app/app.py

# 3. 运行测试（另一个终端）
cd /workspace/bk_cmdb_py
source venv/bin/activate
python test_login.py
```

---

### Task 8: API 兼容性测试

- [ ] **Step 1: 测试与原 API 的兼容性**

```bash
# 测试标准 API 格式
curl -X POST http://localhost:8080/api/v3/user/auth \
  -H "Content-Type: application/json" \
  -d '{"bk_username":"admin","bk_password":"admin"}'

# 测试简化格式
curl -X POST http://localhost:8080/user/auth \
  -H "Content-Type: application/json" \
  -d '{"bk_username":"admin","bk_password":"admin"}'
```

---

## 完成检查清单

在完成 TOP3 后，确认：

- [ ] `requirements.txt` 包含 bcrypt 和 Flask-Session
- [ ] `app/auth/__init__.py` 认证工具模块已创建
- [ ] `app/auth/password.py` 密码加密功能实现
- [ ] `app/auth/session.py` Session 管理实现
- [ ] `user_routes.py` 登录接口已完善（bcrypt + Token）
- [ ] 用户密码已加密存储（bcrypt）
- [ ] Token 生成和验证功能正常
- [ ] 登录/登出接口测试通过
- [ ] API 响应格式与原项目兼容
- [ ] 测试脚本 `test_login.py` 可正常运行

---

## 下一步

完成 TOP3 后，继续执行后续开发任务：

- **TOP4**: 简易授权 IAM（Casbin 权限管理）
- **TOP5**: 业务 API（主机、业务管理）

---

## 附录：API 响应格式

### 登录成功响应

```json
{
    "result": true,
    "code": 0,
    "message": "success",
    "data": {
        "bk_token": "abc123def456...",
        "username": "admin",
        "display_name": "Administrator"
    }
}
```

### 登录失败响应

```json
{
    "result": false,
    "code": 1100000,
    "message": "用户名或密码错误",
    "data": null
}
```

### Token 验证失败响应

```json
{
    "result": false,
    "code": 401,
    "message": "Token 无效或已过期",
    "data": null
}
```
