"""
关联类型数据迁移（cc_AsstDes）

对应 Go: src/scene_server/admin_server/upgrader/history/x18.10.30.01/association.go
    addPresetAssociationType()
"""

from .. import BaseMigrate, get_timestamp, BK_DEFAULT_OWNER_ID, BK_SYSTEM_OPERATOR


class AssociationTypeMigrate(BaseMigrate):
    """关联类型迁移"""

    ASSOCIATION_TYPES = [
        {
            "bk_asst_id": "belong",
            "bk_asst_name": "",
            "src_des": "属于",
            "dest_des": "包含",
            "direction": "dest_to_src",
            "ispre": True,
            "bk_supplier_account": BK_DEFAULT_OWNER_ID,
        },
        {
            "bk_asst_id": "group",
            "bk_asst_name": "",
            "src_des": "组成",
            "dest_des": "组成于",
            "direction": "dest_to_src",
            "ispre": True,
            "bk_supplier_account": BK_DEFAULT_OWNER_ID,
        },
        {
            "bk_asst_id": "bk_mainline",
            "bk_asst_name": "",
            "src_des": "组成",
            "dest_des": "组成于",
            "direction": "dest_to_src",
            "ispre": True,
            "bk_supplier_account": BK_DEFAULT_OWNER_ID,
        },
        {
            "bk_asst_id": "run",
            "bk_asst_name": "",
            "src_des": "运行于",
            "dest_des": "运行",
            "direction": "dest_to_src",
            "ispre": True,
            "bk_supplier_account": BK_DEFAULT_OWNER_ID,
        },
        {
            "bk_asst_id": "connect",
            "bk_asst_name": "",
            "src_des": "上联",
            "dest_des": "下联",
            "direction": "dest_to_src",
            "ispre": True,
            "bk_supplier_account": BK_DEFAULT_OWNER_ID,
        },
        {
            "bk_asst_id": "default",
            "bk_asst_name": "默认关联",
            "src_des": "关联",
            "dest_des": "被关联",
            "direction": "dest_to_src",
            "ispre": True,
            "bk_supplier_account": BK_DEFAULT_OWNER_ID,
        },
    ]

    def migrate(self) -> None:
        self.ensure_collection("cc_AsstDes")
        for item in self.ASSOCIATION_TYPES:
            self.upsert("cc_AsstDes", item, ["bk_asst_id"])


def run_association_type_migrate(db) -> None:
    AssociationTypeMigrate(db).migrate()
    print("Association type migrate completed!")
