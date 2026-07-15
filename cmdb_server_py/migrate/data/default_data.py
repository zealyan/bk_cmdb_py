"""
默认种子数据迁移 - 对齐 Go 官方 v3.10.50 community/0 种子

承载 Go migrate 同时产出的「运行级」集合（业务/资源池、唯一性规则、
业务集、ID 生成器）。这些集合供 Flask 应用读写（next_sequence 依赖 cc_idgenerator）。
"""

from .. import BaseMigrate, get_timestamp, BK_DEFAULT_OWNER_ID, BK_SYSTEM_OPERATOR


class ObjectUniqueMigrate(BaseMigrate):
    """模型唯一性规则 - 对齐 Go cc_ObjectUnique（14 条，key_id 引用 cc_ObjAttDes.id）"""

    OBJECT_UNIQUES = [
        {"id": 1, "bk_obj_id": "host", "keys": [
                        {
                        "key_kind": "property",
                        "key_id": 35},
                        {
                        "key_kind": "property",
                        "key_id": 26}], "ispre": True, "bk_supplier_account": "0"},
        {"id": 4, "bk_obj_id": "biz", "keys": [
                        {
                        "key_kind": "property",
                        "key_id": 1}], "ispre": True, "bk_supplier_account": "0"},
        {"id": 5, "bk_obj_id": "set", "keys": [
                        {
                        "key_kind": "property",
                        "key_id": 10},
                        {
                        "key_kind": "property",
                        "key_id": 11},
                        {
                        "key_kind": "property",
                        "key_id": 18}], "ispre": True, "bk_supplier_account": "0"},
        {"id": 6, "bk_obj_id": "module", "keys": [
                        {
                        "key_kind": "property",
                        "key_id": 19},
                        {
                        "key_kind": "property",
                        "key_id": 20},
                        {
                        "key_kind": "property",
                        "key_id": 21}], "ispre": True, "bk_supplier_account": "0"},
        {"id": 7, "bk_obj_id": "plat", "keys": [
                        {
                        "key_kind": "property",
                        "key_id": 74}], "ispre": True, "bk_supplier_account": "0"},
        {"id": 9, "bk_obj_id": "bk_firewall", "keys": [
                        {
                        "key_kind": "property",
                        "key_id": 109}], "ispre": False, "bk_supplier_account": "0"},
        {"id": 10, "bk_obj_id": "bk_load_balance", "keys": [
                        {
                        "key_kind": "property",
                        "key_id": 98}], "ispre": False, "bk_supplier_account": "0"},
        {"id": 11, "bk_obj_id": "bk_router", "keys": [
                        {
                        "key_kind": "property",
                        "key_id": 87}], "ispre": False, "bk_supplier_account": "0"},
        {"id": 12, "bk_obj_id": "bk_switch", "keys": [
                        {
                        "key_kind": "property",
                        "key_id": 76}], "ispre": False, "bk_supplier_account": "0"},
        {"id": 13, "bk_obj_id": "host", "keys": [
                        {
                        "key_kind": "property",
                        "key_id": 27}], "ispre": False, "bk_supplier_account": "0"},
        {"id": 14, "bk_obj_id": "host", "keys": [
                        {
                        "key_kind": "property",
                        "key_id": 145},
                        {
                        "key_kind": "property",
                        "key_id": 147}], "ispre": False, "bk_supplier_account": "0"},
        {"id": 16, "bk_obj_id": "bk_biz_set_obj", "keys": [
                        {
                        "key_kind": "property",
                        "key_id": 151}], "ispre": True, "bk_supplier_account": "0"},
        {"id": 17, "bk_obj_id": "bk_biz_set_obj", "keys": [
                        {
                        "key_kind": "property",
                        "key_id": 155}], "ispre": True, "bk_supplier_account": "0"},
        {"id": 18, "bk_obj_id": "host", "keys": [
                        {
                        "key_kind": "property",
                        "key_id": 156},
                        {
                        "key_kind": "property",
                        "key_id": 35}], "ispre": True, "bk_supplier_account": "0"},
    ]

    def migrate(self) -> None:
        self.ensure_collection("cc_ObjectUnique")
        for item in self.OBJECT_UNIQUES:
            data = dict(item)
            data["bk_supplier_account"] = BK_DEFAULT_OWNER_ID
            self.upsert("cc_ObjectUnique", data, ["id", "bk_supplier_account"])


class BizSetMigrate(BaseMigrate):
    """业务集 - 对齐 Go cc_BizSetBase（1 条：BlueKing 默认业务集）"""

    BIZ_SETS = [
        {"bk_biz_set_id": 9991001, "bk_biz_set_name": "BlueKing", "description": "", "bk_biz_maintainer": "admin", "bk_supplier_account": "0", "bk_scope": {
                        "match_all": True}, "default": 1},
    ]

    def migrate(self) -> None:
        self.ensure_collection("cc_BizSetBase")
        for item in self.BIZ_SETS:
            data = dict(item)
            data["bk_supplier_account"] = BK_DEFAULT_OWNER_ID
            self.upsert("cc_BizSetBase", data, ["bk_biz_set_id", "bk_supplier_account"])


class DefaultBusinessMigrate(BaseMigrate):
    """内置业务与资源池拓扑 - 对齐 Go cc_ApplicationBase / cc_SetBase / cc_ModuleBase

    资源池(bk_biz_id=1) + 蓝鲸(bk_biz_id=2)，各自含空闲机池/空闲机/故障机/待回收。
    """

    BUSINESSES = [
        {"language": "1", "default": 1, "operator": "", "time_zone": "Asia/Shanghai", "bk_biz_tester": "", "bk_biz_id": 1, "bk_biz_name": "资源池", "bk_biz_maintainer": "admin", "bk_biz_productor": "admin", "life_cycle": "2", "bk_supplier_account": "0", "bk_biz_developer": ""},
        {"language": "1", "bk_biz_productor": "", "bk_biz_name": "蓝鲸", "bk_biz_maintainer": "admin", "default": 0, "operator": "", "bk_biz_id": 2, "time_zone": "Asia/Shanghai", "bk_biz_tester": "", "bk_biz_developer": "", "life_cycle": "2", "bk_supplier_account": "0"},
    ]
    SETS = [
        {"bk_service_status": "1", "description": "", "bk_set_id": 1, "bk_parent_id": 1, "bk_supplier_account": "0", "bk_set_env": "3", "bk_set_name": "空闲机池", "bk_biz_id": 1, "default": 1, "bk_set_desc": "", "bk_capacity": None, "set_template_id": 0},
        {"bk_biz_id": 2, "bk_supplier_account": "0", "bk_service_status": "1", "bk_parent_id": 2, "bk_set_env": "3", "description": "", "bk_capacity": None, "bk_set_name": "空闲机池", "default": 1, "bk_set_desc": "", "bk_set_id": 2, "set_template_id": 0},
    ]
    MODULES = [
        {"default": 1, "operator": "", "bk_set_id": 1, "bk_biz_id": 1, "bk_module_name": "空闲机", "bk_bak_operator": "", "bk_module_id": 1, "bk_parent_id": 1, "bk_supplier_account": "0", "bk_module_type": "1", "service_category_id": 2, "service_template_id": 0, "set_template_id": 0, "host_apply_enabled": False},
        {"bk_biz_id": 2, "default": 1, "bk_bak_operator": "", "bk_parent_id": 2, "bk_module_id": 3, "bk_set_id": 2, "bk_supplier_account": "0", "operator": "", "bk_module_name": "空闲机", "bk_module_type": "1", "service_category_id": 2, "service_template_id": 0, "set_template_id": 0, "host_apply_enabled": False},
        {"bk_bak_operator": "", "bk_parent_id": 2, "bk_module_name": "故障机", "default": 2, "bk_set_id": 2, "bk_biz_id": 2, "bk_module_id": 4, "bk_supplier_account": "0", "bk_module_type": "1", "operator": "", "service_category_id": 2, "service_template_id": 0, "set_template_id": 0, "host_apply_enabled": False},
        {"set_template_id": 0, "bk_module_type": "1", "operator": "", "service_category_id": 2, "default": 3, "bk_bak_operator": "", "bk_set_id": 2, "bk_supplier_account": "0", "bk_biz_id": 2, "bk_module_name": "待回收", "bk_parent_id": 2, "service_template_id": 0, "bk_module_id": 6, "host_apply_enabled": False},
    ]

    def migrate(self) -> None:
        ts = get_timestamp()
        self.ensure_collection("cc_ApplicationBase")
        for item in self.BUSINESSES:
            data = dict(item)
            data["bk_supplier_account"] = BK_DEFAULT_OWNER_ID
            data.setdefault("creator", BK_SYSTEM_OPERATOR)
            data["create_time"] = ts
            data["last_time"] = ts
            self.upsert("cc_ApplicationBase", data, ["bk_biz_id", "bk_supplier_account"])
        self.ensure_collection("cc_SetBase")
        for item in self.SETS:
            data = dict(item)
            data["bk_supplier_account"] = BK_DEFAULT_OWNER_ID
            self.upsert("cc_SetBase", data, ["bk_set_id", "bk_supplier_account"])
        self.ensure_collection("cc_ModuleBase")
        for item in self.MODULES:
            data = dict(item)
            data["bk_supplier_account"] = BK_DEFAULT_OWNER_ID
            self.upsert("cc_ModuleBase", data, ["bk_module_id", "bk_supplier_account"])


class IDGeneratorMigrate(BaseMigrate):
    """ID 自增序列 - 对齐 Go cc_idgenerator（_id=集合名, SequenceID=当前最大 id）

    为保证新建对象不与已种子 id 冲突，SequenceID 取「该集合已用最大 id」。
    Python 服务分类等采用非连续 id（最大 42），故必须按实际数据动态计算，
    不能直接套用 Go 的连续值（否则新建会撞已有 id）。
    仅对 Python 不产出数据、但应用会写入的集合（审计/图表/业务集）保留 Go 基准值。
    """

    # None -> 运行时按该集合当前最大 id 计算；数字 -> 直接使用（该集合 Python 不种子数据）
    SEQUENCE_BASES = {
        "cc_ObjClassification": None,
        "cc_PropertyGroup": None,
        "cc_ObjDes": None,
        "cc_ObjAttDes": None,
        "cc_ObjAsst": None,
        "cc_PlatBase": None,
        "cc_ApplicationBase": None,
        "cc_SetBase": None,
        "cc_ModuleBase": None,
        "cc_AsstDes": None,
        "cc_ObjectUnique": None,
        "cc_ServiceCategory": None,
        "cc_BizSetBase": 10000000,   # 业务集 id 空间起点（种子用 9991001，不冲突）
        "cc_AuditLog": 1,
        "cc_ChartConfig": 8,
    }

    def migrate(self) -> None:
        self.ensure_collection("cc_idgenerator")
        ts = get_timestamp()
        for name, base in self.SEQUENCE_BASES.items():
            if base is None:
                seq = 0
                if name in self.db.list_collection_names():
                    doc = self.db[name].find_one(sort=[("id", -1)])
                    if doc and "id" in doc:
                        seq = doc["id"]
            else:
                seq = base
            self.db["cc_idgenerator"].update_one(
                {"_id": name},
                {"$set": {"_id": name, "SequenceID": seq, "create_time": ts, "last_time": ts}},
                upsert=True)


def run_default_data_migrate(db) -> None:
    """执行默认种子数据迁移"""
    migrations = [
        ObjectUniqueMigrate(db),
        BizSetMigrate(db),
        DefaultBusinessMigrate(db),
        IDGeneratorMigrate(db),
    ]
    for m in migrations:
        print(f"Running migration: {m.__class__.__name__}")
        m.migrate()
    print("Default data migrate completed!")
