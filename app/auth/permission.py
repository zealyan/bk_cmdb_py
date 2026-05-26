"""权限检查核心模块

提供权限验证的核心功能，包括权限检查、角色管理等。
"""

from typing import Optional, List, Dict, Any
from app.auth import casbin_adapter


class PermissionChecker:
    """权限检查器"""
    
    _instance = None
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
        """初始化"""
        pass  # 无需特殊初始化
    
    def reload(self):
        """重新加载策略"""
        pass  # 无需重新加载
    
    def check_permission(self, username: str, obj: str, act: str, obj_id: str = None) -> bool:
        """检查用户权限
        
        Args:
            username: 用户名
            obj: 资源类型
            act: 动作
            obj_id: 资源实例ID（可选）
            
        Returns:
            bool: 有权限返回 True，否则返回 False
        """
        return casbin_adapter.check_permission(username, obj, act, obj_id)
    
    def add_permission(self, username: str, obj: str, act: str, obj_id: str = None) -> bool:
        """添加用户权限
        
        Args:
            username: 用户名
            obj: 资源类型
            act: 动作
            obj_id: 资源实例ID（可选，为None表示所有实例）
            
        Returns:
            bool: 添加成功返回 True
        """
        return casbin_adapter.add_policy(username, obj, act, obj_id)
    
    def remove_permission(self, username: str, obj: str, act: str, obj_id: str = None) -> bool:
        """删除用户权限
        
        Args:
            username: 用户名
            obj: 资源类型
            act: 动作
            obj_id: 资源实例ID（可选）
            
        Returns:
            bool: 删除成功返回 True
        """
        return casbin_adapter.remove_policy(username, obj, act, obj_id)
    
    def get_user_permissions(self, username: str, with_instance: bool = False) -> List[Dict[str, Any]]:
        """获取用户所有权限
        
        Args:
            username: 用户名
            with_instance: 是否包含实例级别权限
            
        Returns:
            List[Dict]: 权限列表，每个元素包含 obj 和 act，可选包含 obj_id
        """
        policies = casbin_adapter.get_user_policies(username)
        
        if with_instance:
            return [{"obj": p["obj"], "act": p["act"], "obj_id": p.get("obj_id")} for p in policies]
        else:
            return [{"obj": p["obj"], "act": p["act"]} for p in policies]
    
    def has_any_permission(self, username: str, obj: str) -> bool:
        """检查用户是否拥有资源的任意权限
        
        Args:
            username: 用户名
            obj: 资源类型
            
        Returns:
            bool: 拥有任意权限返回 True
        """
        if username == "admin":
            return True
        
        perms = self.get_user_permissions(username)
        return any(p["obj"] == obj for p in perms)


# 全局权限检查器实例
permission_checker = PermissionChecker()
