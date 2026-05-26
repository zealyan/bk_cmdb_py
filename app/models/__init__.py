"""Database Models Package

简化版本，只使用 db.py 中的 MongoDB/内存数据库功能。

Usage:
    # MongoDB
    from app.models import db, init_mock_data, get_mongo_collection
    
    init_mock_data()
    collection = get_mongo_collection('users')

Exports:
    # MongoDB (db.py)
    - db: 数据库连接
    - init_mock_data: 初始化数据
    - list_collections: 列出所有集合
    - get_collection_count: 获取集合记录数
    - get_mongo_collection: 获取指定集合
    - is_mongo_available: 检查数据库是否可用
"""

from app.models.db import (
    db,
    init_mock_data,
    list_collections,
    get_collection_count,
    get_mongo_collection,
    is_mongo_available,
    get_all_collections
)

__all__ = [
    'db',
    'init_mock_data',
    'list_collections',
    'get_collection_count',
    'get_mongo_collection',
    'is_mongo_available',
    'get_all_collections',
]
