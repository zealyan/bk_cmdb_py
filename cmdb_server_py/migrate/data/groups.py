"""
属性分组数据迁移

对应 Go 项目: src/scene_server/admin_server/upgrader/history/v3.0.8/
"""

from datetime import datetime
from typing import List, Dict, Any
from .. import BaseMigrate, get_timestamp, BK_DEFAULT_OWNER_ID, BK_SYSTEM_OPERATOR


class PropertyGroupMigrate(BaseMigrate):
    """属性分组迁移"""

    GROUPS = [
        {"bk_obj_id": "biz", "bk_group_id": "base", "bk_group_name": "基础信息", "bk_group_index": 1, "bk_supplier_account": BK_DEFAULT_OWNER_ID, "isdefault": True},
        {"bk_obj_id": "biz", "bk_group_id": "role", "bk_group_name": "运维人员", "bk_group_index": 2, "bk_supplier_account": BK_DEFAULT_OWNER_ID, "isdefault": True},

        {"bk_obj_id": "set", "bk_group_id": "base", "bk_group_name": "基础信息", "bk_group_index": 1, "bk_supplier_account": BK_DEFAULT_OWNER_ID, "isdefault": True},

        {"bk_obj_id": "module", "bk_group_id": "base", "bk_group_name": "基础信息", "bk_group_index": 1, "bk_supplier_account": BK_DEFAULT_OWNER_ID, "isdefault": True},

        {"bk_obj_id": "host", "bk_group_id": "base", "bk_group_name": "基础信息", "bk_group_index": 1, "bk_supplier_account": BK_DEFAULT_OWNER_ID, "isdefault": True},
        {"bk_obj_id": "host", "bk_group_id": "auto", "bk_group_name": "自动发现", "bk_group_index": 3, "bk_supplier_account": BK_DEFAULT_OWNER_ID, "isdefault": True},

        {"bk_obj_id": "process", "bk_group_id": "base", "bk_group_name": "基础信息", "bk_group_index": 1, "bk_supplier_account": BK_DEFAULT_OWNER_ID, "isdefault": True},
        {"bk_obj_id": "process", "bk_group_id": "port", "bk_group_name": "端口信息", "bk_group_index": 2, "bk_supplier_account": BK_DEFAULT_OWNER_ID, "isdefault": True},
        {"bk_obj_id": "process", "bk_group_id": "gsekit_base", "bk_group_name": " GSEkit基础信息", "bk_group_index": 3, "bk_supplier_account": BK_DEFAULT_OWNER_ID, "isdefault": True},
        {"bk_obj_id": "process", "bk_group_id": "gsekit_manage", "bk_group_name": "GSEkit管理信息", "bk_group_index": 4, "bk_supplier_account": BK_DEFAULT_OWNER_ID, "isdefault": True},

        {"bk_obj_id": "plat", "bk_group_id": "base", "bk_group_name": "基础信息", "bk_group_index": 1, "bk_supplier_account": BK_DEFAULT_OWNER_ID, "isdefault": True},

        {"bk_obj_id": "switch", "bk_group_id": "base", "bk_group_name": "基础信息", "bk_group_index": 1, "bk_supplier_account": BK_DEFAULT_OWNER_ID, "isdefault": True},
        {"bk_obj_id": "router", "bk_group_id": "base", "bk_group_name": "基础信息", "bk_group_index": 1, "bk_supplier_account": BK_DEFAULT_OWNER_ID, "isdefault": True},
        {"bk_obj_id": "load_balance", "bk_group_id": "base", "bk_group_name": "基础信息", "bk_group_index": 1, "bk_supplier_account": BK_DEFAULT_OWNER_ID, "isdefault": True},
        {"bk_obj_id": "firewall", "bk_group_id": "base", "bk_group_name": "基础信息", "bk_group_index": 1, "bk_supplier_account": BK_DEFAULT_OWNER_ID, "isdefault": True},
    ]

    def migrate(self) -> None:
        self.ensure_collection("cc_PropertyGroup")
        for item in self.GROUPS:
            self.upsert("cc_PropertyGroup", item, ["bk_obj_id", "bk_group_id"])


def run_group_migrate(db) -> None:
    PropertyGroupMigrate(db).migrate()
    print("Property group migrate completed!")
