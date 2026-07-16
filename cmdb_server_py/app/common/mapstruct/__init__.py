"""结构体与字典互转（对齐 Go common/mapstruct）。

Go 侧用 ``mapstructure`` 做 map↔struct 转换；Python 为动态语言，这里以
**dataclass 字段声明** 作为「struct schema」，提供等价的转换与钩子能力：

  * :func:`struct_to_map`    —— struct → map（json 往返，对齐 ``Struct2Map``）
  * :func:`map_to_struct`    —— map → struct（对齐 ``Decode2Struct``）
  * :func:`map_to_struct_with_hook` —— 带钩子（对齐 ``Decode2StructWithHook``，
    内置 duration 字符串 → 秒 的钩子，等价于 Go 的 ``StringToTimeDurationHookFunc``）
"""

import json
import re
from dataclasses import asdict, dataclass, fields, is_dataclass
from typing import Any, Callable, Dict, Optional, Type, TypeVar

T = TypeVar("T")

_DURATION_RE = re.compile(
    r"^\s*(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>ns|us|µs|ms|s|m|h|d|w)\s*$"
)
_UNIT_SECONDS = {
    "ns": 1e-9, "us": 1e-6, "µs": 1e-6, "ms": 1e-3,
    "s": 1.0, "m": 60.0, "h": 3600.0, "d": 86400.0, "w": 604800.0,
}


def parse_duration(text: str) -> float:
    """解析 Go 风格时长字符串为秒（对齐 ``time.Duration`` 解析）。

    支持 ``ns/us/µs/ms/s/m/h/d/w``，如 ``"5s"`` → ``5.0``、``"1h30m"`` 暂不支持
    复合写法（与 Go 一致，仅识别单一单位）。非时长字符串原样返回。
    """
    if not isinstance(text, str):
        return text
    m = _DURATION_RE.match(text)
    if not m:
        return text
    return float(m.group("value")) * _UNIT_SECONDS[m.group("unit")]


def struct_to_map(v: Any) -> Dict[str, Any]:
    """struct → map（对齐 Go ``Struct2Map``：json marshal 后再 unmarshal）。

    dataclass 经 ``asdict`` 先转为原生 dict；datetime/ObjectId 等非 JSON 原生
    类型会经 ``default=str`` 序列化，确保输出为纯 JSON 可表达的映射。
    """
    if is_dataclass(v) and not isinstance(v, type):
        v = asdict(v)
    return json.loads(json.dumps(v, default=str))


def _dataclass_fields(cls: Type) -> Dict[str, Any]:
    if not is_dataclass(cls):
        raise TypeError(f"{cls!r} 不是 dataclass，map_to_struct 仅支持 dataclass")
    return {f.name: f.type for f in fields(cls)}


def map_to_struct(data: Dict[str, Any], cls: Type[T]) -> T:
    """map → struct（对齐 Go ``Decode2Struct``，弱类型输入）。

    仅取 ``cls`` 声明字段中存在于 ``data`` 的键，忽略多余键；不触发钩子。
    """
    schema = _dataclass_fields(cls)
    kwargs = {name: data[name] for name in schema if name in data}
    return cls(**kwargs)


def map_to_struct_with_hook(
    data: Dict[str, Any],
    cls: Type[T],
    duration_fields: Optional[list] = None,
    hooks: Optional[Dict[str, Callable[[Any], Any]]] = None,
) -> T:
    """map → struct 并应用钩子（对齐 Go ``Decode2StructWithHook``）。

    :param duration_fields: 这些字段若值为时长字符串（如 ``"5s"``），自动转为秒。
    :param hooks: 其它字段级钩子 ``{字段名: callable(value)->new_value}``。
    """
    schema = _dataclass_fields(cls)
    duration_fields = set(duration_fields or [])
    hooks = hooks or {}

    kwargs: Dict[str, Any] = {}
    for name in schema:
        if name not in data:
            continue
        value = data[name]
        if name in duration_fields and isinstance(value, str):
            value = parse_duration(value)
        if name in hooks:
            value = hooks[name](value)
        kwargs[name] = value
    return cls(**kwargs)


# 兼容 Go 命名风格（驼峰别名）
Decode2Struct = map_to_struct
Decode2StructWithHook = map_to_struct_with_hook
Struct2Map = struct_to_map
