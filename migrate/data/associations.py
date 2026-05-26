"""
对象关联数据迁移

对应 Go 项目中的关联定义
"""

from datetime import datetime
from typing import List, Dict, Any
from .. import BaseMigrate, get_timestamp, BK_DEFAULT_OWNER_ID, BK_SYSTEM_OPERATOR


class AssociationMigrate(BaseMigrate):
    """对象关联迁移"""

    ASSOCIATIONS = [
        {"bk_obj_asst_id": "biz_set_set", "bk_asst_id": "biz", "bk_asst_obj_id": "set", "bk_asst_name": "业务关联集群", "mapping": [{"key": "default", "value": "none"}], "priority": 1, "bk_supplier_account": BK_DEFAULT_OWNER_ID},
        {"bk_obj_asst_id": "set_module", "bk_asst_id": "set", "bk_asst_obj_id": "module", "bk_asst_name": "集群关联模块", "mapping": [{"key": "default", "value": "none"}], "priority": 1, "bk_supplier_account": BK_DEFAULT_OWNER_ID},
        {"bk_obj_asst_id": "module_host", "bk_asst_id": "module", "bk_asst_obj_id": "host", "bk_asst_name": "模块关联主机", "mapping": [{"key": "default", "value": "none"}], "priority": 1, "bk_supplier_account": BK_DEFAULT_OWNER_ID},
        {"bk_obj_asst_id": "biz_host", "bk_asst_id": "biz", "bk_asst_obj_id": "host", "bk_asst_name": "业务主机关联", "mapping": [{"key": "default", "value": "none"}], "priority": 0, "bk_supplier_account": BK_DEFAULT_OWNER_ID},
    ]

    def migrate(self) -> None:
        self.ensure_collection("cc_ObjAsst")
        ts = get_timestamp()
        for item in self.ASSOCIATIONS:
            data = {
                **item,
                "creator": BK_SYSTEM_OPERATOR,
                "create_time": ts,
                "last_time": ts,
            }
            self.upsert("cc_ObjAsst", data, ["bk_obj_asst_id", "bk_supplier_account"])


def run_association_migrate(db) -> None:
    AssociationMigrate(db).migrate()
    print("Association migrate completed!")
