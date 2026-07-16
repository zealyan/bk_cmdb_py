"""MongoDB 连接配置（对齐 Go storage/dal/mongo/config.go）。

把 Go 的 MaxOpenConns / MaxIdleConns / SocketTimeout / ConnectTimeout / MaxConnIdleTime
等常量与默认值逐一映射到 Python 侧，供 new_mgo() 构造带连接池的 MongoClient。
"""

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# 连接池 / 超时默认值（与 Go config.go 常量一一对应）
# ---------------------------------------------------------------------------
DEFAULT_MAX_OPEN_CONNS = 1000          # Go DefaultMaxOpenConns
MAXIMUM_MAX_OPEN_CONNS = 3000          # Go MaximumMaxOpenConns
MINIMUM_MAX_IDLE_CONNS = 50            # Go MinimumMaxIdleOpenConns
DEFAULT_SOCKET_TIMEOUT = 10            # 秒，Go DefaultSocketTimeout
MAXIMUM_SOCKET_TIMEOUT = 30            # 秒，Go MaximumSocketTimeout
MINIMUM_SOCKET_TIMEOUT = 5             # 秒，Go MinimumSocketTimeout
CONNECT_TIMEOUT = 60                   # 秒，Go NewMgo 传入的 time.Minute
MAX_CONN_IDLE_TIME = 25 * 60           # 秒，Go maxConnIdleTime = 25min
SERVER_SELECTION_TIMEOUT = 30          # 秒
WAIT_QUEUE_TIMEOUT = 0                 # 秒，0=使用驱动默认（对齐 Go 不显式设置）


@dataclass
class MongoConf:
    """MongoDB 连接配置（对齐 Go mongo.Config / local.MongoConf）。"""

    uri: str = ""
    rs_name: str = "rs0"                       # 副本集名称（Go 必填 ReplicaSet）
    max_open_conns: int = DEFAULT_MAX_OPEN_CONNS
    max_idle_conns: int = MINIMUM_MAX_IDLE_CONNS
    socket_timeout: int = DEFAULT_SOCKET_TIMEOUT
    connect_timeout: int = CONNECT_TIMEOUT
    max_conn_idle_time: int = MAX_CONN_IDLE_TIME
    server_selection_timeout: int = SERVER_SELECTION_TIMEOUT
    app_name: str = "cmdb_server_py"           # 对齐 Go AppName（连接标识）
    retry_writes: bool = False                 # 对齐 Go RetryWrites=false（事务号方案要求）

    def build_uri(self) -> str:
        return self.uri
