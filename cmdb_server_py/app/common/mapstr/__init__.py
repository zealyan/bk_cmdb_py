"""map 工具（对齐 Go common/mapstr 的 MapStr）。

提供带类型安全取值的字典子类，复刻 Go MapStr 的 String/Bool/Int64 等访问器，
避免各处散落的 ``doc.get(k) or default`` 与类型转换。
"""


class MapStr(dict):
    """带类型访问器的字典（对齐 Go common/mapstr.MapStr）。"""

    def String(self, key: str, default: str = "") -> str:
        v = self.get(key)
        return str(v) if v is not None else default

    def Bool(self, key: str, default: bool = False) -> bool:
        v = self.get(key, default)
        return bool(v)

    def Int64(self, key: str, default: int = 0) -> int:
        try:
            v = self.get(key, default)
            return int(v)
        except (ValueError, TypeError):
            return default

    def MapStr(self, key: str, default=None):
        v = self.get(key)
        if isinstance(v, dict):
            return MapStr(v)
        return default if default is not None else MapStr()
