"""日志封装（对齐 Go common/blog）。

Go 的 blog 提供带 V(level) 分级的日志；这里用标准 logging 封装等价的
Infof / Errorf / V(level).Infof 接口，便于后续代码沿用统一日志入口。
"""

import logging

logger = logging.getLogger("cmdb_server_py")


def Infof(fmt: str, *args) -> None:
    logger.info(fmt, *args)


def Errorf(fmt: str, *args) -> None:
    logger.error(fmt, *args)


def Warnf(fmt: str, *args) -> None:
    logger.warning(fmt, *args)


class _VLogger:
    """对齐 Go blog.V(level) 返回的带级别日志器。"""

    def __init__(self, level: int):
        self.level = level

    def Infof(self, fmt: str, *args) -> None:
        if self.level <= 4:
            logger.debug(fmt, *args)

    def InfoDepthf(self, _depth: int, fmt: str, *args) -> None:
        if self.level <= 4:
            logger.debug(fmt, *args)


def V(level: int) -> _VLogger:
    return _VLogger(level)
