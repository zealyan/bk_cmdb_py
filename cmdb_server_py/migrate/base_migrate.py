"""
Base Migrate - 基础数据迁移

对应 Go 项目: src/scene_server/admin_server/upgrader/history/v3.0.8/
"""

from datetime import datetime
from typing import List, Dict, Any
from . import BaseMigrate, get_timestamp, BK_DEFAULT_OWNER_ID, BK_SYSTEM_OPERATOR


class ClassificationMigrate(BaseMigrate):
    """对象分类迁移 - 对应 Go addPresetObjects.addClassifications"""

    CLASSIFICATIONS = [
        {
            "bk_classification_id": "bk_host_manage",
            "bk_classification_name": "主机管理",
            "bk_classification_type": "inner",
            "bk_classification_icon": "icon-cc-host",
            "id": 1,
        },
        {
            "bk_classification_id": "bk_biz_topo",
            "bk_classification_name": "业务拓扑",
            "bk_classification_type": "inner",
            "bk_classification_icon": "icon-cc-business",
            "id": 2,
        },
        {
            "bk_classification_id": "bk_organization",
            "bk_classification_name": "组织架构",
            "bk_classification_type": "inner",
            "bk_classification_icon": "icon-cc-organization",
            "id": 3,
        },
        {
            "bk_classification_id": "bk_network",
            "bk_classification_name": "网络",
            "bk_classification_type": "inner",
            "bk_classification_icon": "icon-cc-network-equipment",
            "id": 4,
        },
    ]

    def migrate(self) -> None:
        self.ensure_collection("cc_ObjClassification")
        for item in self.CLASSIFICATIONS:
            self.upsert("cc_ObjClassification", item, ["bk_classification_id"])


class ObjectDesMigrate(BaseMigrate):
    """对象描述迁移 - 对应 Go addPresetObjects.addObjDesData"""

    OBJECTS = [
        {
            "bk_obj_id": "host",
            "bk_obj_name": "主机",
            "bk_classification_id": "bk_host_manage",
            "bk_obj_icon": "icon-cc-host",
            "position": '{"bk_host_manage":{"x":-600,"y":-650}}',
            "ispre": True,
            "creator": BK_SYSTEM_OPERATOR,
            "create_time": get_timestamp(),
            "last_time": get_timestamp(),
            "bk_supplier_account": BK_DEFAULT_OWNER_ID,
        },
        {
            "bk_obj_id": "module",
            "bk_obj_name": "模块",
            "bk_classification_id": "bk_biz_topo",
            "bk_obj_icon": "icon-cc-module",
            "position": "",
            "ispre": True,
            "creator": BK_SYSTEM_OPERATOR,
            "create_time": get_timestamp(),
            "last_time": get_timestamp(),
            "bk_supplier_account": BK_DEFAULT_OWNER_ID,
        },
        {
            "bk_obj_id": "set",
            "bk_obj_name": "集群",
            "bk_classification_id": "bk_biz_topo",
            "bk_obj_icon": "icon-cc-set",
            "position": "",
            "ispre": True,
            "creator": BK_SYSTEM_OPERATOR,
            "create_time": get_timestamp(),
            "last_time": get_timestamp(),
            "bk_supplier_account": BK_DEFAULT_OWNER_ID,
        },
        {
            "bk_obj_id": "biz",
            "bk_obj_name": "业务",
            "bk_classification_id": "bk_organization",
            "bk_obj_icon": "icon-cc-business",
            "position": '{"bk_organization":{"x":-100,"y":-100}}',
            "ispre": True,
            "creator": BK_SYSTEM_OPERATOR,
            "create_time": get_timestamp(),
            "last_time": get_timestamp(),
            "bk_supplier_account": BK_DEFAULT_OWNER_ID,
        },
        {
            "bk_obj_id": "process",
            "bk_obj_name": "进程",
            "bk_classification_id": "bk_host_manage",
            "bk_obj_icon": "icon-cc-process",
            "position": '{"bk_host_manage":{"x":-450,"y":-650}}',
            "ispre": True,
            "creator": BK_SYSTEM_OPERATOR,
            "create_time": get_timestamp(),
            "last_time": get_timestamp(),
            "bk_supplier_account": BK_DEFAULT_OWNER_ID,
        },
        {
            "bk_obj_id": "plat",
            "bk_obj_name": "云区域",
            "bk_classification_id": "bk_host_manage",
            "bk_obj_icon": "icon-cc-subnet",
            "position": '{"bk_host_manage":{"x":-600,"y":-500}}',
            "ispre": True,
            "creator": BK_SYSTEM_OPERATOR,
            "create_time": get_timestamp(),
            "last_time": get_timestamp(),
            "bk_supplier_account": BK_DEFAULT_OWNER_ID,
        },
        {
            "bk_obj_id": "switch",
            "bk_obj_name": "交换机",
            "bk_classification_id": "bk_network",
            "bk_obj_icon": "icon-cc-switch2",
            "position": '{"bk_network":{"x":-200,"y":-50}}',
            "ispre": False,
            "creator": BK_SYSTEM_OPERATOR,
            "create_time": get_timestamp(),
            "last_time": get_timestamp(),
            "bk_supplier_account": BK_DEFAULT_OWNER_ID,
        },
        {
            "bk_obj_id": "router",
            "bk_obj_name": "路由器",
            "bk_classification_id": "bk_network",
            "bk_obj_icon": "icon-cc-router",
            "position": '{"bk_network":{"x":-350,"y":-50}}',
            "ispre": False,
            "creator": BK_SYSTEM_OPERATOR,
            "create_time": get_timestamp(),
            "last_time": get_timestamp(),
            "bk_supplier_account": BK_DEFAULT_OWNER_ID,
        },
        {
            "bk_obj_id": "load_balance",
            "bk_obj_name": "负载均衡",
            "bk_classification_id": "bk_network",
            "bk_obj_icon": "icon-cc-balance",
            "position": '{"bk_network":{"x":-500,"y":-50}}',
            "ispre": False,
            "creator": BK_SYSTEM_OPERATOR,
            "create_time": get_timestamp(),
            "last_time": get_timestamp(),
            "bk_supplier_account": BK_DEFAULT_OWNER_ID,
        },
        {
            "bk_obj_id": "firewall",
            "bk_obj_name": "防火墙",
            "bk_classification_id": "bk_network",
            "bk_obj_icon": "icon-cc-firewall",
            "position": '{"bk_network":{"x":-650,"y":-50}}',
            "ispre": False,
            "creator": BK_SYSTEM_OPERATOR,
            "create_time": get_timestamp(),
            "last_time": get_timestamp(),
            "bk_supplier_account": BK_DEFAULT_OWNER_ID,
        },
    ]

    def migrate(self) -> None:
        self.ensure_collection("cc_ObjDes")
        for idx, item in enumerate(self.OBJECTS, start=1):
            data = {**item}
            # 使用 insert_if_not_exists + update 组合：仅新文档设置 id
            query = {"bk_obj_id": item["bk_obj_id"], "bk_supplier_account": item.get("bk_supplier_account", "0")}
            existing = self.db["cc_ObjDes"].find_one(query)
            if existing:
                # 已有文档只更新业务字段，不覆盖 id
                data.pop("id", None)
                self.db["cc_ObjDes"].update_one(query, {"$set": data})
            else:
                data["id"] = idx
                self.db["cc_ObjDes"].insert_one(data)


class SystemMigrate(BaseMigrate):
    """系统配置 + 迁移版本记录
    - host_cross_biz: 业务配置标志（app 使用）
    - migrate_version: 迁移版本记录，用于幂等追踪
    """

    def migrate(self) -> None:
        self.ensure_collection("cc_System")
        # 业务配置标志
        self.insert_if_not_exists("cc_System", {"host_cross_biz": False}, ["host_cross_biz"])
        # 迁移版本记录（Go 用 cc_System 做版本追踪）
        self.insert_if_not_exists("cc_System", {
            "flag": "migrate_version",
            "version": "v3.0.0",
            "description": "基础 seed 对齐 Go v3.0.8 addPresetObjects",
        }, ["flag", "version"])


class PlatMigrate(BaseMigrate):
    """云区域迁移 - 对应 Go addPlatData"""

    def migrate(self) -> None:
        self.ensure_collection("cc_PlatBase")
        plat_data = {
            "bk_cloud_name": "default area",
            "bk_supplier_account": BK_DEFAULT_OWNER_ID,
            "bk_cloud_id": 0,
            "create_time": get_timestamp(),
            "last_time": get_timestamp(),
        }
        self.insert_if_not_exists("cc_PlatBase", plat_data, ["bk_cloud_name", "bk_supplier_account"])


def run_base_migrate(db) -> None:
    """执行所有基础数据迁移"""
    migrations = [
        ClassificationMigrate(db),
        ObjectDesMigrate(db),
        SystemMigrate(db),
        PlatMigrate(db),
    ]

    for m in migrations:
        print(f"Running migration: {m.__class__.__name__}")
        m.migrate()

    print("Base migrate completed!")
