#!/usr/bin/env python3
"""
MongoDB 数据初始化脚本（已废弃 mock 播种）

本项目统一使用 bk-cmdb 通过 initdb 写入的 ``cmdb`` MongoDB 实例，
本脚本不再向本地库写入任何仿真数据，仅做连接与数据概况校验。

若需重建 bk-cmdb 初始化数据，请使用 bk-cmdb 官方 initdb 流程。
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.db import is_mongo_available, list_collections, get_collection_count


def main():
    print("=" * 60)
    print("BK-CMDB MongoDB 数据源校验（无 mock 初始化）")
    print("=" * 60)

    if not is_mongo_available():
        print("✗ MongoDB 引擎不可用，请检查 MONGODB_URI 与实例状态")
        print("提示: 请确保 MongoDB 服务已启动并配置正确")
        return 1

    from app.config import Config
    print(f"✓ MongoDB 引擎连接有效，当前数据库: {Config.MONGODB_DB}")
    collections = list_collections()
    print(f"  集合数量: {len(collections)}")
    for name in sorted(collections):
        print(f"    - {name}: {get_collection_count(name)}")

    print("\n" + "=" * 60)
    print("校验完成（无数据写入）。真实数据由 bk-cmdb initdb 维护。")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
