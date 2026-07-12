"""MongoDB 数据访问层

本项目（cmdb_server_py）统一使用 bk-cmdb 通过 initdb 初始化的 ``cmdb`` MongoDB 实例，
**不再维护 / 播种任何本地 mock 数据**。

关键约定：
  * 数据源：bk-cmdb 的 ``cmdb`` 数据库（由 bk-cmdb 的 initdb 流程写入真实拓扑 / 主机 / 模型数据）。
  * 连接：通过 ``app.config.Config.MONGODB_URI`` 与 ``MONGODB_DB`` 配置，默认即指向 ``cmdb``。
  * 无 mock：历史上 ``INIT_DATA`` 与 ``init_mock_data()`` 会向 ``bk_cmdb`` 库写入仿真数据，
    现已全部移除，避免与真实 ``cmdb`` 实例数据产生混淆。
"""

from pymongo import MongoClient
from app.config import Config

client = None
db = None
use_mongomock = False


def get_db_connection():
    """获取 MongoDB 连接，延迟加载。

    优先连接真实 MongoDB；仅当真实实例不可用时回退到 mongomock 内存库（开发兜底）。
    """
    global client, db, use_mongomock
    if client is None:
        # 首先尝试连接真实的 MongoDB（cmdb 实例）
        try:
            client = MongoClient(Config.MONGODB_URI, serverSelectionTimeoutMS=5000)
            client.admin.command('ping')
            db = client[Config.MONGODB_DB]
            print(f"MongoDB 连接成功 -> db='{Config.MONGODB_DB}'")
            use_mongomock = False
        except Exception as e:
            print(f"MongoDB 连接失败: {e}")
            print("尝试使用 mongomock 作为内存数据库（仅开发兜底）...")
            try:
                import mongomock
                client = mongomock.MongoClient()
                db = client[Config.MONGODB_DB]
                use_mongomock = True
                print("mongomock 内存数据库初始化成功")
            except ImportError:
                print("mongomock 未安装，请运行 pip install mongomock")
    return db


def get_db():
    """获取数据库连接（延迟加载的别名）。"""
    return get_db_connection()


def get_mongo_collection(collection_name):
    """获取指定 Collection 句柄。"""
    return get_db_connection()[collection_name]


def list_collections():
    """列出当前数据库所有集合名称。"""
    conn = get_db_connection()
    return conn.list_collection_names() if conn is not None else []


def get_collection_count(collection_name):
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
            # 真实 MongoDB 的检查方式
            client.admin.command('ping')
            return True
        return False
    except Exception as e:
        print(f"MongoDB 可用性检查失败: {e}")
        return False


def get_all_collections():
    """获取当前数据库所有集合名称（真实 MongoDB 实例）。"""
    return list_collections()
