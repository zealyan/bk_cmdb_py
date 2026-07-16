"""生成对齐 Go v3.10.50 (145 属性 / 11 对象) 的 attributes.py

数据源: /tmp/extract_out.txt (由 Go upgrader 全量跑出权威终态)
"""
import re
import json

SRC = "/tmp/extract_out.txt"
OUT = "/workspace/bk_cmdb_py/cmdb_server_py/migrate/data/attributes.py"

OBJMAP = {
    "bk_switch": "switch",
    "bk_router": "router",
    "bk_load_balance": "load_balance",
    "bk_firewall": "firewall",
}
GRPMAP = {
    "default": "base",
    "proc_mgr": "none",
    "proc_port": "port",
    "auto": "auto",
    "role": "role",
}
# Python 体系既有 13 条被 Go 重命名/删除/合并的旧属性，需定向清理以保证总数=145
STALE_KEYS = [
    ("biz", "bk_maintainers"),
    ("biz", "bk_operator"),
    ("biz", "bk_productpm"),
    ("biz", "bk_tester"),
    ("host", "bk_cpu_mhz"),
    ("module", "bk_childid"),
    ("process", "auto_time_gap"),
    ("process", "bind_ip"),
    ("process", "bk_func_id"),
    ("process", "port"),
    ("process", "protocol"),
    ("set", "bk_childid"),
    ("set", "bk_parentid"),
]
OBJ_ORDER = ["biz", "set", "module", "host", "process", "plat",
             "switch", "router", "load_balance", "firewall", "bk_biz_set_obj"]


def transform_option(opt, ptype):
    if opt is None:
        return None
    if isinstance(opt, str):
        # singlechar 校验正则等 -> 沿用 Python 约定不落库
        return None
    if isinstance(opt, dict):
        cleaned = {k: v for k, v in opt.items() if v not in ("", None)}
        return cleaned  # 可能为 {}
    if isinstance(opt, list):
        if opt and isinstance(opt[0], dict):
            if "id" in opt[0]:
                # 枚举: {id, name, default}
                return [{"id": e["id"], "name": e["name"],
                         "default": bool(e.get("is_default", False))} for e in opt]
            # 其余(list of dict, 如 table 列定义) 原样保留
            return opt
        # list of strings (type=list, 如 bk_state)
        return opt
    return None


def build_attr(d):
    oid = OBJMAP.get(d["bk_obj_id"], d["bk_obj_id"])
    grp = GRPMAP.get(d.get("bk_property_group"), d.get("bk_property_group"))
    item = {
        "bk_obj_id": oid,
        "bk_property_id": d["bk_property_id"],
    }
    name = d.get("bk_property_name")
    if name not in (None, ""):
        item["bk_property_name"] = name
    item["bk_property_group"] = grp
    item["bk_property_type"] = d["bk_property_type"]
    opt = transform_option(d.get("option"), d["bk_property_type"])
    if opt is not None:
        item["option"] = opt
    item["isrequired"] = bool(d.get("isrequired"))
    item["isonly"] = bool(d.get("isonly"))
    item["editable"] = bool(d.get("editable"))
    item["isreadonly"] = bool(d.get("isreadonly"))
    item["ispre"] = bool(d.get("ispre"))
    item["bk_issystem"] = bool(d.get("bk_issystem"))
    item["bk_isapi"] = bool(d.get("bk_isapi"))
    unit = d.get("unit")
    if unit not in (None, ""):
        item["unit"] = unit
    return item


def fmt(item):
    s = json.dumps(item, ensure_ascii=False)
    # JSON bool/null -> Python 字面量（带前导空格的 token 不会误伤字符串内值）
    s = s.replace(" true", " True").replace(" false", " False").replace(" null", " None")
    return "        " + s


def main():
    txt = open(SRC, "r", encoding="utf-8").read()
    arr = json.loads(re.search(r"ATTRS_JSON_START\n(.*)\nATTRS_JSON_END", txt, re.S).group(1))
    attrs = [build_attr(d) for d in arr]

    # 分组并排序
    by_obj = {o: [] for o in OBJ_ORDER}
    for a in attrs:
        by_obj.setdefault(a["bk_obj_id"], []).append(a)
    ordered = []
    for o in OBJ_ORDER:
        ordered.extend(by_obj.get(o, []))
    # 兜底: 不在 OBJ_ORDER 中的对象
    for o, lst in by_obj.items():
        if o not in OBJ_ORDER:
            ordered.extend(lst)

    # 校验
    from collections import Counter
    cnt = Counter(a["bk_obj_id"] for a in ordered)
    print("total:", len(ordered))
    for o in OBJ_ORDER:
        print(f"  {o}: {cnt.get(o, 0)}")

    lines = []
    lines.append('"""')
    lines.append("对象属性数据迁移（全量 145 条，对齐 Go v3.10.50 / 11 对象）")
    lines.append("")
    lines.append("由 Go upgrader 全量链路跑出的权威终态生成；对象 ID 沿用 Python 体系约定")
    lines.append("（bk_switch->switch, bk_router->router, bk_load_balance->load_balance, bk_firewall->firewall）。")
    lines.append('"""')
    lines.append("from .. import BaseMigrate, get_timestamp, BK_DEFAULT_OWNER_ID, BK_SYSTEM_OPERATOR")
    lines.append("")
    lines.append("")
    lines.append("class AttributeMigrate(BaseMigrate):")
    lines.append('    """对象属性迁移（145 条，对齐 Go v3.10.50）"""')
    lines.append("")
    lines.append("    # Go 已重命名/删除/合并的旧属性，需定向清理以保证 cc_ObjAttDes 总数=145")
    lines.append("    STALE_KEYS = [")
    for k in STALE_KEYS:
        lines.append(f'        {list(k)},')
    lines.append("    ]")
    lines.append("")
    lines.append("    ATTRIBUTES = [")
    for a in ordered:
        lines.append(fmt(a) + ",")
    lines.append("    ]")
    lines.append("")
    lines.append("    def migrate(self) -> None:")
    lines.append('        self.ensure_collection("cc_ObjAttDes")')
    lines.append("        # 清理被 Go 重命名/删除的旧属性（幂等）")
    lines.append("        for oid, pid in self.STALE_KEYS:")
    lines.append('            self.db["cc_ObjAttDes"].delete_many({')
    lines.append('                "bk_obj_id": oid,')
    lines.append('                "bk_property_id": pid,')
    lines.append('                "bk_supplier_account": BK_DEFAULT_OWNER_ID,')
    lines.append("            })")
    lines.append("        ts = get_timestamp()")
    lines.append("        for idx, item in enumerate(self.ATTRIBUTES, start=1):")
    lines.append("            data = {**item,")
    lines.append('                "id": idx,')
    lines.append('                "bk_supplier_account": BK_DEFAULT_OWNER_ID,')
    lines.append('                "creator": BK_SYSTEM_OPERATOR,')
    lines.append('                "create_time": ts,')
    lines.append('                "last_time": ts,')
    lines.append("            }")
    lines.append('            self.upsert("cc_ObjAttDes", data, ["bk_obj_id", "bk_property_id", "bk_supplier_account"])')
    lines.append("")
    lines.append("")
    lines.append("def run_attribute_migrate(db) -> None:")
    lines.append("    AttributeMigrate(db).migrate()")
    lines.append('    print("Attribute migrate completed!")')
    lines.append("")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("written:", OUT)


if __name__ == "__main__":
    main()
