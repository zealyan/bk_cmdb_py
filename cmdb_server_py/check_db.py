#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.db import db, init_mock_data

print("--- MongoDB 连接 ---")
print("MongoDB 可用:", db is not None)

print("\n--- 用户集合 ---")
users = list(db.users.find())
print(f"用户数量: {len(users)}")
for u in users:
    print(f"  - 用户名: {u.get('username')}, 密码哈希存在: {bool(u.get('password'))}")

print("\n--- 尝试登录验证 ---")
from app.auth import verify_password
for u in users:
    username = u.get('username')
    # 尝试默认密码
    for test_pass in ['admin', '123456', username, username+'123']:
        if verify_password(test_pass, u.get('password', '')):
            print(f"✅ 用户 {username} 的密码是: {test_pass}")
            break
    else:
        print(f"❌ 用户 {username} 无法用默认密码登录")

print("\n--- 业务集合 ---")
biz_count = db.cc_ApplicationBase.count_documents({})
print(f"业务数量: {biz_count}")

print("\n--- 权限策略集合 ---")
policy_count = db.auth_policies.count_documents({})
print(f"权限策略数量: {policy_count}")
