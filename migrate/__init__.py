"""
BK-CMDB Python Migrate Module

基于原 Go 项目 upgrader 模块的数据迁移
"""

from datetime import datetime
from typing import Dict, List, Any, Optional

BK_DEFAULT_OWNER_ID = "0"
BK_SYSTEM_OPERATOR = "system"


def get_timestamp() -> datetime:
    return datetime.now()


class BaseMigrate:
    def __init__(self, db):
        self.db = db

    def ensure_collection(self, name: str) -> None:
        if name not in self.db.list_collection_names():
            self.db.create_collection(name)

    def upsert(self, collection: str, data: Dict, query_keys: List[str]) -> None:
        query = {k: data.get(k) for k in query_keys if k in data}
        existing = self.db[collection].find_one(query)
        if existing:
            self.db[collection].update_one(query, {"$set": data})
        else:
            self.db[collection].insert_one(data)

    def insert_if_not_exists(self, collection: str, data: Dict, query_keys: List[str]) -> None:
        query = {k: data.get(k) for k in query_keys if k in data}
        if not self.db[collection].find_one(query):
            self.db[collection].insert_one(data)

    def migrate(self) -> None:
        raise NotImplementedError("Subclasses must implement migrate()")
