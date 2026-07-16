"""类型与错误哨兵（对齐 Go common/types 与 storage/dal/types）。

仅抽取与 MongoDB 数据访问最相关的常量与错误哨兵；完整 Go 类型体系按需补充。
"""

# ---------------------------------------------------------------------------
# 错误哨兵（对应 Go storage/dal/types.ErrDocumentNotFound / ErrDuplicated）
# 使用轻量异常类型，便于 is_not_found_error / is_duplicated_error 做身份判断。
# ---------------------------------------------------------------------------


class _SentinelBase(Exception):
    """哨兵基类：允许通过 ``err is ErrXxx`` 做精确身份判断。"""

    def __repr__(self):
        return self.__class__.__name__


def _make_sentinel(name):
    return type(name, (_SentinelBase,), {})


ErrDocumentNotFound = _make_sentinel("ErrDocumentNotFound")
ErrDuplicated = _make_sentinel("ErrDuplicated")


# ---------------------------------------------------------------------------
# 读偏好模式（对应 Go common 的 read preference 常量）
# ---------------------------------------------------------------------------


class ReadPreferenceMode:
    NIL = "nil"
    PRIMARY = "primary"
    PRIMARY_PREFERRED = "primaryPreferred"
    SECONDARY = "secondary"
    SECONDARY_PREFERRED = "secondaryPreferred"
    NEAREST = "nearest"


# ---------------------------------------------------------------------------
# 常用集合名常量（对应 Go common 的 BKTableName*，按需补充）
# ---------------------------------------------------------------------------

BK_TABLE_NAME_BASE_HOST = "cc_HostBase"
BK_TABLE_NAME_BASE_APP = "cc_ApplicationBase"
BK_TABLE_NAME_BASE_SET = "cc_SetBase"
BK_TABLE_NAME_BASE_MODULE = "cc_ModuleBase"
BK_TABLE_NAME_MODULE_HOST_CONFIG = "cc_ModuleHostConfig"
BK_TABLE_NAME_INST_ASST = "cc_InstAsst"
BK_TABLE_NAME_BASE_INST = "cc_BaseInst"
BK_TABLE_NAME_DEL_ARCHIVE = "cc_DelArchive"
BK_TABLE_NAME_ID_GENERATOR = "cc_idgenerator"


# ---------------------------------------------------------------------------
# MongoDB 操作符常量（对应 Go common.BKDB*）
# ---------------------------------------------------------------------------

BK_DB_IN = "$in"
BK_DB_NIN = "$nin"
BK_DB_EXISTS = "$exists"
BK_DB_NE = "$ne"
BK_DB_AND = "$and"
