#!/usr/bin/env python3
"""MongoDB 引擎连接校验

用于确认 cmdb_server_py 能否正确连上 bk-cmdb 的 ``cmdb`` 实例。
不再假设存在本项目的 mock 集合（users / auth_policies / user_business），
而是直接校验引擎连通性并统计真实 ``cmdb`` 实例的关键集合。

用法：
    python3.11 check_db.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.db import is_mongo_available, list_collections, get_collection_count
from app.config import Config


# 真实 bk-cmdb initdb 会写入的核心集合（用于快速确认数据源就位）
CORE_COLLECTIONS = [
    "cc_ApplicationBase",
    "cc_SetBase",
    "cc_ModuleBase",
    "cc_HostBase",
    "cc_ModuleHostConfig",
    "cc_ObjAttDes",
    "cc_ObjectBase",
]


def main():
    print("=" * 60)
    print("BK-CMDB Python 后端 —— MongoDB 引擎连接校验")
    print("=" * 60)
    print(f"MONGODB_URI : {Config.MONGODB_URI}")
    print(f"MONGODB_DB  : {Config.MONGODB_DB}")

    if not is_mongo_available():
        print("\n✗ MongoDB 引擎不可用，请检查 MONGODB_URI / 实例状态")
        return 1

    print("\n✓ MongoDB 引擎连接有效")

    cols = set(list_collections())
    print(f"  集合总数: {len(cols)}")

    print("\n--- 核心集合（bk-cmdb initdb 产物）---")
    for c in CORE_COLLECTIONS:
        mark = "✓" if c in cols else "✗ 缺失"
        count = get_collection_count(c) if c in cols else 0
        print(f"  [{mark}] {c}: {count}")

    missing = [c for c in CORE_COLLECTIONS if c not in cols]
    if missing:
        print("\n⚠ 以下核心集合缺失，请确认 bk-cmdb 已完成 initdb：")
        for m in missing:
            print(f"    - {m}")
        return 1

    print("\n✓ 数据源（cmdb 实例）校验通过，项目可直接使用真实 CMDB 数据。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
