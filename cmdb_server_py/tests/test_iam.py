#!/usr/bin/env python3
"""IAM 功能测试脚本

测试权限检查、授予、撤销等功能。

Usage:
    python test_iam.py
"""

import sys
import requests

BASE_URL = "http://localhost:8080"


def get_token(username, password):
    """获取登录 Token"""
    response = requests.post(
        f"{BASE_URL}/user/auth",
        json={"bk_username": username, "bk_password": password}
    )
    
    data = response.json()
    return data.get("data", {}).get("bk_token")


def test_admin_permissions():
    """测试 admin 超级权限"""
    print("\n=== 测试 Admin 超级权限 ===")
    
    admin_token = get_token("admin", "admin")
    if not admin_token:
        print("✗ 无法获取 admin token")
        return
    
    print(f"Admin Token: {admin_token[:30]}...")
    
    response = requests.get(
        f"{BASE_URL}/auth/permissions",
        cookies={"bk_token": admin_token}
    )
    
    data = response.json()
    
    if data.get("result"):
        perms = data.get("data", {}).get("permissions", [])
        print(f"✓ Admin 拥有 {len(perms)} 条权限")
        
        resource_types = data.get("data", {}).get("resource_types", {})
        print(f"✓ 支持 {len(resource_types)} 种资源类型")
    else:
        print(f"✗ 获取权限失败: {data.get('message')}")


def test_user_permissions():
    """测试普通用户权限"""
    print("\n=== 测试普通用户权限 ===")
    
    tom_token = get_token("tom", "tom123")
    if not tom_token:
        print("✗ 无法获取 tom token")
        return
    
    print(f"Tom Token: {tom_token[:30]}...")
    
    response = requests.get(
        f"{BASE_URL}/auth/permissions",
        cookies={"bk_token": tom_token}
    )
    
    data = response.json()
    
    if data.get("result"):
        perms = data.get("data", {}).get("permissions", [])
        print(f"✓ Tom 拥有 {len(perms)} 条权限")
        
        for p in perms:
            print(f"  - {p['name']}")
    else:
        print(f"✗ 获取权限失败: {data.get('message')}")


def test_permission_check():
    """测试权限检查"""
    print("\n=== 测试权限检查 ===")
    
    admin_token = get_token("admin", "admin")
    tom_token = get_token("tom", "tom123")
    
    test_cases = [
        {"user": "admin", "token": admin_token, "obj": "biz", "act": "create", "expected": True},
        {"user": "tom", "token": tom_token, "obj": "biz", "act": "create", "expected": False},
        {"user": "tom", "token": tom_token, "obj": "host", "act": "view", "expected": True},
    ]
    
    for test in test_cases:
        response = requests.post(
            f"{BASE_URL}/auth/check",
            json={"obj": test["obj"], "act": test["act"]},
            cookies={"bk_token": test["token"]}
        )
        
        data = response.json()
        allowed = data.get("data", {}).get("allowed", False)
        
        if allowed == test["expected"]:
            print(f"✓ {test['user']} {test['obj']}:{test['act']} = {allowed}")
        else:
            print(f"✗ {test['user']} {test['obj']}:{test['act']} 预期 {test['expected']}，实际 {allowed}")


def test_permission_grant():
    """测试权限授予"""
    print("\n=== 测试权限授予 ===")
    
    admin_token = get_token("admin", "admin")
    
    response = requests.post(
        f"{BASE_URL}/auth/grant",
        json={"username": "tom", "obj": "biz", "act": "create"},
        cookies={"bk_token": admin_token}
    )
    
    data = response.json()
    
    if data.get("result"):
        print("✓ 权限授予成功")
    else:
        print(f"✗ 权限授予失败: {data.get('message')}")


def main():
    print("=" * 60)
    print("IAM 权限管理功能测试")
    print("=" * 60)
    
    try:
        test_admin_permissions()
        test_user_permissions()
        test_permission_check()
        test_permission_grant()
    except requests.exceptions.ConnectionError:
        print("\n⚠ 服务器未启动，跳过 API 测试")
        print("请先启动服务器: python app.py")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
