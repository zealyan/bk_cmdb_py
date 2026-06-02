#!/usr/bin/env python3
"""
业务管理API测试脚本
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models.db import init_mock_data, db


def test_business_api():
    """测试业务管理API"""
    print("=" * 60)
    print("开始测试业务管理API")
    print("=" * 60)
    
    # 1. 初始化测试数据库
    print("\n[1] 初始化数据库...")
    if db:
        init_mock_data()
        print("✓ 数据库初始化成功")
    else:
        print("⚠  数据库不可用，跳过部分测试")
        return
    
    # 2. 测试业务查询
    print("\n[2] 测试业务查询...")
    
    # 测试简化业务列表
    businesses = list(db.cc_ApplicationBase.find())
    print(f"✓ 共 {len(businesses)} 个业务")
    for biz in businesses:
        print(f"  - {biz['bk_biz_name} (ID: {biz['bk_biz_id']})")
    
    # 3. 测试用户业务关系
    print("\n[3] 测试用户业务关系...")
    user_biz_list = list(db.user_business.find())
    print(f"✓ 共 {len(user_biz_list)} 条用户业务关系")
    for ub in user_biz_list:
        print(f"  - 用户 {ub['username']} -> 业务 {ub['bk_biz_id']}")
    
    # 4. 测试查询条件查询
    print("\n[4] 测试条件查询...")
    # 只查询启用的业务
    enabled_biz = list(db.cc_ApplicationBase.find({'bk_data_status': {'$ne': 'disabled'}}))
    print(f"✓ 共 {len(enabled_biz)} 个启用的业务")
    
    # 5. 测试创建业务
    print("\n[5] 测试创建业务...")
    from datetime import datetime
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    new_biz = {
        'bk_biz_id': 99,
        'bk_biz_name': '测试业务-新业务',
        'bk_supplier_account': '0',
        'operator': 'admin',
        'bk_maintainer': 'admin',
        'time_zone': 'Asia/Shanghai',
        'create_time': current_time,
        'last_time': current_time,
        'bk_data_status': 'enabled'
    }
    db.cc_ApplicationBase.insert_one(new_biz)
    print("✓ 业务创建成功")
    
    # 6. 测试更新业务
    print("\n[6] 测试更新业务...")
    db.cc_ApplicationBase.update_one(
        {'bk_biz_id': 99},
        {'$set': {'bk_biz_name': '测试业务-已更新'}}
    )
    updated_biz = db.cc_ApplicationBase.find_one({'bk_biz_id': 99})
    print(f"✓ 业务更新成功: {updated_biz['bk_biz_name']}")
    
    # 7. 测试归档业务
    print("\n[7] 测试归档业务...")
    db.cc_ApplicationBase.update_one(
        {'bk_biz_id': 99},
        {'$set': {'bk_data_status': 'disabled'}}
    )
    archived_biz = db.cc_ApplicationBase.find_one({'bk_biz_id': 99})
    print(f"✓ 业务归档成功: {archived_biz['bk_data_status']}")
    
    # 清理测试数据
    print("\n[8] 清理测试数据...")
    db.cc_ApplicationBase.delete_one({'bk_biz_id': 99})
    print("✓ 测试数据清理完成")
    
    print("\n" + "=" * 60)
    print("所有测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    test_business_api()
