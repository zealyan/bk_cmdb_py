#!/usr/bin/env python3
"""
MongoDB 数据初始化脚本
用于初始化 BK-CMDB 的业务拓扑等相关数据
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.db import init_mock_data, list_collections, get_collection_count, get_all_collections


def main():
    print("=" * 60)
    print("BK-CMDB MongoDB 数据初始化")
    print("=" * 60)
    
    try:
        # 1. 初始化数据
        print("\n[1/1] 开始初始化数据...")
        init_mock_data()
        print("✓ 数据初始化完成")
        
        print("\n" + "=" * 60)
        print("初始化完成！")
        print("=" * 60)
        
    except Exception as e:
        import traceback
        print(f"\n错误: {e}")
        print(f"堆栈: {traceback.format_exc()}")
        print("\n提示: 请确保 MongoDB 服务已启动并配置正确")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
