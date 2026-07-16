"""MongoDB 操作指标采集（对齐 Go common/metric 与 storage/dal/mongo/local/metric.go 的 mtc）。

Go 在每个 Find/Count/Insert/Update/Delete/Aggregate/Distinct/Index 操作前后
调用 ``mtc.collectOperCount / collectOperDuration / collectErrorCount``，
按 (集合, 操作) 维度累计次数、耗时、错误数。

Python 侧采用两条互补的采集路径：
  1. pymongo ``CommandListener``（见 app/common/mongo/monitor.py）在驱动层自动
     记录所有命令的耗时与成败，无需改动任何业务路由即可全量覆盖；
  2. 业务层也可直接调用本模块的 ``record`` 做更细粒度埋点。

指标线程安全，可通过 ``snapshot()`` 导出、``reset()`` 清零。
"""

import threading
from collections import defaultdict
from typing import Dict, Any


class MongoMetrics:
    def __init__(self):
        self._lock = threading.Lock()
        self._counts: Dict[tuple, int] = defaultdict(int)
        self._durations: Dict[tuple, float] = defaultdict(float)  # 秒
        self._errors: Dict[tuple, int] = defaultdict(int)

    def record(self, coll: str, op: str, duration_s: float, error: bool = False) -> None:
        """记录一次操作（对齐 Go mtc.collectOper*）。"""
        key = (coll, op)
        with self._lock:
            self._counts[key] += 1
            self._durations[key] += duration_s
            if error:
                self._errors[key] += 1

    def snapshot(self) -> Dict[str, Any]:
        """导出当前指标快照，key 形如 ``cc_HostBase/find``。"""
        with self._lock:
            out = {}
            for (coll, op), cnt in self._counts.items():
                total = self._durations[(coll, op)]
                out[f"{coll}/{op}"] = {
                    "count": cnt,
                    "total_ms": round(total * 1000, 2),
                    "avg_ms": round((total / cnt) * 1000, 2) if cnt else 0,
                    "errors": self._errors[(coll, op)],
                }
            return out

    def reset(self) -> None:
        with self._lock:
            self._counts.clear()
            self._durations.clear()
            self._errors.clear()


_metrics = MongoMetrics()


def get_metrics() -> MongoMetrics:
    """返回全局指标采集器（单例）。"""
    return _metrics
