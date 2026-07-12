"""Database Models Package

仅使用 db.py 中的 MongoDB 连接与查询能力。项目统一连接 bk-cmdb 的 ``cmdb`` 实例，
不再提供本地 mock 数据初始化。

Usage:
    from app.models import db, get_mongo_collection

    collection = get_mongo_collection('cc_ApplicationBase')

Exports:
    # MongoDB (db.py)
    - db: 数据库连接（延迟加载）
    - list_collections: 列出所有集合
    - get_collection_count: 获取集合记录数
    - get_mongo_collection: 获取指定集合
    - is_mongo_available: 检查数据库是否可用
"""

from app.models.db import (
    db,
    list_collections,
    get_collection_count,
    get_mongo_collection,
    is_mongo_available,
    get_all_collections
)

__all__ = [
    'db',
    'list_collections',
    'get_collection_count',
    'get_mongo_collection',
    'is_mongo_available',
    'get_all_collections',
]
