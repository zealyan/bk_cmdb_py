"""MongoDB 客户端封装（对齐 Go storage/dal/mongo/local/mongo.go 的 NewMgo / Mongo）。

new_mgo() 复刻 Go 的连接池与超时配置：MaxPoolSize / MinPoolSize / ConnectTimeout /
SocketTimeout / MaxConnIdleTime / ReplicaSet / AppName / RetryWrites，并通过
CommandListener 自动采集所有操作的指标。Mongo 提供 Table / Ping / Close /
next_sequence 等统一入口。
"""

import contextvars

from pymongo import MongoClient
from pymongo.read_preferences import (
    Nearest,
    Primary,
    PrimaryPreferred,
    Secondary,
    SecondaryPreferred,
)

from app.common.mongo.collection import Collection
from app.common.mongo.conf import MongoConf
from app.common.mongo.monitor import MongoCommandListener
from app.common.mongo.sequence import next_sequence
from app.common.types import ReadPreferenceMode

# 读偏好上下文变量（对齐 Go 通过 ctx 传递 read preference）
read_preference_ctx = contextvars.ContextVar(
    "mongo_read_preference", default=ReadPreferenceMode.NIL
)

_READ_PREF_MAP = {
    ReadPreferenceMode.PRIMARY: Primary(),
    ReadPreferenceMode.PRIMARY_PREFERRED: PrimaryPreferred(max_staleness=90),
    ReadPreferenceMode.SECONDARY: Secondary(max_staleness=90),
    ReadPreferenceMode.SECONDARY_PREFERRED: SecondaryPreferred(max_staleness=90),
    ReadPreferenceMode.NEAREST: Nearest(max_staleness=90),
}


def read_preference_for_ctx():
    """取当前上下文的读偏好对象（无则 None，使用驱动默认）。"""
    return _READ_PREF_MAP.get(read_preference_ctx.get())


def _db_name_from_uri(uri: str):
    """从 URI 解析 database 段（mongodb://u:p@h:port/db?opts -> db）。"""
    try:
        path = uri.split("?", 1)[0]
        db = path.rsplit("/", 1)[-1]
        return db or None
    except Exception:  # noqa: BLE001
        return None


class Mongo:
    """MongoDB 客户端封装（对齐 Go Mongo）。"""

    def __init__(self, client: MongoClient, db_name: str):
        self.dbc = client
        self.dbname = db_name

    def ping(self):
        self.dbc.admin.command("ping")

    def close(self):
        self.dbc.close()

    def table(self, name: str) -> Collection:
        return Collection(self, name)

    def get_db_client(self) -> MongoClient:
        return self.dbc

    def get_db_name(self) -> str:
        return self.dbname

    def next_sequence(self, sequence_name: str):
        return next_sequence(self.dbc[self.dbname], sequence_name)


def new_mgo(conf: MongoConf = None, connect_timeout_s=None) -> Mongo:
    """构造带连接池 / 超时 / 指标监听的 Mongo 客户端（对齐 Go NewMgo）。

    :param conf: MongoConf；为空时使用默认配置。
    :param connect_timeout_s: 覆盖连接超时（秒），对齐 Go 传入的 time.Minute。
    """
    if conf is None:
        conf = MongoConf()
    connect_timeout = connect_timeout_s if connect_timeout_s is not None else conf.connect_timeout

    kwargs = dict(
        connectTimeoutMS=connect_timeout * 1000,
        socketTimeoutMS=conf.socket_timeout * 1000,
        maxIdleTimeMS=conf.max_conn_idle_time * 1000,
        serverSelectionTimeoutMS=conf.server_selection_timeout * 1000,
        maxPoolSize=conf.max_open_conns,
        minPoolSize=conf.max_idle_conns,
        appName=conf.app_name,
        retryWrites=conf.retry_writes,
        event_listeners=[MongoCommandListener()],
    )
    if conf.rs_name:
        kwargs["replicaSet"] = conf.rs_name

    client = MongoClient(conf.uri, **kwargs)
    # 连接自检（对齐 Go client.Connect 后的可用性验证）
    client.admin.command("ping")

    db_name = _db_name_from_uri(conf.uri) or "cmdb"
    return Mongo(client, db_name)
