"""Password Hashing Module

密码加密与验证模块，使用 bcrypt 算法。

Functions:
    hash_password: 密码哈希加密
    verify_password: 验证密码
    upgrade_password_hash: 密码哈希升级
"""

import bcrypt
from typing import Optional


def hash_password(password: str) -> str:
    """密码哈希加密

    使用 bcrypt 对明文密码进行加密存储

    Args:
        password: 明文密码

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
        plain_password: 明文密码
        hashed_password: 数据库中存储的哈希密码

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
        password: 明文密码
        old_hash: 旧的哈希值

    Returns:
        Optional[str]: 成功返回新哈希，失败返回 None
    """
    if verify_password(password, old_hash):
        return hash_password(password)
    return None
