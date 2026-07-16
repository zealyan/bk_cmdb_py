"""通用工具（对齐 Go common/util 的常用函数）。

抽取与 MongoDB 数据访问相关的两个原语：
  * ConverToInterfaceSlice：把单个文档 / 文档列表统一成 list（对应 Go util.ConverToInterfaceSlice）。
  * GetInt32ByInterface：把接口值安全地转成 int（对应 Go util.GetInt32ByInterface）。
"""

from typing import Any, List


def conver_to_interface_slice(docs: Any) -> List[Any]:
    """单个文档或文档列表统一成 list（保证 Insert/Update 多文档语义一致）。"""
    if docs is None:
        return []
    if isinstance(docs, (list, tuple, set)):
        return list(docs)
    return [docs]


def get_int32_by_interface(v: Any) -> int:
    """把接口值转成 int；无法转换时回退为 0（对齐 Go 的容错语义）。"""
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str):
        try:
            return int(float(v))
        except (ValueError, TypeError):
            return 0
    return 0
