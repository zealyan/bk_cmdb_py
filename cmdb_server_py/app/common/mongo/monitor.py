"""PyMongo 命令监听 -> 指标采集（对齐 Go 每个操作的 mtc.collectOper*）。

Go 在每次 DB 操作前后手动埋点；Python 借助 pymongo 的 ``monitoring.CommandListener``
在**驱动层**自动捕获所有命令的耗时与成败，无需改动任何业务路由即可全量覆盖，
语义等价于 Go 的 ``mtc``。采集结果写入 ``app.common.metric`` 的全局采集器。
"""

import threading

from pymongo import monitoring

from app.common.metric import get_metrics

# pymongo 命令名 -> Go 风格操作名（对齐 Go metric.go 的 findOper/countOper/...）
_OP_MAP = {
    "find": "find",
    "getMore": "getMore",
    "insert": "insert",
    "update": "update",
    "delete": "delete",
    "findAndModify": "upsert",
    "aggregate": "aggregate",
    "count": "count",
    "distinct": "distinct",
    "createIndexes": "indexCreate",
    "dropIndexes": "indexDrop",
    "drop": "dropTable",
    "create": "createTable",
    "ping": "ping",
    "hello": "hello",
    "buildInfo": "buildInfo",
}


class MongoCommandListener(monitoring.CommandListener):
    """命令级监听器：记录每次操作的集合、操作类型、耗时与成败。"""

    def __init__(self):
        self._inflight = {}
        self._lock = threading.Lock()

    def started(self, event):
        cmd = getattr(event, "command", None)
        op = event.command_name
        coll = op
        if isinstance(cmd, dict):
            coll = cmd.get(op, next((v for v in cmd.values() if isinstance(v, str)), op))
        with self._lock:
            self._inflight[event.request_id] = (op, coll)

    def succeeded(self, event):
        op, coll = self._pop(event.request_id, event.command_name)
        get_metrics().record(coll, _OP_MAP.get(op, op), event.duration_micros / 1e6, error=False)

    def failed(self, event):
        op, coll = self._pop(event.request_id, event.command_name)
        get_metrics().record(coll, _OP_MAP.get(op, op), event.duration_micros / 1e6, error=True)

    def _pop(self, request_id, default_op):
        with self._lock:
            return self._inflight.pop(request_id, (default_op, default_op))
