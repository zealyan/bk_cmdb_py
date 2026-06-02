#!/usr/bin/env python3
"""检查对象模型数据"""

import sys
sys.path.insert(0, '/workspace/bk_cmdb_py')

from pymongo import MongoClient

def check_objects():
    """检查cc_ObjectBase集合中的对象"""
    try:
        client = MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        db = client['bk_cmdb']
        
        # 查询所有对象
        objects = list(db.cc_ObjectBase.find({}, {'_id': 0}).sort('id', 1))
        
        print(f"总共 {len(objects)} 个对象：\n")
        for obj in objects:
            print(f"ID: {obj.get('id')}, bk_obj_id: {obj.get('bk_obj_id'):20} 名称: {obj.get('bk_obj_name')}")
        
        # 检查是否缺少业务集对象
        biz_set = db.cc_ObjectBase.find_one({'bk_obj_id': 'biz_set'})
        if biz_set:
            print(f"\n业务集对象存在: {biz_set}")
        else:
            print(f"\n❌ 业务集对象 (biz_set) 不存在！")
        
        client.close()
        
    except Exception as e:
        print(f"查询失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    check_objects()
