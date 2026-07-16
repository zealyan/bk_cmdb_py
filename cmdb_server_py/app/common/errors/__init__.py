"""错误分类（对齐 Go storage/driver/mongodb/monogdb.go 的 IsDuplicatedError /
IsNotFoundError / GetDuplicateKey / GetDuplicateValue）。

复刻 Go 基于错误字符串的关键字匹配逻辑，便于在 Python 侧统一判定
「重复键」「文档不存在」等业务语义错误。
"""

from app.common.types import ErrDocumentNotFound, ErrDuplicated

# Go IsDuplicatedError 识别的关键字集合
_DUP_MARKERS = (
    "The existing index",
    "There's already an index with name",
    "E11000 duplicate",
    "IndexOptionsConflict",
    "all indexes already exist",
    "already exists with a different name",
)


def is_duplicated_error(err) -> bool:
    """判定是否为 MongoDB 重复键（唯一索引冲突）错误。"""
    if err is None:
        return False
    if err is ErrDuplicated:
        return True
    msg = str(err)
    return any(marker in msg for marker in _DUP_MARKERS)


def is_not_found_error(err) -> bool:
    """判定是否为文档不存在错误。"""
    return err is ErrDocumentNotFound


def get_duplicate_key(err) -> str:
    """从重复键错误中提取 dup key 片段（对齐 Go GetDuplicateKey）。

    原始错误形如：
        ...E11000 duplicate key error collection: cmdb.cc_xxx index: ...
        dup key: { bk_inst_name: "xxx" }]}...
    返回 ``{ bk_inst_name: "xxx" }`` 部分；若不是重复键错误，返回原始错误串。
    """
    if err is None:
        return ""
    msg = str(err)
    if "E11000 duplicate" not in msg:
        return msg
    start = msg.find("dup key: ")
    if start == -1:
        return msg
    start += len("dup key: ")
    end = msg.rfind("}]},")
    if end == -1 or end < start:
        return msg
    return msg[start:end]


def get_duplicate_value(field: str, err) -> str:
    """从重复键错误中提取指定字段的重复值（对齐 Go GetDuplicateValue）。"""
    if not field or err is None:
        return ""
    msg = str(err)
    if "E11000 duplicate" not in msg:
        return msg
    marker = "dup key: { " + field + ": "
    start = msg.find(marker)
    if start == -1:
        return msg
    start += len(marker)
    end = msg.rfind(" }")
    if end == -1 or end < start:
        return msg
    return msg[start:end]
