#!/usr/bin/env python3

"""数据初始化脚本（已废弃 mock 播种）

本项目不再向本地库写入任何 mock 数据。所有 CMDB 业务拓扑 / 主机 / 模型数据
均来自 bk-cmdb 通过 initdb 写入的 ``cmdb`` MongoDB 实例。

本脚本仅用于：

  * 校验 MongoDB 引擎连接是否有效；
  * 打印当前数据库（应为 ``cmdb``）及其集合概况。

若需重建 bk-cmdb 的初始化数据，请使用 bk-cmdb 官方的 initdb 流程，而非本脚本。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.db import is_mongo_available, list_collections, get_collection_count


def main():
    print("=" * 60)
    print("BK-CMDB Python 后端 —— 数据源校验（无 mock 初始化）")
    print("=" * 60)

    if not is_mongo_available():
        print("✗ MongoDB 引擎不可用，请检查 MONGODB_URI 与实例状态")
        return 1

    from app.config import Config
    print(f"✓ MongoDB 引擎连接有效，当前数据库: {Config.MONGODB_DB}")
    collections = list_collections()
    print(f"  集合数量: {len(collections)}")
    for name in sorted(collections):
        print(f"    - {name}: {get_collection_count(name)}")
    print("=" * 60)
    print("提示: 业务/主机/模型数据由 bk-cmdb initdb 维护，无需本脚本播种。")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
