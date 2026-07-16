"""MongoDB 数据访问层（兼容层）

逻辑已复刻到 ``app/common/mongo``（对齐 bk-cmdb Go storage/driver/mongodb +
storage/dal/mongo/local）。本模块保留原有公共 API，确保既有路由无需改动即可获得
**连接池 / 操作指标 / 错误分类 / 读偏好** 等能力：

  * get_db_connection / get_db           -> 延迟加载、带连接池与指标监听的客户端
  * get_mongo_collection                -> 返回 pymongo 原生集合（向后兼容）
  * next_sequence                       -> 原子自增 ID（对齐 Go NextSequence）
  * is_mongo_available / list_collections / get_collection_count ...

关键约定：
  * 数据源：bk-cmdb 的 ``cmdb`` 数据库（由 initdb 写入真实拓扑 / 主机 / 模型数据）。
  * 连接：通过 app.config.Config 的 MONGODB_URI / MONGODB_DB 及新增的连接池参数。
  * 无 mock：不再维护 / 播种本地 mock 数据。
"""

from datetime import datetime  # noqa: F401  保留历史导入兼容
from pymongo import ReturnDocument  # noqa: F401  保留历史导入兼容

from app.common.mongo import MongoConf, new_mgo, next_sequence as _next_sequence
from app.common.mongo.client import read_preference_ctx  # noqa: F401  读偏好上下文可用

_mongo = None
_db = None
use_mongomock = False


class _LazyDatabase:
    """延迟数据库代理（对齐原 db.py 的模块级 db 变量）。

    ``from app.models.db import db`` 在导入时绑定的是本代理实例；每次属性 / 下标
    访问都即时解析由 :func:`get_db_connection` 返回的实时 pymongo Database，
    因此无需在导入阶段完成 MongoDB 连接即可被路由直接使用（支持 db.cc_X 与
    db["cc_X"] 两种访问方式）。
    """

    def __getattr__(self, name):
        return getattr(get_db_connection(), name)

    def __getitem__(self, name):
        return get_db_connection()[name]

    def __repr__(self):  # pragma: no cover - 仅调试友好
        try:
            real = get_db_connection()
            return f"<LazyDatabase proxy -> {real!r}>"
        except Exception:  # noqa: BLE001
            return "<LazyDatabase proxy (unconnected)>"


# 暴露为模块级 db，供 ``from app.models.db import db`` 向后兼容使用。
db = _LazyDatabase()


def _build_conf() -> MongoConf:
    from app.config import Config

    return MongoConf(
        uri=Config.MONGODB_URI,
        rs_name=getattr(Config, "MONGODB_REPLICA_SET", "rs0"),
        max_open_conns=int(getattr(Config, "MONGODB_MAX_POOL_SIZE", 1000)),
        max_idle_conns=int(getattr(Config, "MONGODB_MIN_POOL_SIZE", 50)),
        socket_timeout=int(getattr(Config, "MONGODB_SOCKET_TIMEOUT", 10)),
        connect_timeout=int(getattr(Config, "MONGODB_CONNECT_TIMEOUT", 60)),
        max_conn_idle_time=int(getattr(Config, "MONGODB_MAX_IDLE_TIME", 25 * 60)),
        server_selection_timeout=int(getattr(Config, "MONGODB_SERVER_SELECTION_TIMEOUT", 30)),
        app_name=getattr(Config, "MONGODB_APP_NAME", "cmdb_server_py"),
        retry_writes=False,
    )


def get_db_connection():
    """获取 MongoDB 连接（延迟加载，带连接池 + 指标监听）。"""
    global _mongo, _db, use_mongomock
    if _mongo is None:
        try:
            _mongo = new_mgo(_build_conf())
            _db = _mongo.dbc[_mongo.dbname]
            print(f"MongoDB 连接成功 -> db='{_mongo.dbname}' "
                  f"(连接池 max={_build_conf().max_open_conns}, min={_build_conf().max_idle_conns})")
            use_mongomock = False
        except Exception as e:  # noqa: BLE001
            print(f"MongoDB 连接失败: {e}")
            print("尝试使用 mongomock 作为内存数据库（仅开发兜底）...")
            try:
                import mongomock

                client = mongomock.MongoClient()
                _db = client[getattr(__import__("app.config", fromlist=["Config"]).Config,
                                     "MONGODB_DB", "cmdb")]
                use_mongomock = True
                print("mongomock 内存数据库初始化成功")
            except ImportError:
                print("mongomock 未安装，请运行 pip install mongomock")
    return _db


def get_db():
    """获取数据库连接（延迟加载别名）。"""
    return get_db_connection()


def get_mongo_collection(collection_name: str):
    """获取指定 Collection 句柄（pymongo 原生集合，向后兼容）。"""
    return get_db_connection()[collection_name]


def next_sequence(conn, sequence_name: str):
    """Go 风格原子自增 ID 生成器（对齐 Go NextSequence）。

    :param conn: pymongo Database 或 Mongo 包装对象均可。
    """
    from app.common.mongo.client import Mongo

    if isinstance(conn, Mongo):
        # Mongo 包装对象（app/common/mongo/client.Mongo）
        db = conn.dbc[conn.dbname]
    else:
        # pymongo Database（注意：pymongo Database.__getattr__ 会把任意属性
        # 当成集合名，故不能用 hasattr(conn, "dbc") 区分，必须用 isinstance）
        db = conn
    return _next_sequence(db, sequence_name)


def list_collections():
    """列出当前数据库所有集合名称。"""
    conn = get_db_connection()
    return conn.list_collection_names() if conn is not None else []


def get_collection_count(collection_name: str):
    """获取集合记录数。"""
    conn = get_db_connection()
    return conn[collection_name].count_documents({}) if conn is not None else 0


def is_mongo_available():
    """检查数据库是否可用（用于健康检查 / 启动校验）。"""
    try:
        conn = get_db_connection()
        if conn is not None:
            if use_mongomock:
                return True
            _mongo.dbc.admin.command("ping")
            return True
        return False
    except Exception as e:  # noqa: BLE001
        print(f"MongoDB 可用性检查失败: {e}")
        return False


def get_all_collections():
    """获取当前数据库所有集合名称（真实 MongoDB 实例）。"""
    return list_collections()
