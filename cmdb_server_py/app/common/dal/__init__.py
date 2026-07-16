"""数据访问抽象层（对齐 Go storage/dal）。

Go 的 storage/dal 定义了 RDB / Table 接口并由 storage/dal/mongo/local 实现。
本模块提供 new_rdb() 工厂，返回 app.common.mongo 的 Mongo 实现，作为 Python 侧
统一的数据访问入口。
"""

from app.common.mongo import Mongo, MongoConf, new_mgo

__all__ = ["Mongo", "MongoConf", "new_mgo", "new_rdb"]


def new_rdb(conf: MongoConf = None) -> Mongo:
    """构造 RDB（对齐 Go dal.NewMgo / InitClient）。"""
    return new_mgo(conf)
