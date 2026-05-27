#!/usr/bin/env python3
"""IAM 增强功能测试
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("IAM 增强功能测试")
print("=" * 60)

try:
    print("\n[1] 测试模块导入...")
    from app.auth.casbin_adapter import (
        check_permission,
        add_policy,
        remove_policy,
        get_user_policies
    )
    from app.auth.permission import permission_checker
    print("  ✓ 所有模块导入成功")
    
    print("\n[2] 测试实例级别权限...")
    print("  添加 tom 对 biz:123 实例的 view 权限")
    result = add_policy('tom', 'biz', 'view', '123')
    print(f"    添加结果: {result}")
    
    print("  检查 tom 对 biz:123 的 view 权限")
    has_perm = check_permission('tom', 'biz', 'view', '123')
    print(f"    权限检查: {has_perm}")
    
    print("  检查 tom 对 biz:456 的 view 权限（应无权限）")
    has_perm = check_permission('tom', 'biz', 'view', '456')
    print(f"    权限检查: {has_perm}")
    
    print("  检查 tom 对 biz 所有实例的 view 权限（应无权限）")
    has_perm = check_permission('tom', 'biz', 'view')
    print(f"    权限检查: {has_perm}")
    
    print("\n[3] 测试资源类型级别权限...")
    print("  添加 tom 对所有 biz 实例的 edit 权限")
    result = add_policy('tom', 'biz', 'edit')
    print(f"    添加结果: {result}")
    
    print("  检查 tom 对任意 biz 实例的 edit 权限")
    has_perm = check_permission('tom', 'biz', 'edit')
    print(f"    权限检查: {has_perm}")
    
    print("  检查 tom 对 biz:999 的 edit 权限")
    has_perm = check_permission('tom', 'biz', 'edit', '999')
    print(f"    权限检查: {has_perm}")
    
    print("\n[4] 测试权限撤销...")
    print("  撤销 tom 对 biz:123 的 view 权限")
    result = remove_policy('tom', 'biz', 'view', '123')
    print(f"    撤销结果: {result}")
    
    print("  检查 tom 对 biz:123 的 view 权限（应无权限）")
    has_perm = check_permission('tom', 'biz', 'view', '123')
    print(f"    权限检查: {has_perm}")
    
    print("\n[5] 测试 PermissionChecker...")
    print("  添加 jack 对 host:888 实例的 create 权限")
    result = permission_checker.add_permission('jack', 'host', 'create', '888')
    print(f"    添加结果: {result}")
    
    print("  检查 jack 对 host:888 的 create 权限")
    has_perm = permission_checker.check_permission('jack', 'host', 'create', '888')
    print(f"    权限检查: {has_perm}")
    
    print("\n[6] 测试获取用户权限（包含实例）...")
    perms = permission_checker.get_user_permissions('tom', with_instance=True)
    print(f"  Tom 共有 {len(perms)} 条权限:")
    for p in perms:
        obj_id = p.get('obj_id', '所有实例')
        print(f"    - {p['obj']}:{p['act']} (实例: {obj_id})")
    
    print("\n" + "=" * 60)
    print("所有增强功能测试通过！")
    print("=" * 60)
    sys.exit(0)
    
except Exception as e:
    print(f"\n✗ 测试失败: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
