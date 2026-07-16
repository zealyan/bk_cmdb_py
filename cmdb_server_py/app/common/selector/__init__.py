"""标签选择器（对齐 Go common/selector）。

将 Kubernetes 风格的资源标签选择器转换为 MongoDB 过滤条件，主要作用于
``labels.<key>`` 字段。覆盖 Go 的 ``Selector`` / ``Selectors`` / ``Labels`` 及
相关请求选项结构。
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.common.types import BK_DB_AND, BK_DB_EXISTS, BK_DB_IN, BK_DB_NE, BK_DB_NIN

# ---------------------------------------------------------------------------
# 操作符（对应 Go selector.Operator 常量）
# ---------------------------------------------------------------------------

DOES_NOT_EXIST = "!"
EQUALS = "="
IN = "in"
NOT_EQUALS = "!="
NOT_IN = "notin"
EXISTS = "exists"

AVAILABLE_OPERATORS = [DOES_NOT_EXIST, EQUALS, IN, NOT_EQUALS, NOT_IN, EXISTS]


# ---------------------------------------------------------------------------
# 标签键/值语法（对应 Go LabelNGKeyRule / LabelNGValueRule，K8s 风格）
# ---------------------------------------------------------------------------

_LABEL_NG_KEY_RE = re.compile(r"^[a-zA-Z]([a-z0-9A-Z\-_.]*[a-z0-9A-Z])?$")
_LABEL_NG_VALUE_RE = re.compile(r"^[a-z0-9A-Z]([a-z0-9A-Z\-_.]*[a-z0-9A-Z])?$")
_MAX_LABEL_LEN = 63


class SelectorError(Exception):
    """选择器校验失败（携带出错字段名，对齐 Go ``(string, error)`` 返回）。"""


@dataclass
class Selector:
    """单条标签选择器（对应 Go selector.Selector）。"""

    key: str = ""
    operator: str = EQUALS
    values: List[str] = field(default_factory=list)

    def validate(self) -> Tuple[str, Optional[str]]:
        """校验并返回 ``(出错字段, 错误信息)``（对齐 Go ``Validate() (string, error)``）。"""
        if self.operator not in AVAILABLE_OPERATORS:
            return "operator", f"operator {self.operator!r} not available, available: {AVAILABLE_OPERATORS}"
        if self.operator in (IN, NOT_IN) and len(self.values) == 0:
            return "values", "values shouldn't be empty"
        if self.operator in (EXISTS, DOES_NOT_EXIST) and len(self.values) > 0:
            return "values", "values should be empty"
        if self.operator in (EQUALS, NOT_EQUALS) and len(self.values) != 1:
            return "values", "values field length for equal operation should be exactly one"
        if not _LABEL_NG_KEY_RE.match(self.key):
            return "key", f"key {self.key!r} invalid"
        return "", None

    def to_mgo_filter(self) -> Dict[str, object]:
        """转换为 MongoDB 过滤条件（对应 Go ``ToMgoFilter``）。"""
        fld = "labels." + self.key
        if self.operator == IN:
            return {fld: {BK_DB_IN: list(self.values)}}
        if self.operator == NOT_IN:
            return {fld: {BK_DB_NIN: list(self.values)}}
        if self.operator in (EXISTS, DOES_NOT_EXIST):
            return {fld: {BK_DB_EXISTS: self.operator == EXISTS}}
        if self.operator == EQUALS:
            if not self.values:
                raise ValueError("values empty")
            return {fld: self.values[0]}
        if self.operator == NOT_EQUALS:
            if not self.values:
                raise ValueError("values empty")
            return {fld: {BK_DB_NE: self.values[0]}}
        return {}


@dataclass
class Selectors:
    """多条选择器（对应 Go selector.Selectors）。"""

    items: List[Selector] = field(default_factory=list)

    def validate(self) -> Tuple[str, Optional[str]]:
        for s in self.items:
            key, err = s.validate()
            if err is not None:
                return key, err
        return "", None

    def to_mgo_filter(self) -> Dict[str, object]:
        """多条以 ``$and`` 组合（对应 Go ``Selectors.ToMgoFilter``）。"""
        filters = [s.to_mgo_filter() for s in self.items]
        if not filters:
            return {}
        if len(filters) == 1:
            return filters[0]
        return {BK_DB_AND: filters}


# 兼容 Go 的 ``Selectors`` 作为列表的用法
SelectorsList = List[Selector]


@dataclass
class Labels:
    """标签集合（对应 Go selector.Labels = map[string]string）。"""

    data: Dict[str, str] = field(default_factory=dict)

    def validate(self) -> Tuple[str, Optional[str]]:
        """校验键/值语法与长度（对齐 Go ``Labels.Validate``）。"""
        for key, value in self.data.items():
            if not _LABEL_NG_KEY_RE.match(key):
                return key, f"key: {key!r} format error"
            if len(key) >= _MAX_LABEL_LEN:
                return key, f"key: {key!r} exceed max length {_MAX_LABEL_LEN - 1}"
            field_name = f"{key}:{value}"
            if not _LABEL_NG_VALUE_RE.match(value):
                return field_name, f"value: {field_name!r} format error"
            if len(value) >= _MAX_LABEL_LEN:
                return field_name, f"value: {field_name!r} exceed max length {_MAX_LABEL_LEN - 1}"
        return "", None

    def add_label(self, other: "Labels") -> None:
        """合并标签（对应 Go ``AddLabel``）。"""
        self.data.update(other.data)

    def remove_label(self, keys: List[str]) -> None:
        """移除指定键（对应 Go ``RemoveLabel``）。"""
        for k in keys:
            self.data.pop(k, None)

    # dict 风格便捷访问
    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def get(self, key, default=None):
        return self.data.get(key, default)

    def items(self):  # type: ignore[override]
        return self.data.items()


@dataclass
class LabelInstance:
    """带标签的实例（对应 Go selector.LabelInstance）。"""

    labels: Labels = field(default_factory=Labels)


# ---------------------------------------------------------------------------
# 请求选项结构（对应 Go selector 的 *Option / *Request）
# ---------------------------------------------------------------------------

@dataclass
class LabelAddOption:
    instance_ids: List[int] = field(default_factory=list)
    labels: Labels = field(default_factory=Labels)


@dataclass
class LabelUpdateOption:
    instance_ids: List[int] = field(default_factory=list)
    labels: Labels = field(default_factory=Labels)


@dataclass
class LabelRemoveOption:
    instance_ids: List[int] = field(default_factory=list)
    keys: List[str] = field(default_factory=list)


@dataclass
class LabelAddRequest:
    option: LabelAddOption = field(default_factory=LabelAddOption)
    table_name: str = ""


@dataclass
class LabelUpdateRequest:
    option: LabelUpdateOption = field(default_factory=LabelUpdateOption)
    table_name: str = ""


@dataclass
class LabelRemoveRequest:
    option: LabelRemoveOption = field(default_factory=LabelRemoveOption)
    table_name: str = ""


@dataclass
class SvcInstLabelAddOption(LabelAddOption):
    bk_biz_id: int = 0


@dataclass
class SvcInstLabelUpdateOption(LabelUpdateOption):
    bk_biz_id: int = 0


@dataclass
class SvcInstLabelRemoveOption(LabelRemoveOption):
    bk_biz_id: int = 0
