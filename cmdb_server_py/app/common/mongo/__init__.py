"""MongoDB 驱动公共层（对齐 Go storage/driver/mongodb + storage/dal/mongo/local）。

对外暴露统一入口：MongoConf / new_mgo / Mongo / Collection / next_sequence /
错误分类 / 读偏好上下文。业务代码既可直接用 new_mgo 得到 Mongo 句柄，也可继续
通过 app.models.db 的兼容层获取 pymongo 原生集合（二者共享同一带连接池与
指标监听的客户端）。
"""

from app.common.errors import (
    get_duplicate_key,
    get_duplicate_value,
    is_duplicated_error,
    is_not_found_error,
)
from app.common.mongo.client import (
    Mongo,
    new_mgo,
    read_preference_ctx,
    read_preference_for_ctx,
)
from app.common.mongo.collection import Collection
from app.common.mongo.conf import (
    DEFAULT_MAX_OPEN_CONNS,
    DEFAULT_SOCKET_TIMEOUT,
    MINIMUM_MAX_IDLE_CONNS,
    MongoConf,
)
from app.common.mongo.sequence import next_sequence, next_sequences

__all__ = [
    "MongoConf",
    "Mongo",
    "new_mgo",
    "Collection",
    "next_sequence",
    "next_sequences",
    "is_duplicated_error",
    "is_not_found_error",
    "get_duplicate_key",
    "get_duplicate_value",
    "read_preference_ctx",
    "read_preference_for_ctx",
    "DEFAULT_MAX_OPEN_CONNS",
    "MINIMUM_MAX_IDLE_CONNS",
    "DEFAULT_SOCKET_TIMEOUT",
]
