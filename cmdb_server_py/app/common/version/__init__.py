"""版本信息（对齐 Go common/version）。

仅移植常量与版本格式化能力，用于运维诊断与 ``--version`` 展示。
"""

# ---------------------------------------------------------------------------
# 版本常量（对应 Go common/version 的包级变量）
# ---------------------------------------------------------------------------

CC_VERSION = "17.03.28"
CC_TAG = "2017-03-28 Release"
CC_BRANCH = ""
CC_BUILD_TIME = "2017-03-28 19:50:00"
CC_GIT_HASH = "unknown"
CC_RUN_MODE = "product"          # product / test / dev
CC_DISTRO = "community"          # enterprise / community
CC_DISTRO_VERSION = "9999.9999.9999"
SERVICE_NAME = "unknown"

# 运行模式枚举（对应 Go CCRunMode*）
CC_RUN_MODE_PRODUCT = "product"
CC_RUN_MODE_TEST = "test"
CC_RUN_MODE_DEV = "dev"
CC_RUN_MODE_FOR_CI = "for_ci"

# 发行版枚举（对应 Go CCDistr*）
CC_DISTR_ENTERPRISE = "enterprise"
CC_DISTR_COMMUNITY = "community"

# 是否允许无模板创建 set/module（对应 Go CanCreateSetModuleWithoutTemplate）
CAN_CREATE_SET_MODULE_WITHOUT_TEMPLATE = True


def get_version() -> str:
    """返回格式化版本信息（对齐 Go GetVersion）。"""
    return (
        f"Version     : {CC_VERSION}\n"
        f"Tag         : {CC_TAG}\n"
        f"BuildTime   : {CC_BUILD_TIME}\n"
        f"GitHash     : {CC_GIT_HASH}\n"
        f"RunMode     : {CC_RUN_MODE}\n"
        f"Distribution: {CC_DISTRO}\n"
        f"ServiceName : {SERVICE_NAME}\n"
    )


def show_version() -> None:
    """打印版本信息（对齐 Go ShowVersion，匹配 ``--version`` 标志）。"""
    print(get_version())
