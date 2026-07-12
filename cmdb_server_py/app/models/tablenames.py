"""MongoDB 元数据集合（表）名常量。

对齐 bk-cmdb Go 端 ``common/tablenames.go``：模型元数据（对象模型、属性、分类、
关联、唯一规则、属性分组）的物理存储集合名集中在此定义，业务层与路由层统一引用，
避免散落硬编码。

bk-cmdb 的**模型元数据**全部以独立 collection 存储（而非分片）：
  - cc_ObjDes            模型（object）定义本体
  - cc_ObjAttDes         模型属性（字段）定义
  - cc_ObjClassification 模型分类（分组）
  - cc_ObjAsst           模型间关联关系
  - cc_ObjectUnique      模型唯一性校验规则
  - cc_PropertyGroup     属性分组
  - cc_AsstDes           关联类型（association kind）定义

而**模型实例数据**则按 supplier account + 对象 ID 动态分片（见 ``get_object_inst_table_name``），
这正是 id0/id1 供应商账户隔离在存储层的落地方式。
"""

# 模型元数据集合名（对齐 common/tablenames.go 的 BKTableName* 常量）
BK_TABLE_NAME_OBJ_DES = "cc_ObjDes"
BK_TABLE_NAME_OBJ_ATT_DES = "cc_ObjAttDes"
BK_TABLE_NAME_OBJ_CLASSIFICATION = "cc_ObjClassification"
BK_TABLE_NAME_OBJ_ASST = "cc_ObjAsst"
BK_TABLE_NAME_OBJ_UNIQUE = "cc_ObjectUnique"
BK_TABLE_NAME_PROPERTY_GROUP = "cc_PropertyGroup"
BK_TABLE_NAME_ASST_DES = "cc_AsstDes"  # 关联类型（associationtype）

# 实例分片表前缀（对齐 common/tablenames.go 的 cc_ObjectBase / cc_InstAsst）
BK_TABLE_NAME_OBJECT_BASE_PREFIX = "cc_ObjectBase"
BK_TABLE_NAME_INST_ASST_PREFIX = "cc_InstAsst"

# 内置对象使用固定集合（不走分片），对齐 common/metadata.GetInstTableNameByObjID
_FIXED_OBJECT_TABLES = {
    "biz": "cc_ApplicationBase",
    "bk_biz_set_obj": "cc_BizSetBase",
    "set": "cc_SetBase",
    "module": "cc_ModuleBase",
    "host": "cc_HostBase",
    "process": "cc_Process",
    "plat": "cc_PlatBase",
    "cloud_area": "cc_PlatBase",
}


def get_object_inst_table_name(obj_id, supplier_account="0"):
    """返回某对象的实例数据集合名（对齐 common/tablenames.go GetObjectInstTableName）。

    内置对象（业务/集群/模块/主机/进程/平台…）走固定集合；
    通用/自定义对象按 ``cc_ObjectBase_{supplierAccount}_pub_{objectID}`` 分片，
    如 ``cc_ObjectBase_0_pub_bk_switch``。
    """
    if obj_id in _FIXED_OBJECT_TABLES:
        return _FIXED_OBJECT_TABLES[obj_id]
    return f"{BK_TABLE_NAME_OBJECT_BASE_PREFIX}_{supplier_account}_pub_{obj_id}"


def get_inst_asst_table_name(obj_id, supplier_account="0"):
    """返回某对象的实例关联关系集合名（对齐 common/tablenames.go GetInstTableName）。"""
    if obj_id in _FIXED_OBJECT_TABLES:
        return _FIXED_OBJECT_TABLES[obj_id]
    return f"{BK_TABLE_NAME_INST_ASST_PREFIX}_{supplier_account}_pub_{obj_id}"
