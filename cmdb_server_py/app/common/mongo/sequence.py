"""序列号（自增 ID）生成（对齐 Go storage/dal/mongo/local/mongo.go NextSequence/NextSequences）。

使用 ``find_one_and_update`` 原子递增 ``cc_idgenerator.SequenceID``，支持 upsert，
返回递增后的值；分表名经 redirectTable 规则重定向到主表（与 Go 一致）。
"""

from datetime import datetime

from pymongo import ReturnDocument


def _redirect_table(name: str) -> str:
    """分表名重定向到主表（对齐 Go Mongo.redirectTable）。"""
    if name.startswith("cc_ObjectBase_"):
        return "cc_ObjectBase"
    if name.startswith("cc_InstAsst_"):
        return "cc_InstAsst"
    return name


def next_sequence(db, sequence_name: str):
    """获取单个新序列号（对齐 Go NextSequence）。

    :param db: pymongo Database 句柄
    """
    sequence_name = _redirect_table(sequence_name)
    coll = db["cc_idgenerator"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    doc = coll.find_one_and_update(
        {"_id": sequence_name},
        {
            "$inc": {"SequenceID": 1},
            "$setOnInsert": {"create_time": now},
            "$set": {"last_time": now},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return doc["SequenceID"]


def next_sequences(db, sequence_name: str, num: int):
    """批量获取新序列号（对齐 Go NextSequences）。

    为避免与事务会话耦合导致序列号重复，使用独立 context（此处直接用传入的 db）。
    """
    if num == 0:
        return []
    sequence_name = _redirect_table(sequence_name)
    coll = db["cc_idgenerator"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    doc = coll.find_one_and_update(
        {"_id": sequence_name},
        {
            "$inc": {"SequenceID": num},
            "$setOnInsert": {"create_time": now},
            "$set": {"last_time": now},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return [i - num + 1 + doc["SequenceID"] for i in range(num)]
