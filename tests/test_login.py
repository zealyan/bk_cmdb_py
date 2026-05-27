#!/usr/bin/env python3
"""登录功能测试脚本

测试用户登录、密码加密、Token验证等功能。

Usage:
    # 测试密码加密功能（不需要服务器）
    python test_login.py
    
    # 测试登录接口（需要服务器运行）
    python test_login.py --api
"""

import sys
import os
import json
import requests

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE_URL = "http://localhost:8080"


def test_password_hashing():
    """测试密码加密功能"""
    print("\n" + "=" * 60)
    print("测试密码加密")
    print("=" * 60)
    
    from app.auth import hash_password, verify_password
    
    test_cases = [
        {"password": "admin", "should_pass": True},
        {"password": "tom123", "should_pass": True},
        {"password": "jelly123", "should_pass": True},
    ]
    
    all_passed = True
    for test in test_cases:
        password = test['password']
        hashed = hash_password(password)
        
        print(f"\n密码: {password}")
        print(f"加密后: {hashed[:60]}...")
        
        # 验证正确密码
        if verify_password(password, hashed):
            print(f"✓ 正确密码验证成功")
        else:
            print(f"✗ 正确密码验证失败")
            all_passed = False
        
        # 验证错误密码
        wrong_password = password + "wrong"
        if not verify_password(wrong_password, hashed):
            print(f"✓ 错误密码验证成功被拒绝")
        else:
            print(f"✗ 错误密码验证未被拒绝")
            all_passed = False
    
    return all_passed


def test_login_api():
    """测试登录 API 接口"""
    print("\n" + "=" * 60)
    print("测试登录 API")
    print("=" * 60)
    
    # 测试用例
    test_cases = [
        {
            "username": "admin",
            "password": "admin",
            "should_succeed": True,
            "description": "管理员正确密码登录"
        },
        {
            "username": "tom",
            "password": "tom123",
            "should_succeed": True,
            "description": "普通用户正确密码登录"
        },
        {
            "username": "admin",
            "password": "wrong_password",
            "should_succeed": False,
            "description": "错误密码登录"
        },
        {
            "username": "nonexistent",
            "password": "password",
            "should_succeed": False,
            "description": "不存在的用户"
        },
        {
            "username": "",
            "password": "admin",
            "should_succeed": False,
            "description": "空用户名"
        },
        {
            "username": "admin",
            "password": "",
            "should_succeed": False,
            "description": "空密码"
        },
    ]
    
    all_passed = True
    
    for test in test_cases:
        print(f"\n测试: {test['description']}")
        print(f"  用户名: {test['username'] or '<empty>'}")
        print(f"  密码: {test['password'] or '<empty>'}")
        
        try:
            response = requests.post(
                f"{BASE_URL}/user/auth",
                json={
                    "bk_username": test['username'],
                    "bk_password": test['password']
                },
                headers={"Content-Type": "application/json"}
            )
            
            data = response.json()
            print(f"  响应: {json.dumps(data, ensure_ascii=False)}")
            
            if test['should_succeed']:
                if data.get('result'):
                    print(f"  ✓ 登录成功")
                    token = data.get('data', {}).get('bk_token')
                    if token:
                        print(f"  ✓ 获取到 Token")
                    else:
                        print(f"  ✗ 未获取到 Token")
                        all_passed = False
                else:
                    print(f"  ✗ 登录失败")
                    all_passed = False
            else:
                if not data.get('result'):
                    print(f"  ✓ 登录被正确拒绝")
                else:
                    print(f"  ✗ 不应成功登录")
                    all_passed = False
        
        except Exception as e:
            print(f"  ✗ 请求失败: {str(e)}")
            all_passed = False
    
    return all_passed


def test_database_init():
    """测试数据库初始化"""
    print("\n" + "=" * 60)
    print("测试数据库初始化")
    print("=" * 60)
    
    from app.models.db import get_collection_count, get_mongo_collection, is_mongo_available
    from app.models.relational_db import get_table_count, list_tables
    
    all_passed = True
    
    # 检查 MongoDB
    if is_mongo_available():
        print("\nMongoDB:")
        user_count = get_collection_count('users')
        print(f"  用户数量: {user_count}")
        
        if user_count == 3:
            print(f"  ✓ 用户数量正确")
        else:
            print(f"  ✗ 用户数量不正确，期望 3，实际 {user_count}")
            all_passed = False
    else:
        print("\n✗ MongoDB 不可用")
        all_passed = False
    
    # 检查关系型数据库
    print("\n关系型数据库:")
    tables = list_tables()
    print(f"  表: {tables}")
    
    if 'users' in tables:
        user_count = get_table_count('users')
        print(f"  用户数量: {user_count}")
    
    return all_passed


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='登录功能测试')
    parser.add_argument('--api', action='store_true', help='测试 API（需要服务器运行）')
    args = parser.parse_args()
    
    print("\n" + "=" * 60)
    print("BK-CMDB 登录功能测试")
    print("=" * 60)
    
    passed = []
    
    # 测试密码加密（总是测试）
    passed.append(("密码加密", test_password_hashing()))
    
    # 测试数据库初始化（总是测试）
    passed.append(("数据库初始化", test_database_init()))
    
    # 测试登录 API（如果指定）
    if args.api:
        passed.append(("登录 API", test_login_api()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    all_passed = True
    for test_name, test_passed in passed:
        status = "✓ 通过" if test_passed else "✗ 失败"
        print(f"  {test_name}: {status}")
        if not test_passed:
            all_passed = False
    
    print("=" * 60)
    if all_passed:
        print("所有测试通过！")
        return 0
    else:
        print("部分测试失败！")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
