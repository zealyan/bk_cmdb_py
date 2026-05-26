"""Session Management Module

会话管理模块，提供 Token 生成和验证功能。

Classes:
    SessionManager: 会话管理类

Global:
    session_manager: 全局 Session 管理器实例
"""

import secrets
import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any


class SessionManager:
    """Session 管理器

    管理用户登录会话，支持 Token 生成和验证。
    采用简单的 Token 方案，存储在内存和文件中（持久化）。

    Attributes:
        _sessions: 存储会话的字典 {token: session_data}
        _token_expiry: Token 过期时间（小时）
        _session_file: 会话持久化文件路径
    """

    def __init__(self, token_expiry_hours: int = 24):
        """初始化 Session 管理器

        Args:
            token_expiry_hours: Token 过期时间，默认 24 小时
        """
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._token_expiry = token_expiry_hours
        self._session_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'data',
            'sessions.json'
        )
        self._ensure_data_dir()
        self._load_sessions()

    def _ensure_data_dir(self):
        """确保数据目录存在"""
        data_dir = os.path.dirname(self._session_file)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

    def _load_sessions(self):
        """从文件加载会话数据"""
        if os.path.exists(self._session_file):
            try:
                with open(self._session_file, 'r') as f:
                    self._sessions = json.load(f)
                self._cleanup_expired_silent()
            except Exception as e:
                print(f"[WARNING] 加载会话文件失败: {e}")
                self._sessions = {}

    def _save_sessions(self):
        """将会话数据保存到文件"""
        try:
            with open(self._session_file, 'w') as f:
                json.dump(self._sessions, f)
        except Exception as e:
            print(f"[WARNING] 保存会话文件失败: {e}")

    def _cleanup_expired_silent(self):
        """静默清理过期会话（不保存，仅在加载时调用）"""
        now = datetime.now()
        expired_tokens = []
        for token, session in self._sessions.items():
            try:
                expires_at = datetime.fromisoformat(session['expires_at'])
                if now > expires_at:
                    expired_tokens.append(token)
            except Exception:
                expired_tokens.append(token)

        for token in expired_tokens:
            del self._sessions[token]

    def generate_token(self, username: str, user_info: Optional[Dict] = None) -> str:
        """生成登录 Token

        Args:
            username: 用户名
            user_info: 用户附加信息

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

        self._save_sessions()
        return token

    def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """验证 Token 有效性

        Args:
            token: 待验证的 Token

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

        try:
            expires_at = datetime.fromisoformat(session['expires_at'])
            if datetime.now() > expires_at:
                del self._sessions[token]
                self._save_sessions()
                return None
        except Exception:
            del self._sessions[token]
            self._save_sessions()
            return None

        return session

    def get_username(self, token: str) -> Optional[str]:
        """从 Token 获取用户名

        Args:
            token: Token 字符串

        Returns:
            Optional[str]: 用户名，Token 无效返回 None
        """
        session = self.validate_token(token)
        return session['username'] if session else None

    def invalidate_token(self, token: str) -> bool:
        """使 Token 失效（登出）

        Args:
            token: 要失效的 Token

        Returns:
            bool: 成功返回 True，Token 不存在返回 False
        """
        if token in self._sessions:
            del self._sessions[token]
            self._save_sessions()
            return True
        return False

    def cleanup_expired(self) -> int:
        """清理过期会话

        Returns:
            int: 清理的会话数量
        """
        now = datetime.now()
        expired_tokens = []
        for token, session in self._sessions.items():
            try:
                if datetime.fromisoformat(session['expires_at']) < now:
                    expired_tokens.append(token)
            except Exception:
                expired_tokens.append(token)

        for token in expired_tokens:
            del self._sessions[token]

        if expired_tokens:
            self._save_sessions()

        return len(expired_tokens)


# 全局 Session 管理器实例
session_manager = SessionManager()