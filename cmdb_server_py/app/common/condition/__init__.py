"""查询条件（对齐 Go common/condition 的 Condition）。

Go 的 Condition 是一套可组合的查询条件构造器；这里提供等价的轻量实现，
支持 Eq / In / Ne / Gt / Lt / Regex 等常用条件，并最终产出 pymongo 兼容的 filter dict。
"""


class Condition:
    def __init__(self):
        self.fields = {}

    def Field(self, name: str) -> "Condition":
        self.fields.setdefault(name, {})
        return self

    def Eq(self, name: str, val) -> "Condition":
        self.fields[name] = val
        return self

    def Ne(self, name: str, val) -> "Condition":
        self.fields[name] = {"$ne": val}
        return self

    def In(self, name: str, vals) -> "Condition":
        self.fields[name] = {"$in": list(vals)}
        return self

    def Nin(self, name: str, vals) -> "Condition":
        self.fields[name] = {"$nin": list(vals)}
        return self

    def Gt(self, name: str, val) -> "Condition":
        self.fields[name] = {"$gt": val}
        return self

    def Gte(self, name: str, val) -> "Condition":
        self.fields[name] = {"$gte": val}
        return self

    def Lt(self, name: str, val) -> "Condition":
        self.fields[name] = {"$lt": val}
        return self

    def Lte(self, name: str, val) -> "Condition":
        self.fields[name] = {"$lte": val}
        return self

    def Regex(self, name: str, pattern: str) -> "Condition":
        self.fields[name] = {"$regex": pattern}
        return self

    def to_filter(self) -> dict:
        return dict(self.fields)
