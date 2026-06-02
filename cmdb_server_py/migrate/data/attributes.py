"""
对象属性数据迁移

对应 Go 项目: src/scene_server/admin_server/upgrader/history/v3.0.8/objAttDescData.go
"""

from datetime import datetime
from typing import List, Dict, Any
from .. import BaseMigrate, get_timestamp, BK_DEFAULT_OWNER_ID, BK_SYSTEM_OPERATOR


STATE_ENUM = [{"id": "AR", "name": "阿根廷"}, {"id": "AD", "name": "安道尔"}, {"id": "AE", "name": "阿联酋"}, {"id": "CN", "name": "中国"}, {"id": "US", "name": "美国"}]

PROVINCES_ENUM = [
    {"id": "110000", "name": "北京市"}, {"id": "120000", "name": "天津市"}, {"id": "310000", "name": "上海市"},
    {"id": "320000", "name": "江苏省"}, {"id": "330000", "name": "浙江省"}, {"id": "440000", "name": "广东省"}
]

ISP_ENUM = [{"id": "0", "name": "其他"}, {"id": "1", "name": "电信"}, {"id": "2", "name": "联通"}, {"id": "3", "name": "移动"}]

LIFE_CYCLE_ENUM = [{"id": "1", "name": "测试中"}, {"id": "2", "name": "已上线", "default": True}, {"id": "3", "name": "停运"}]
LANGUAGE_ENUM = [{"id": "1", "name": "中文", "default": True}, {"id": "2", "name": "English"}]


class AttributeMigrate(BaseMigrate):
    """对象属性迁移"""

    ATTRIBUTES = [
        {"bk_obj_id": "biz", "bk_property_id": "bk_biz_name", "bk_property_name": "业务名", "bk_property_group": "base", "editable": True, "isreadonly": False, "isonly": True, "isrequired": True, "bk_property_type": "singlechar", "option": "", "ispre": True},
        {"bk_obj_id": "biz", "bk_property_id": "life_cycle", "bk_property_name": "生命周期", "bk_property_group": "base", "editable": True, "isreadonly": False, "isonly": False, "isrequired": False, "bk_property_type": "enum", "option": LIFE_CYCLE_ENUM, "ispre": True},
        {"bk_obj_id": "biz", "bk_property_id": "bkMaintainers", "bk_property_name": "运维人员", "bk_property_group": "role", "editable": True, "isreadonly": False, "isonly": False, "isrequired": True, "bk_property_type": "usercase", "option": "", "ispre": True},
        {"bk_obj_id": "biz", "bk_property_id": "time_zone", "bk_property_name": "时区", "bk_property_group": "base", "editable": False, "isreadonly": True, "isonly": False, "isrequired": True, "bk_property_type": "timezone", "option": "", "ispre": True},
        {"bk_obj_id": "biz", "bk_property_id": "language", "bk_property_name": "语言", "bk_property_group": "base", "editable": False, "isreadonly": True, "isonly": False, "isrequired": True, "bk_property_type": "enum", "option": LANGUAGE_ENUM, "ispre": True},

        {"bk_obj_id": "set", "bk_property_id": "bk_set_name", "bk_property_name": "集群名字", "bk_property_group": "base", "editable": True, "isreadonly": False, "isonly": True, "isrequired": True, "bk_property_type": "singlechar", "option": "", "ispre": True},
        {"bk_obj_id": "set", "bk_property_id": "bk_set_desc", "bk_property_name": "集群描述", "bk_property_group": "base", "editable": True, "isreadonly": False, "isonly": False, "isrequired": False, "bk_property_type": "singlechar", "option": "", "ispre": True},
        {"bk_obj_id": "set", "bk_property_id": "bk_set_env", "bk_property_name": "环境类型", "bk_property_group": "base", "editable": True, "isreadonly": False, "isonly": False, "isrequired": False, "bk_property_type": "enum", "option": [{"id": "1", "name": "测试"}, {"id": "2", "name": "体验"}, {"id": "3", "name": "正式", "default": True}], "ispre": True},

        {"bk_obj_id": "module", "bk_property_id": "bk_module_name", "bk_property_name": "模块名", "bk_property_group": "base", "editable": True, "isreadonly": False, "isonly": True, "isrequired": True, "bk_property_type": "singlechar", "option": "", "ispre": True},
        {"bk_obj_id": "module", "bk_property_id": "bk_module_type", "bk_property_name": "模块类型", "bk_property_group": "base", "editable": True, "isreadonly": False, "isonly": False, "isrequired": False, "bk_property_type": "enum", "option": [{"id": "1", "name": "普通", "default": True}, {"id": "2", "name": "数据库"}], "ispre": True},

        {"bk_obj_id": "plat", "bk_property_id": "bk_cloud_name", "bk_property_name": "云区域", "bk_property_group": "base", "editable": True, "isreadonly": False, "isonly": True, "isrequired": True, "bk_property_type": "singlechar", "option": "", "ispre": True},
        {"bk_obj_id": "plat", "bk_property_id": "bk_supplier_account", "bk_property_name": "供应商", "bk_property_group": "base", "editable": True, "isreadonly": False, "isonly": True, "isrequired": True, "bk_property_type": "singlechar", "option": "", "ispre": True},

        {"bk_obj_id": "host", "bk_property_id": "bk_host_innerip", "bk_property_name": "内网IP", "bk_property_group": "base", "editable": False, "isreadonly": False, "isonly": True, "isrequired": True, "bk_property_type": "singlechar", "option": "", "ispre": True},
        {"bk_obj_id": "host", "bk_property_id": "bk_host_outerip", "bk_property_name": "外网IP", "bk_property_group": "base", "editable": True, "isreadonly": False, "isonly": False, "isrequired": False, "bk_property_type": "singlechar", "option": "", "ispre": False},
        {"bk_obj_id": "host", "bk_property_id": "operator", "bk_property_name": "主要维护人", "bk_property_group": "base", "editable": True, "isreadonly": False, "isonly": False, "isrequired": False, "bk_property_type": "usercase", "option": "", "ispre": False},
        {"bk_obj_id": "host", "bk_property_id": "bk_bak_operator", "bk_property_name": "备份维护人", "bk_property_group": "base", "editable": True, "isreadonly": False, "isonly": False, "isrequired": False, "bk_property_type": "usercase", "option": "", "ispre": False},
        {"bk_obj_id": "host", "bk_property_id": "bk_cloud_id", "bk_property_name": "云区域", "bk_property_group": "base", "editable": False, "isreadonly": False, "isonly": True, "isrequired": False, "bk_property_type": "singleasst", "option": "", "ispre": True},
        {"bk_obj_id": "host", "bk_property_id": "bk_os_type", "bk_property_name": "操作系统类型", "bk_property_group": "auto", "editable": True, "isreadonly": False, "isonly": False, "isrequired": False, "bk_property_type": "enum", "option": [{"id": "1", "name": "Linux"}, {"id": "2", "name": "Windows"}], "ispre": False},
        {"bk_obj_id": "host", "bk_property_id": "bk_os_name", "bk_property_name": "操作系统名称", "bk_property_group": "auto", "editable": True, "isreadonly": False, "isonly": False, "isrequired": False, "bk_property_type": "singlechar", "option": "", "ispre": False},
        {"bk_obj_id": "host", "bk_property_id": "bk_cpu", "bk_property_name": "CPU逻辑核心数", "bk_property_group": "auto", "editable": True, "isreadonly": False, "isonly": False, "isrequired": False, "bk_property_type": "int", "option": {"min": "1", "max": "1000000"}, "ispre": False},
        {"bk_obj_id": "host", "bk_property_id": "bk_mem", "bk_property_name": "内存容量", "bk_property_group": "auto", "editable": True, "isreadonly": False, "isonly": False, "isrequired": False, "bk_property_type": "int", "option": {"min": "1", "max": "100000000"}, "ispre": False},
        {"bk_obj_id": "host", "bk_property_id": "bk_disk", "bk_property_name": "磁盘容量", "bk_property_group": "auto", "editable": True, "isreadonly": False, "isonly": False, "isrequired": False, "bk_property_type": "int", "option": {"min": "1", "max": "100000000"}, "ispre": False},

        {"bk_obj_id": "process", "bk_property_id": "bk_process_name", "bk_property_name": "进程名称", "bk_property_group": "base", "editable": True, "isreadonly": False, "isonly": True, "isrequired": True, "bk_property_type": "singlechar", "option": "", "ispre": True},
        {"bk_obj_id": "process", "bk_property_id": "bind_ip", "bk_property_name": "绑定IP", "bk_property_group": "port", "editable": True, "isreadonly": False, "isonly": False, "isrequired": False, "bk_property_type": "enum", "option": [{"id": "1", "name": "127.0.0.1"}, {"id": "2", "name": "0.0.0.0"}, {"id": "3", "name": "第一内网IP"}, {"id": "4", "name": "第一外网IP"}], "ispre": True},
        {"bk_obj_id": "process", "bk_property_id": "port", "bk_property_name": "端口", "bk_property_group": "port", "editable": True, "isreadonly": False, "isonly": False, "isrequired": False, "bk_property_type": "singlechar", "option": "", "ispre": True},
        {"bk_obj_id": "process", "bk_property_id": "protocol", "bk_property_name": "协议", "bk_property_group": "port", "editable": True, "isreadonly": False, "isonly": False, "isrequired": False, "bk_property_type": "enum", "option": [{"id": "1", "name": "TCP"}, {"id": "2", "name": "UDP"}], "ispre": True},
        {"bk_obj_id": "process", "bk_property_id": "auto_start", "bk_property_name": "是否自动拉起", "bk_property_group": "base", "editable": True, "isreadonly": False, "isonly": False, "isrequired": False, "bk_property_type": "bool", "option": "", "ispre": True},
    ]

    def migrate(self) -> None:
        self.ensure_collection("cc_ObjAttDes")
        ts = get_timestamp()
        for item in self.ATTRIBUTES:
            data = {
                **item,
                "bk_supplier_account": BK_DEFAULT_OWNER_ID,
                "creator": BK_SYSTEM_OPERATOR,
                "create_time": ts,
                "last_time": ts,
            }
            self.upsert("cc_ObjAttDes", data, ["bk_obj_id", "bk_property_id", "bk_supplier_account"])


def run_attribute_migrate(db) -> None:
    AttributeMigrate(db).migrate()
    print("Attribute migrate completed!")
