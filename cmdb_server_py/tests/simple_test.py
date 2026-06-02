#!/usr/bin/env python3
"""简单测试脚本，不依赖 requests"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("BK-CMDB 登录功能 - 简单测试")
print("=" * 60)


def test_password_hashing():
    """测试密码加密功能"""
    print("\n测试密码加密:")
    
    from app.auth import hash_password, verify_password
    
    test_cases = ["admin", "tom123", "jelly123"]
    
    all_passed = True
    for password in test_cases:
        hashed = hash_password(password)
        
        print(f"\n  密码: {password}")
        print(f"  加密后: {hashed[:60]}...")
        
        # 验证正确密码
        if verify_password(password, hashed):
            print(f"  ✓ 正确密码验证成功")
        else:
            print(f"  ✗ 正确密码验证失败")
            all_passed = False
        
        # 验证错误密码
        wrong_password = password + "wrong"
        if not verify_password(wrong_password, hashed):
            print(f"  ✓ 错误密码验证成功被拒绝")
        else:
            print(f"  ✗ 错误密码验证未被拒绝")
            all_passed = False
    
    return all_passed


def test_session_manager():
    """测试 Session 管理器"""
    print("\n测试 Session 管理器:")
    
    from app.auth.session import session_manager
    
    # 生成 Token
    token = session_manager.generate_token(
        "admin",
        user_info={
            'display_name': 'Administrator',
            'role': 'admin'
        }
    )
    
    print(f"  生成 Token: {token[:50]}...")
    
    # 验证 Token
    session = session_manager.validate_token(token)
    if session:
        print(f"  ✓ Token 验证成功")
        print(f"    用户名: {session['username']}")
        print(f"    显示名: {session['user_info'].get('display_name')}")
    else:
        print(f"  ✗ Token 验证失败")
        return False
    
    # 测试无效 Token
    if not session_manager.validate_token("invalid_token"):
        print(f"  ✓ 无效 Token 正确被拒绝")
    else:
        print(f"  ✗ 无效 Token 未被正确拒绝")
        return False
    
    # 测试 Token 失效
    session_manager.invalidate_token(token)
    if not session_manager.validate_token(token):
        print(f"  ✓ Token 失效成功")
    else:
        print(f"  ✗ Token 未正确失效")
        return False
    
    return True


def test_database_connection():
    """测试数据库连接"""
    print("\n测试数据库连接:")
    
    try:
        from app.models.db import is_mongo_available, get_collection_count, init_mock_data
        from app.models.relational_db import init_relational_schema, init_relational_data, list_tables
        
        # 初始化数据库
        print("  初始化数据库...")
        init_mock_data()
        init_relational_schema()
        init_relational_data()
        
        # 检查 MongoDB
        if is_mongo_available():
            user_count = get_collection_count('users')
            print(f"  ✓ MongoDB 用户数量: {user_count}")
            
            if user_count == 3:
                print(f"  ✓ 用户数量正确")
            else:
                print(f"  ✗ 用户数量不正确，期望 3")
                return False
        else:
            print(f"  ✗ MongoDB 不可用")
            return False
        
        # 检查关系型数据库
        tables = list_tables()
        print(f"  ✓ 关系型数据库表: {tables[:5]}...")
        
        if 'users' in tables:
            print(f"  ✓ users 表存在")
        else:
            print(f"  ✗ users 表不存在")
            return False
        
        return True
    except Exception as e:
        print(f"  ✗ 数据库测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    passed = []
    
    # 测试密码加密
    passed.append(("密码加密", test_password_hashing()))
    
    # 测试 Session 管理器
    passed.append(("Session 管理器", test_session_manager()))
    
    # 测试数据库连接
    passed.append(("数据库连接", test_database_connection()))
    
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
