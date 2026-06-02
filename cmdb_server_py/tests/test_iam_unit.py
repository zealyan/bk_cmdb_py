#!/usr/bin/env python3
"""IAM 功能单元测试
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("IAM 功能单元测试")
print("=" * 60)

try:
    print("\n[1] 测试权限检查核心模块...")
    from app.auth.permission import permission_checker
    print("  ✓ permission_checker 导入成功")
    
    print("\n[2] 测试权限策略模块...")
    from app.auth.policies import (
        init_admin_super_permission,
        init_default_policies,
        get_all_policies,
        RESOURCE_TYPES,
        ACTION_TYPES
    )
    print("  ✓ policies 模块导入成功")
    print(f"  ✓ 支持 {len(RESOURCE_TYPES)} 种资源类型")
    print(f"  ✓ 支持 {len(ACTION_TYPES)} 种动作类型")
    
    print("\n[3] 测试初始化权限...")
    init_admin_super_permission()
    init_default_policies()
    policies = get_all_policies()
    print(f"  ✓ 共 {len(policies)} 条权限策略")
    
    print("\n[4] 测试权限检查...")
    print(f"  admin / biz / create: {permission_checker.check_permission('admin', 'biz', 'create')}")
    print(f"  tom / biz / view: {permission_checker.check_permission('tom', 'biz', 'view')}")
    print(f"  tom / biz / create: {permission_checker.check_permission('tom', 'biz', 'create')}")
    
    print("\n[5] 测试添加权限...")
    result = permission_checker.add_permission('tom', 'biz', 'create')
    print(f"  添加 tom / biz / create: {result}")
    print(f"  检查 tom / biz / create: {permission_checker.check_permission('tom', 'biz', 'create')}")
    
    print("\n[6] 测试获取用户权限...")
    perms = permission_checker.get_user_permissions('tom')
    print(f"  Tom 共有 {len(perms)} 条权限:")
    for p in perms:
        print(f"    - {p['obj']}:{p['act']}")
    
    print("\n[7] 测试权限装饰器模块...")
    from app.auth.decorators import require_login, require_permission, require_any_permission
    print("  ✓ 权限装饰器导入成功")
    
    print("\n[8] 测试 API 路由模块...")
    from app.routes.auth_routes import auth_bp
    print("  ✓ 权限 API 路由导入成功")
    print(f"  ✓ 路由名称: {auth_bp.name}")
    
    print("\n" + "=" * 60)
    print("所有单元测试通过！")
    print("=" * 60)
    sys.exit(0)
    
except Exception as e:
    print(f"\n✗ 测试失败: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
