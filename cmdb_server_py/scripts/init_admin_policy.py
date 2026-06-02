#!/usr/bin/env python3
"""权限策略初始化脚本

初始化 admin 超级权限和默认权限策略。

Usage:
    python scripts/init_admin_policy.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.auth.policies import (
    init_admin_super_permission,
    init_default_policies,
    get_all_policies
)
from app.models.db import is_mongo_available


def main():
    """主函数"""
    print("=" * 60)
    print("权限策略初始化")
    print("=" * 60)
    
    if not is_mongo_available():
        print("错误: MongoDB 不可用")
        return 1
    
    print("\n[1] 初始化 admin 超级权限...")
    init_admin_super_permission()
    
    print("\n[2] 初始化默认权限...")
    init_default_policies()
    
    print("\n[3] 验证权限策略...")
    policies = get_all_policies()
    print(f"共初始化 {len(policies)} 条权限策略")
    
    print("\n" + "=" * 60)
    print("权限初始化完成")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
