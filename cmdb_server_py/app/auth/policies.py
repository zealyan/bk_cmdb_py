"""权限策略管理模块

提供权限策略的初始化和管理功能。
包含 admin 超级权限的初始化逻辑。

Functions:
    init_default_policies: 初始化默认策略
    init_admin_super_permission: 初始化 admin 超级权限
    get_all_policies: 获取所有策略
"""

from typing import List, Dict, Any
from app.models.db import get_db_connection, is_mongo_available
from app.auth import casbin_adapter


RESOURCE_TYPES = {
    "biz": "业务",
    "host": "主机",
    "module": "模块",
    "set": "集群",
    "process": "进程",
    "cloud_area": "云区域",
    "model": "模型",
    "custom_query": "自定义查询",
}

ACTION_TYPES = {
    "create": "创建",
    "view": "查看",
    "edit": "编辑",
    "delete": "删除",
    "list": "列表",
}


def init_admin_super_permission() -> bool:
    """初始化 admin 超级权限
    
    admin 用户对所有资源拥有所有权限。
    
    Returns:
        bool: 初始化成功返回 True
    """
    if not is_mongo_available():
        print("MongoDB 不可用，跳过 admin 权限初始化")
        return False
    
    db_conn = get_db_connection()
    collection = db_conn["auth_policies"]
    
    # 先删除旧的 admin 权限
    collection.delete_many({"sub": "admin"})
    
    # 添加所有资源和动作的权限
    policies = []
    for obj in RESOURCE_TYPES.keys():
        for act in ACTION_TYPES.keys():
            policies.append({
                "sub": "admin",
                "sub_type": "user",
                "obj": obj,
                "act": act,
                "obj_id": None,
                "effect": "allow",
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
    
    db_conn = get_db_connection()
    collection = db_conn["auth_policies"]
    
    default_policies = [
        {"sub": "tom", "obj": "biz", "act": "view"},
        {"sub": "tom", "obj": "host", "act": "view"},
        {"sub": "tom", "obj": "host", "act": "edit"},
        {"sub": "jelly", "obj": "biz", "act": "view"},
        {"sub": "jelly", "obj": "biz", "act": "list"},
    ]
    
    for policy in default_policies:
        existing = collection.find_one({
            "sub": policy["sub"],
            "obj": policy["obj"],
            "act": policy["act"]
        })
        
        if not existing:
            collection.insert_one({
                **policy,
                "sub_type": "user",
                "obj_id": None,
                "effect": "allow",
            })
    
    print(f"默认权限策略初始化完成，共 {len(default_policies)} 条")
    return True


def get_all_policies() -> List[Dict[str, Any]]:
    """获取所有权限策略
    
    Returns:
        List[Dict]: 策略列表
    """
    return casbin_adapter.load_policies()


def get_user_policies(username: str) -> List[Dict[str, Any]]:
    """获取指定用户的权限策略
    
    Args:
        username: 用户名
        
    Returns:
        List[Dict]: 策略列表
    """
    return casbin_adapter.get_user_policies(username)
