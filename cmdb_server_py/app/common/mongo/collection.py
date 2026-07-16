"""集合操作封装（对齐 Go storage/dal/mongo/local/mongo.go 的 Collection）。

提供 Find/One/List/Count/Insert/Update/Upsert/Delete/Aggregate/Distinct/CreateIndex 等
常用操作；每个操作在 ``_coll()`` 中按需施加当前上下文的**读偏好**（对齐 Go 的
getCollectionOption(ctx)），操作级耗时与成败指标由驱动层 CommandListener 统一采集。

> 说明：本封装是「增强 DAL API」。既有路由仍可直接使用 pymongo 原生集合
> （通过 app.models.db.get_mongo_collection 获取），二者共享同一个带连接池 /
> 指标监听的 MongoClient，因此连接池与指标对所有路径均生效。
"""

from pymongo import ReturnDocument

from app.common.types import ErrDocumentNotFound


class Collection:
    def __init__(self, mongo, name: str):
        self.mongo = mongo
        self.name = name

    # ------------------------------------------------------------------
    # 内部：按上下文读偏好返回集合句柄
    # ------------------------------------------------------------------
    def _coll(self):
        from app.common.mongo.client import read_preference_for_ctx

        coll = self.mongo.dbc[self.mongo.dbname][self.name]
        rp = read_preference_for_ctx()
        if rp is not None:
            coll = coll.with_options(read_preference=rp)
        return coll

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    def find(self, filter=None, projection=None, sort=None, skip=0, limit=0):
        opts = {}
        if projection is not None:
            opts["projection"] = projection
        if sort is not None:
            opts["sort"] = sort
        if skip:
            opts["skip"] = skip
        if limit:
            opts["limit"] = limit
        return list(self._coll().find(filter or {}, **opts))

    def find_one(self, filter=None, projection=None):
        opts = {}
        if projection is not None:
            opts["projection"] = projection
        doc = self._coll().find_one(filter or {}, **opts)
        if doc is None:
            raise ErrDocumentNotFound()
        return doc

    def count(self, filter=None):
        return self._coll().count_documents(filter or {})

    def distinct(self, field: str, filter=None):
        return self._coll().distinct(field, filter or {})

    def aggregate(self, pipeline, allow_disk_use=False):
        return list(self._coll().aggregate(pipeline, allowDiskUse=allow_disk_use))

    # ------------------------------------------------------------------
    # 写
    # ------------------------------------------------------------------
    def insert_many(self, docs):
        from app.common.util import conver_to_interface_slice

        rows = conver_to_interface_slice(docs)
        return self._coll().insert_many(rows)

    def insert_one(self, doc):
        return self._coll().insert_one(doc)

    def update_many(self, filter, doc, upsert=False):
        return self._coll().update_many(filter or {}, {"$set": doc}, upsert=upsert)

    def update_one(self, filter, doc, upsert=False):
        return self._coll().update_one(filter or {}, {"$set": doc}, upsert=upsert)

    def upsert(self, filter, doc):
        return self._coll().update_one(filter or {}, {"$set": doc}, upsert=True)

    def delete_many(self, filter):
        return self._coll().delete_many(filter or {})

    def delete_one(self, filter):
        return self._coll().delete_one(filter or {})

    # ------------------------------------------------------------------
    # 索引 / 表
    # ------------------------------------------------------------------
    def create_index(self, keys, unique=False, name=None, background=True,
                     partial_filter=None, expire_after_seconds=0):
        opts = {"unique": unique, "background": background}
        if name:
            opts["name"] = name
        if partial_filter is not None:
            opts["partialFilterExpression"] = partial_filter
        if expire_after_seconds:
            opts["expireAfterSeconds"] = expire_after_seconds
        return self._coll().create_index(keys, **opts)

    def drop_index(self, name: str):
        try:
            self._coll().drop_index(name)
        except Exception as e:  # noqa: BLE001
            if "IndexNotFound" in str(e):
                return
            raise

    def has_table(self) -> bool:
        names = self.mongo.dbc[self.mongo.dbname].list_collection_names()
        return self.name in names
