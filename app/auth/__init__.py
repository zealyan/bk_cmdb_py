"""Authentication Module

提供用户认证相关的工具函数，包括密码加密、Session 管理等。

Exports:
    - hash_password: 密码哈希加密
    - verify_password: 密码验证
    - upgrade_password_hash: 密码哈希升级
"""

from app.auth.password import hash_password, verify_password, upgrade_password_hash

__all__ = [
    'hash_password',
    'verify_password',
    'upgrade_password_hash',
]
