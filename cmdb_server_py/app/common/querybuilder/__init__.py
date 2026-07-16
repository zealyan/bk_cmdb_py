"""查询构造（对齐 Go common/querybuilder）。

提供把常见查询参数（等值过滤、排序字符串）转换成 pymongo 兼容结构的小工具，
复刻 Go querybuilder 中最常用的构建能力。
"""


def build_filter(**kwargs) -> dict:
    """仅保留非 None 的等值条件，产出 filter dict。"""
    return {k: v for k, v in kwargs.items() if v is not None}


def build_sort(sort_str: str):
    """把排序字符串解析成 pymongo 的 sort 列表。

    支持两种写法（与 Go 一致）：
      * ``"host_id,-host_name"``
      * ``"host_id:1, host_name:-1"``
    均表示先按 host_id 升序、再按 host_name 降序。
    """
    out = []
    if not sort_str:
        return out
    for item in sort_str.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            key, direction = item.split(":", 1)
            key = key.strip()
            direction = direction.strip()
            out.append((key, -1 if direction == "-1" else 1))
        else:
            key = item.lstrip("+-").strip()
            out.append((key, -1 if item.startswith("-") else 1))
    return out


def build_projection(fields) -> dict:
    """把字段列表转成 pymongo projection（1=包含）。"""
    if not fields:
        return None
    return {f: 1 for f in fields if f}
