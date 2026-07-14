"""
版本升级引擎 — 对齐 Go scene_server/admin_server/upgrader/

执行流程:
  1. 读取 cc_System 中 type="version" 的 current_version
  2. 按 VersionCmp 排序所有注册版本
  3. 跳过 ≤ current_version 的版本
  4. 逐一执行 > current_version 的版本
  5. 每次成功后更新 current_version 到 cc_System

版本排序规则（对齐 Go compare.go VersionCmp）:
  - 两者都以 "y" 开头 → 比较时间戳数字（y3.6.202002131522 → 202002131522）
  - 仅一个以 "y" 开头 → y > x > v（字母序，但 y 总是最大）
  - 其它（x*, v*）→ 按 LegacyMigrationVersion 硬编码顺序
"""

import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from pymongo import MongoClient

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.environ.get("MONGO_DB", "cmdb")


# Go register.go LegacyMigrationVersion — 硬编码的遗留版本执行顺序
LEGACY_ORDER = [
    "v3.0.8", "v3.0.9-beta.1", "v3.0.9-beta.3", "v3.1.0-alpha.2",
    "x08.09.04.01", "x08.09.11.01", "x08.09.13.01", "x08.09.17.01",
    "x08.09.18.01", "x08.09.26.01", "x18.09.30.01", "x18.10.10.01",
    "x18.10.30.01", "x18.10.30.02", "x18.11.19.01", "x18.12.12.01",
    "x18.12.12.02", "x18.12.12.03", "x18.12.12.04", "x18.12.12.05",
    "x18.12.12.06", "x18.12.13.01", "x18_12_13_02", "x19.01.18.01",
    "x19.02.15.10", "x19.04.16.01", "x19.04.16.02", "x19.04.16.03",
    "x19.05.16.01", "x19_05_22_01", "x19_08_19_01", "x19_08_20_01",
    "x19_08_26_02", "x19_09_03_01", "x19_09_03_02", "x19_09_03_03",
    "x19_09_03_04", "x19_09_03_05", "x19_09_03_06", "x19_09_03_07",
    "x19_09_03_08", "x19_09_06_01", "x19_09_27_01", "x19_10_09_01",
    "x19_10_22_01",
]


def get_ordered_versions(known_versions):
    """按 Go 顺序返回版本列表（legacy → y3.* 按时间戳）。"""
    legacy_set = set(LEGACY_ORDER)
    legacy = [v for v in LEGACY_ORDER if v in known_versions]
    y_versions = sorted(
        [v for v in known_versions if v.startswith("y") and v not in legacy_set],
        key=lambda v: v.split(".")[-1] if "." in v else v,
    )
    other = sorted([v for v in known_versions if v not in legacy_set and not v.startswith("y")])
    return legacy + y_versions + other


def get_db():
    client = MongoClient(MONGO_URI)
    return client[MONGO_DB]


def get_current_version(db):
    """读取 cc_System 中 type="version" 的 current_version（对齐 Go）。"""
    doc = db["cc_System"].find_one({"flag": "migrate_version"})
    if doc:
        return doc.get("version", doc.get("current_version", "v0.0.0"))
    doc = db["cc_System"].find_one({"type": "version"})
    if doc:
        return doc.get("current_version", "v0.0.0")
    return "v0.0.0"


def set_current_version(db, version):
    """记录当前版本到 cc_System。"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db["cc_System"].update_one(
        {"flag": "migrate_version"},
        {"$set": {"flag": "migrate_version", "version": version, "last_time": now_str}},
        upsert=True,
    )


def run_all():
    db = get_db()
    current = get_current_version(db)
    print(f"[Upgrader] 当前版本: {current}")

    # 收集可用版本模块
    from importlib import import_module
    known = set()
    versions_dir = os.path.join(os.path.dirname(__file__), "versions")
    for f in os.listdir(versions_dir):
        if f.endswith(".py") and f != "__init__.py":
            # 把 v3_0_8 → v3.0.8
            name = f[:-3]
            ver = name.replace("_", ".")
            known.add(ver)
    
    ordered = get_ordered_versions(known)
    pending = [v for v in ordered if v > current]
    
    if not pending:
        print("[Upgrader] 已为最新版本")
        return
    
    print(f"[Upgrader] 共 {len(ordered)} 个版本，待执行 {len(pending)} 个: {pending[0]} → {pending[-1]}")
    
    for version in pending:
        mod_name = version.replace(".", "_")
        # 特殊处理：x18_12_13_02 和 x19_* 等下划线版本
        mod_name = re.sub(r'(?<=[a-z0-9])-(?=[0-9a-z])', '_', mod_name)
        
        print(f"  → {version}...", end=" ")
        try:
            mod = import_module(f"migrate.versions.{mod_name}")
            if hasattr(mod, "up"):
                mod.up(db)
            print("✓")
        except ModuleNotFoundError:
            print("∅ (跳过)")
        except Exception as e:
            print(f"✗ {e}")
            import traceback; traceback.print_exc()
            raise
        
        set_current_version(db, version)
    
    print(f"[Upgrader] 完成，当前版本: {pending[-1]}")


if __name__ == "__main__":
    run_all()
