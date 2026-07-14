"""
对象关联数据迁移（对齐 Go v3.0.8 getAddAsstData）

Go 权威 4 条:
  1. set → biz（bk_childid）
  2. module → set（bk_childid）
  3. host → module（bk_childid）
  4. host → plat（bk_cloud_id）

bk_obj_asst_id 遵循 app 的 _build_obj_asst_id(obj_id, asst_id, asst_obj_id) = {source}_{kind}_{target}
"""

from datetime import datetime
from typing import List, Dict, Any
from .. import BaseMigrate, get_timestamp, BK_DEFAULT_OWNER_ID, BK_SYSTEM_OPERATOR


class AssociationMigrate(BaseMigrate):
    """对象关联迁移"""

    ASSOCIATIONS = [
        {
            "bk_obj_asst_id": "set_bk_mainline_biz",
            "bk_obj_id": "set",
            "bk_asst_id": "bk_mainline",
            "bk_asst_obj_id": "biz",
            "bk_asst_name": "集群关联业务",
            "mapping": [{"key": "default", "value": "none"}],
            "priority": 1,
            "bk_supplier_account": BK_DEFAULT_OWNER_ID,
        },
        {
            "bk_obj_asst_id": "module_bk_mainline_set",
            "bk_obj_id": "module",
            "bk_asst_id": "bk_mainline",
            "bk_asst_obj_id": "set",
            "bk_asst_name": "模块关联集群",
            "mapping": [{"key": "default", "value": "none"}],
            "priority": 1,
            "bk_supplier_account": BK_DEFAULT_OWNER_ID,
        },
        {
            "bk_obj_asst_id": "host_bk_mainline_module",
            "bk_obj_id": "host",
            "bk_asst_id": "bk_mainline",
            "bk_asst_obj_id": "module",
            "bk_asst_name": "主机关联模块",
            "mapping": [{"key": "default", "value": "none"}],
            "priority": 1,
            "bk_supplier_account": BK_DEFAULT_OWNER_ID,
        },
        {
            "bk_obj_asst_id": "host_bk_cloud_id_plat",
            "bk_obj_id": "host",
            "bk_asst_id": "bk_cloud_id",
            "bk_asst_obj_id": "plat",
            "bk_asst_name": "主机关联云区域",
            "mapping": [{"key": "default", "value": "none"}],
            "priority": 1,
            "bk_supplier_account": BK_DEFAULT_OWNER_ID,
        },
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
