"""权限数据存储模块

将权限策略存储在 MongoDB 中。
"""

from typing import List, Dict, Any
from datetime import datetime
from app.models.db import db, is_mongo_available


def get_collection():
    """获取 MongoDB 集合"""
    if not is_mongo_available():
        return None
    return db["auth_policies"]


def load_policies() -> List[Dict[str, Any]]:
    """加载所有权限策略"""
    if not is_mongo_available():
        return []
    
    collection = get_collection()
    return list(collection.find({"effect": "allow"}))


def add_policy(sub: str, obj: str, act: str, obj_id: str = None) -> bool:
    """添加单条策略
    
    Args:
        sub: 用户名
        obj: 资源类型
        act: 动作
        obj_id: 资源实例ID（可选，为None表示该资源类型的所有实例）
        
    Returns:
        bool: 添加是否成功
    """
    if not is_mongo_available():
        return False
    
    collection = get_collection()
    
    # 检查是否已存在
    query = {"sub": sub, "obj": obj, "act": act, "effect": "allow"}
    if obj_id:
        query["obj_id"] = obj_id
    else:
        query["obj_id"] = None
    
    existing = collection.find_one(query)
    if existing:
        return False
    
    collection.insert_one({
        "sub": sub,
        "sub_type": "user",
        "obj": obj,
        "act": act,
        "obj_id": obj_id,
        "effect": "allow",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    })
    
    return True


def remove_policy(sub: str, obj: str, act: str, obj_id: str = None) -> bool:
    """删除单条策略
    
    Args:
        sub: 用户名
        obj: 资源类型
        act: 动作
        obj_id: 资源实例ID（可选）
        
    Returns:
        bool: 删除是否成功
    """
    if not is_mongo_available():
        return False
    
    collection = get_collection()
    
    query = {"sub": sub, "obj": obj, "act": act}
    if obj_id:
        query["obj_id"] = obj_id
    else:
        query["obj_id"] = None
    
    result = collection.delete_one(query)
    return result.deleted_count > 0


def clear_policies() -> bool:
    """清空所有策略"""
    if not is_mongo_available():
        return False
    
    collection = get_collection()
    collection.delete_many({})
    return True


def get_user_policies(username: str) -> List[Dict[str, Any]]:
    """获取用户的所有策略"""
    if not is_mongo_available():
        return []
    
    collection = get_collection()
    return list(collection.find({"sub": username}))


def check_permission(username: str, obj: str, act: str, obj_id: str = None) -> bool:
    """检查用户是否有权限
    
    Args:
        username: 用户名
        obj: 资源类型
        act: 动作
        obj_id: 资源实例ID（可选）
        
    Returns:
        bool: 是否有权限
    """
    # Admin 有所有权限
    if username == "admin":
        return True
    
    if not is_mongo_available():
        return False
    
    collection = get_collection()
    
    # 优先检查实例级别的权限
    if obj_id:
        policy = collection.find_one({
            "sub": username,
            "obj": obj,
            "act": act,
            "effect": "allow",
            "obj_id": obj_id
        })
        if policy:
            return True
    
    # 检查资源类型级别的权限（obj_id 为 None 表示所有实例）
    policy = collection.find_one({
        "sub": username,
        "obj": obj,
        "act": act,
        "effect": "allow",
        "obj_id": None
    })
    
    return policy is not None
