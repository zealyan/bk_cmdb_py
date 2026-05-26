#!/usr/bin/env python3
"""补充缺失的对象模型数据"""

import sys
sys.path.insert(0, '/workspace/bk_cmdb_py')

from pymongo import MongoClient

def add_missing_objects():
    """添加缺失的对象模型"""
    try:
        client = MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        db = client['bk_cmdb']
        
        # 需要添加的对象模型
        objects_to_add = [
            # 业务拓扑对象
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
            # 业务集对象
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
            # 云区域对象
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
            # 进程对象
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
            },
        ]
        
        added_count = 0
        for obj in objects_to_add:
            # 检查是否已存在
            existing = db.cc_ObjectBase.find_one({'bk_obj_id': obj['bk_obj_id']})
            if existing:
                print(f"✓ {obj['bk_obj_id']} ({obj['bk_obj_name']}) 已存在")
            else:
                db.cc_ObjectBase.insert_one(obj)
                print(f"+ 添加 {obj['bk_obj_id']} ({obj['bk_obj_name']})")
                added_count += 1
        
        # 补充缺失的对象属性
        add_missing_attributes(db)
        
        print(f"\n总共添加了 {added_count} 个对象模型")
        
        # 验证结果
        print("\n当前所有对象模型：")
        objects = list(db.cc_ObjectBase.find({}, {'_id': 0}).sort('id', 1))
        for obj in objects:
            print(f"  - {obj.get('bk_obj_id'):20} ({obj.get('bk_obj_name')})")
        
        client.close()
        
    except Exception as e:
        print(f"添加失败: {e}")
        import traceback
        traceback.print_exc()

def add_missing_attributes(db):
    """添加缺失的对象属性"""
    print("\n检查对象属性...")
    
    # 业务对象属性
    biz_attributes = [
        {"id": 1, "bk_obj_id": "biz", "bk_property_id": "bk_biz_id", "bk_property_name": "业务ID", "bk_property_type": "int", "bk_property_group": "default", "is_pre": True, "is_required": True, "is_readonly": True, "is_only": True, "bk_is_system": True, "bk_is_api": True},
        {"id": 2, "bk_obj_id": "biz", "bk_property_id": "bk_biz_name", "bk_property_name": "业务名称", "bk_property_type": "singlechar", "bk_property_group": "default", "is_pre": True, "is_required": True, "is_readonly": False, "is_only": False, "bk_is_system": False, "bk_is_api": False},
        {"id": 3, "bk_obj_id": "biz", "bk_property_id": "bk_maintainer", "bk_property_name": "运维负责人", "bk_property_type": "objuser", "bk_property_group": "default", "is_pre": True, "is_required": True, "is_readonly": False, "is_only": False, "bk_is_system": False, "bk_is_api": False},
        {"id": 4, "bk_obj_id": "biz", "bk_property_id": "bk_supplier_account", "bk_property_name": "开发商账号", "bk_property_type": "singlechar", "bk_property_group": "default", "is_pre": True, "is_required": True, "is_readonly": True, "is_only": False, "bk_is_system": True, "bk_is_api": True},
        {"id": 5, "bk_obj_id": "biz", "bk_property_id": "create_time", "bk_property_name": "创建时间", "bk_property_type": "time", "bk_property_group": "default", "is_pre": False, "is_required": False, "is_readonly": True, "is_only": False, "bk_is_system": True, "bk_is_api": False},
        {"id": 6, "bk_obj_id": "biz", "bk_property_id": "last_time", "bk_property_name": "更新时间", "bk_property_type": "time", "bk_property_group": "default", "is_pre": False, "is_required": False, "is_readonly": True, "is_only": False, "bk_is_system": True, "bk_is_api": False},
        {"id": 7, "bk_obj_id": "biz", "bk_property_id": "time_zone", "bk_property_name": "时区", "bk_property_type": "singlechar", "bk_property_group": "default", "is_pre": False, "is_required": False, "is_readonly": False, "is_only": False, "bk_is_system": False, "bk_is_api": False, "default": "Asia/Shanghai"},
        {"id": 8, "bk_obj_id": "biz", "bk_property_id": "operator", "bk_property_name": "最后修改人", "bk_property_type": "singlechar", "bk_property_group": "default", "is_pre": False, "is_required": False, "is_readonly": True, "is_only": False, "bk_is_system": True, "bk_is_api": False},
    ]
    
    # 集群对象属性
    set_attributes = [
        {"id": 101, "bk_obj_id": "set", "bk_property_id": "bk_set_id", "bk_property_name": "集群ID", "bk_property_type": "int", "bk_property_group": "default", "is_pre": True, "is_required": True, "is_readonly": True, "is_only": True, "bk_is_system": True, "bk_is_api": True},
        {"id": 102, "bk_obj_id": "set", "bk_property_id": "bk_set_name", "bk_property_name": "集群名称", "bk_property_type": "singlechar", "bk_property_group": "default", "is_pre": True, "is_required": True, "is_readonly": False, "is_only": False, "bk_is_system": False, "bk_is_api": False},
        {"id": 103, "bk_obj_id": "set", "bk_property_id": "bk_biz_id", "bk_property_name": "业务ID", "bk_property_type": "int", "bk_property_group": "default", "is_pre": True, "is_required": True, "is_readonly": True, "is_only": False, "bk_is_system": True, "bk_is_api": True},
    ]
    
    # 模块对象属性
    module_attributes = [
        {"id": 201, "bk_obj_id": "module", "bk_property_id": "bk_module_id", "bk_property_name": "模块ID", "bk_property_type": "int", "bk_property_group": "default", "is_pre": True, "is_required": True, "is_readonly": True, "is_only": True, "bk_is_system": True, "bk_is_api": True},
        {"id": 202, "bk_obj_id": "module", "bk_property_id": "bk_module_name", "bk_property_name": "模块名称", "bk_property_type": "singlechar", "bk_property_group": "default", "is_pre": True, "is_required": True, "is_readonly": False, "is_only": False, "bk_is_system": False, "bk_is_api": False},
        {"id": 203, "bk_obj_id": "module", "bk_property_id": "bk_set_id", "bk_property_name": "集群ID", "bk_property_type": "int", "bk_property_group": "default", "is_pre": True, "is_required": True, "is_readonly": True, "is_only": False, "bk_is_system": True, "bk_is_api": True},
    ]
    
    # 主机对象属性
    host_attributes = [
        {"id": 301, "bk_obj_id": "host", "bk_property_id": "bk_host_id", "bk_property_name": "主机ID", "bk_property_type": "int", "bk_property_group": "default", "is_pre": True, "is_required": True, "is_readonly": True, "is_only": True, "bk_is_system": True, "bk_is_api": True},
        {"id": 302, "bk_obj_id": "host", "bk_property_id": "bk_host_innerip", "bk_property_name": "内网IP", "bk_property_type": "singlechar", "bk_property_group": "default", "is_pre": True, "is_required": True, "is_readonly": False, "is_only": False, "bk_is_system": False, "bk_is_api": True},
        {"id": 303, "bk_obj_id": "host", "bk_property_id": "bk_host_outerip", "bk_property_name": "外网IP", "bk_property_type": "singlechar", "bk_property_group": "default", "is_pre": True, "is_required": False, "is_readonly": False, "is_only": False, "bk_is_system": False, "bk_is_api": True},
    ]
    
    # 业务集对象属性
    biz_set_attributes = [
        {"id": 401, "bk_obj_id": "biz_set", "bk_property_id": "bk_biz_set_id", "bk_property_name": "业务集ID", "bk_property_type": "int", "bk_property_group": "default", "is_pre": True, "is_required": True, "is_readonly": True, "is_only": True, "bk_is_system": True, "bk_is_api": True},
        {"id": 402, "bk_obj_id": "biz_set", "bk_property_id": "bk_biz_set_name", "bk_property_name": "业务集名称", "bk_property_type": "singlechar", "bk_property_group": "default", "is_pre": True, "is_required": True, "is_readonly": False, "is_only": False, "bk_is_system": False, "bk_is_api": False},
        {"id": 403, "bk_obj_id": "biz_set", "bk_property_id": "bk_biz_set_desc", "bk_property_name": "业务集描述", "bk_property_type": "longchar", "bk_property_group": "default", "is_pre": True, "is_required": False, "is_readonly": False, "is_only": False, "bk_is_system": False, "bk_is_api": False},
    ]
    
    all_attributes = biz_attributes + set_attributes + module_attributes + host_attributes + biz_set_attributes
    
    added_count = 0
    for attr in all_attributes:
        # 检查是否已存在
        existing = db.cc_ObjAttDes.find_one({
            'bk_obj_id': attr['bk_obj_id'],
            'bk_property_id': attr['bk_property_id']
        })
        if existing:
            continue
        else:
            db.cc_ObjAttDes.insert_one(attr)
            print(f"  + {attr['bk_obj_id']}.{attr['bk_property_id']}")
            added_count += 1
    
    print(f"添加了 {added_count} 个对象属性")

if __name__ == '__main__':
    add_missing_objects()
