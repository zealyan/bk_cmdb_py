#!/usr/bin/env python3
"""更新db.py中的初始化数据"""

import re

def update_db_init_data():
    """更新db.py中的INIT_DATA"""
    try:
        with open('/workspace/bk_cmdb_py/app/models/db.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 新的cc_ObjectBase初始化数据
        new_objects = '''    "cc_ObjectBase": [
        {
            "id": 1,
            "bk_classification_id": "bk_biz_topo",
            "bk_obj_id": "biz",
            "bk_obj_name": "业务",
            "bk_supplier_account": "0",
            "bk_obj_icon": "icon-cc-business",
            "is_built_in": True,
            "is_pre": True,
            "position": "biz"
        },
        {
            "id": 2,
            "bk_classification_id": "bk_biz_topo",
            "bk_obj_id": "set",
            "bk_obj_name": "集群",
            "bk_supplier_account": "0",
            "bk_obj_icon": "icon-cc-set",
            "is_built_in": True,
            "is_pre": True,
            "position": "biz"
        },
        {
            "id": 3,
            "bk_classification_id": "bk_biz_topo",
            "bk_obj_id": "module",
            "bk_obj_name": "模块",
            "bk_supplier_account": "0",
            "bk_obj_icon": "icon-cc-module",
            "is_built_in": True,
            "is_pre": True,
            "position": "biz"
        },
        {
            "id": 4,
            "bk_classification_id": "bk_host_manage",
            "bk_obj_id": "host",
            "bk_obj_name": "主机",
            "bk_supplier_account": "0",
            "bk_obj_icon": "icon-cc-host",
            "is_built_in": True,
            "is_pre": True,
            "position": "host"
        },
        {
            "id": 5,
            "bk_classification_id": "bk_biz_set",
            "bk_obj_id": "biz_set",
            "bk_obj_name": "业务集",
            "bk_supplier_account": "0",
            "bk_obj_icon": "icon-cc-business-set",
            "is_built_in": True,
            "is_pre": True,
            "position": "biz_set"
        },
        {
            "id": 6,
            "bk_classification_id": "bk_cloud_area",
            "bk_obj_id": "cloud_area",
            "bk_obj_name": "云区域",
            "bk_supplier_account": "0",
            "bk_obj_icon": "icon-cc-cloud",
            "is_built_in": True,
            "is_pre": True,
            "position": "cloud"
        },
        {
            "id": 7,
            "bk_classification_id": "bk_process",
            "bk_obj_id": "process",
            "bk_obj_name": "进程",
            "bk_supplier_account": "0",
            "bk_obj_icon": "icon-cc-process",
            "is_built_in": True,
            "is_pre": True,
            "position": "process"
        }
    ],'''
        
        # 替换cc_ObjectBase部分
        pattern = r'"cc_ObjectBase":\s*\[[\s\S]*?\],\s*"cc_ObjAttDes"'
        if re.search(pattern, content):
            content = re.sub(pattern, new_objects + '\n    "cc_ObjAttDes"', content)
            print("✓ 更新了cc_ObjectBase初始化数据")
        else:
            print("❌ 未找到cc_ObjectBase模式")
        
        with open('/workspace/bk_cmdb_py/app/models/db.py', 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✓ db.py更新完成")
        
    except Exception as e:
        print(f"更新失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    update_db_init_data()
