#!/usr/bin/env python3
"""更新属性数据，修复创建业务表单不显示的问题"""

import sys
import os

sys.path.insert(0, '/workspace/bk_cmdb_py')

from pymongo import MongoClient

def update_properties():
    """更新cc_ObjAttDes集合中的bk_is_api字段"""
    try:
        client = MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        db = client['bk_cmdb']
        
        # 需要在创建表单中显示的字段（用户可以填写的）
        form_fields = [
            'bk_biz_name',
            'bk_maintainer',
            'time_zone',
        ]
        
        # 更新这些字段的bk_is_api为False
        result = db.cc_ObjAttDes.update_many(
            {'bk_property_id': {'$in': form_fields}},
            {'$set': {'bk_is_api': False}}
        )
        
        print(f"更新了 {result.modified_count} 条记录的 bk_is_api 字段")
        
        # 验证更新结果
        for field in form_fields:
            doc = db.cc_ObjAttDes.find_one({'bk_property_id': field})
            if doc:
                print(f"{field}: bk_is_api = {doc.get('bk_is_api')}")
            else:
                print(f"{field}: 未找到")
        
        client.close()
        print("更新完成！")
        
    except Exception as e:
        print(f"更新失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    update_properties()
