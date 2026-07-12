#!/usr/bin/env python3
"""
seed_extra.py —— 在 bk-cmdb init seed 之后，补充「1 个模拟业务 + N 台主机」

为什么需要它：
  bk-cmdb 的 init seed（POST /migrate/v3/migrate/community/0）只写入「模型定义」
  （cc_ObjectBase / cc_ObjAttDes / cc_PropertyGroup / 分类 …）与内置资源池
  （biz_id=1 资源池、set_id=1 空闲机池、module_id=1 空闲机），**不创建任何业务实例/主机实例**。
  本脚本补齐研发自测所需的业务拓扑与主机实例，使 Python 后端直接读 Mongo 时即有可用数据。

数据约定（与 init seed 产出的内置拓扑保持一致）：
  * 所有自增 ID 取自 cc_idgenerator.SequenceID（原子 $inc），避免与既有数据冲突；
  * bk_*_id 一律为 NumberLong；bk_host_innerip 以「列表」存储（bk-cmdb 真实形态）；
  * bk_supplier_account 固定 "0"（社区版单租户）；default=0（非资源池/空闲机）；
  * 主机 → 模块关系写入 cc_ModuleHostConfig（bk_biz_id/set/module/host 均为 NumberLong）。

连接串与 Go(mongodb.yaml) / Python(app.config) 完全一致，可通过环境变量覆盖：
  MONGODB_URI   默认 mongodb://cc:cc@127.0.0.1:27017/cmdb?authSource=cmdb
  SEED_BIZ_NAME 模拟业务名，默认 mock-biz-001
  SEED_HOST_COUNT 主机数量，默认 12
  SEED_IP_PREFIX 主机内网 IP 前缀，默认 10.10.10（生成 10.10.10.101..）
  SEED_SET_NAME / SEED_MODULE_NAME 集群/模块名（可选）

幂等/追加策略：
  同名业务不存在时创建业务/集群/模块 + N 台主机；已存在时向该业务「追加」N 台主机
  （沿用既有集群/模块，IP 与名称序号从现有主机数续接，避免冲突）。因此重复执行可安全地
  「再补 N 台」，而不会新建重复业务。

用法：
  python3 seed_extra.py                       # 首次：1 业务 + 12 主机
  SEED_HOST_COUNT=9 python3 seed_extra.py     # 向已有业务再追加 9 台主机
  SEED_HOST_COUNT=20 SEED_BIZ_NAME=demo-biz python3 seed_extra.py
"""
import os
import sys
from datetime import datetime, timezone

try:
    from pymongo import MongoClient
    from pymongo import ReturnDocument
    from bson import Int64
except ImportError:
    sys.exit("缺少 pymongo，请先安装: pip install pymongo")

MONGO_URI = os.environ.get("MONGODB_URI") or "mongodb://cc:cc@127.0.0.1:27017/cmdb?authSource=cmdb"
DB_NAME = os.environ.get("MONGODB_DB") or "cmdb"

SEED_BIZ_NAME = os.environ.get("SEED_BIZ_NAME") or "mock-biz-001"
SEED_SET_NAME = os.environ.get("SEED_SET_NAME") or "mock-set-001"
SEED_MODULE_NAME = os.environ.get("SEED_MODULE_NAME") or "mock-module-001"
SEED_HOST_COUNT = int(os.environ.get("SEED_HOST_COUNT") or "12")
SEED_IP_PREFIX = os.environ.get("SEED_IP_PREFIX") or "10.10.10"


def now_iso():
    return datetime.now(timezone.utc)


def connect():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    return client[DB_NAME]


def next_id(db, coll_name):
    """从 cc_idgenerator 原子自增取下一个 ID（与 bk-cmdb 一致）。

    返回 bson.Int64，使写入 Mongo 的 bk_*_id 与 Go init seed 产出的 NumberLong 完全一致，
    避免后续启用 Go 全栈或类型敏感查询时出现 32/64 位整型偏差。
    """
    doc = db.cc_idgenerator.find_one_and_update(
        {"_id": coll_name},
        {"$inc": {"SequenceID": 1}, "$set": {"last_time": now_iso()}},
        return_document=ReturnDocument.AFTER,
        upsert=True,
    )
    return Int64(doc["SequenceID"])


def seed_business(db):
    biz_id = next_id(db, "cc_ApplicationBase")
    t = now_iso()
    doc = {
        "bk_biz_id": biz_id,
        "bk_biz_name": SEED_BIZ_NAME,
        "bk_biz_maintainer": "admin",
        "bk_biz_productor": "admin",
        "bk_biz_developer": "",
        "bk_biz_tester": "",
        "operator": "",
        "life_cycle": "2",
        "language": "1",
        "bk_supplier_account": "0",
        "time_zone": "Asia/Shanghai",
        "default": 0,
        "create_time": t,
        "last_time": t,
    }
    db.cc_ApplicationBase.insert_one(doc)
    print(f"  [业务]   bk_biz_id={biz_id}  name={SEED_BIZ_NAME}")
    return biz_id


def seed_set(db, biz_id):
    set_id = next_id(db, "cc_SetBase")
    t = now_iso()
    doc = {
        "bk_set_id": set_id,
        "bk_biz_id": biz_id,
        "bk_parent_id": biz_id,
        "bk_set_name": SEED_SET_NAME,
        "bk_set_env": "3",
        "bk_service_status": "1",
        "default": 0,
        "bk_supplier_account": "0",
        "bk_set_desc": "",
        "description": "",
        "set_template_id": 0,
        "create_time": t,
        "last_time": t,
    }
    db.cc_SetBase.insert_one(doc)
    print(f"  [集群]   bk_set_id={set_id}  name={SEED_SET_NAME}  (biz={biz_id})")
    return set_id


def seed_module(db, biz_id, set_id):
    module_id = next_id(db, "cc_ModuleBase")
    t = now_iso()
    doc = {
        "bk_module_id": module_id,
        "bk_set_id": set_id,
        "bk_parent_id": set_id,
        "bk_biz_id": biz_id,
        "bk_module_name": SEED_MODULE_NAME,
        "bk_module_type": "1",
        "default": 0,
        "service_category_id": Int64(2),
        "service_template_id": 0,
        "set_template_id": 0,
        "host_apply_enabled": False,
        "bk_supplier_account": "0",
        "operator": "",
        "bk_bak_operator": "",
        "create_time": t,
        "last_time": t,
    }
    db.cc_ModuleBase.insert_one(doc)
    print(f"  [模块]   bk_module_id={module_id}  name={SEED_MODULE_NAME}  (set={set_id})")
    return module_id


def seed_hosts(db, biz_id, set_id, module_id, start=1):
    """向指定业务/集群/模块写入 SEED_HOST_COUNT 台主机。

    start: 主机序号起点（默认 1）。向已存在业务「追加」时传入现有主机数 + 1，
    使 IP（10.10.10.{100+i}）与名称（mock-host-{i:02d}）续接，避免与既有主机冲突。
    """
    created = []
    for n in range(SEED_HOST_COUNT):
        i = start + n
        host_id = next_id(db, "cc_HostBase")
        ip = f"{SEED_IP_PREFIX}.{100 + i}"
        t = now_iso()
        # 字段结构对齐 init seed 产出的内置主机（bk_host_innerip 为列表）
        doc = {
            "bk_host_id": host_id,
            "bk_host_innerip": [ip],
            "bk_cloud_id": Int64(0),
            "bk_supplier_account": "0",
            "bk_host_name": f"mock-host-{i:02d}",
            "bk_cpu_architecture": "x86",
            "bk_os_name": "Linux",
            "bk_os_type": "linux",
            "bk_mem": 16384,
            "bk_disk": 500,
            "bk_cpu": 8,
            "bk_asset_id": "",
            "bk_comment": "mock-seed",
            "operator": "admin",
            "import_from": None,
            "bk_cloud_host_status": None,
            "bk_cloud_vendor": None,
            "bk_province_name": None,
            "bk_service_term": None,
            "bk_state": None,
            "bk_state_name": None,
            "create_time": t,
            "last_time": t,
        }
        db.cc_HostBase.insert_one(doc)
        # 主机 → 模块关系（一主机一模块，幂等靠唯一索引保证）
        db.cc_ModuleHostConfig.insert_one({
            "bk_biz_id": biz_id,
            "bk_host_id": host_id,
            "bk_module_id": module_id,
            "bk_set_id": set_id,
            "bk_supplier_account": "0",
        })
        created.append((host_id, ip))
    print(f"  [主机]   共创建 {len(created)} 台，示例: "
          + ", ".join(f"id={h}/ip={ip}" for h, ip in created[:3]) + " ...")
    return created


def fix_required_fields(db):
    """把各模型「名称字段」标记为必填（is_required=true），使前端创建/编辑实例时强制必填校验。

    背景：本地 init seed（Go adminserver migrate）写入的 cc_ObjAttDes 未带 is_required，
    导致前端创建交换机等通用对象实例时不提示必填项（提交空名称也能成功）。
    真实 bk-cmdb 中名称字段默认必填，这里对齐。
    名称字段映射：biz->bk_biz_name、host->bk_host_name、set->bk_set_name、
    module->bk_module_name、process->bk_process_name、plat/cloud_area->bk_cloud_name、
    其余通用对象->bk_inst_name（如 bk_switch.bk_inst_name）。
    """
    NAME_FIELD = {
        "biz": "bk_biz_name",
        "bk_biz_set_obj": "bk_biz_set_name",
        "set": "bk_set_name",
        "module": "bk_module_name",
        "host": "bk_host_name",
        "process": "bk_process_name",
        "plat": "bk_cloud_name",
        "cloud_area": "bk_cloud_name",
    }
    obj_ids = db.cc_ObjAttDes.distinct("bk_obj_id")
    total = 0
    for obj in obj_ids:
        name_prop = NAME_FIELD.get(obj, "bk_inst_name")
        res = db.cc_ObjAttDes.update_many(
            {"bk_obj_id": obj, "bk_property_id": name_prop},
            {"$set": {"is_required": True}},
        )
        total += res.modified_count
    # 兜底：将历史遗留的 undefined is_required 显式置 false，避免歧义
    db.cc_ObjAttDes.update_many(
        {"is_required": {"$exists": False}},
        {"$set": {"is_required": False}},
    )
    print(f"  [必填]   标记名称字段 is_required=true 共 {total} 条属性")


def main():
    print("=" * 64)
    print("bk-cmdb 补充种子数据：1 模拟业务 + %d 主机" % SEED_HOST_COUNT)
    print("=" * 64)
    db = connect()
    print("MongoDB 连接成功 -> db='%s'" % DB_NAME)

    # 幂等策略（支持「追加」主机）：
    #   * 同名业务不存在 -> 创建业务/集群/模块 + SEED_HOST_COUNT 台主机（首次 seed）；
    #   * 同名业务已存在 -> 沿用既有集群/模块，向其「追加」SEED_HOST_COUNT 台主机，
    #     序号从现有主机数续接，避免 IP / 名称冲突（用于「再加 N 台」场景）。
    existing = db.cc_ApplicationBase.find_one({"bk_biz_name": SEED_BIZ_NAME})
    if existing:
        biz_id = existing["bk_biz_id"]
        set_doc = db.cc_SetBase.find_one({"bk_biz_id": biz_id}) or {}
        set_id = set_doc.get("bk_set_id", biz_id)
        mod_doc = db.cc_ModuleBase.find_one({"bk_set_id": set_id}) or {}
        module_id = mod_doc.get("bk_module_id", set_id)
        start = db.cc_ModuleHostConfig.count_documents({"bk_biz_id": biz_id}) + 1
        print(f"[追加] 业务 '{SEED_BIZ_NAME}'(id={biz_id}) 已存在，"
              f"向其追加 {SEED_HOST_COUNT} 台主机（起始序号 {start}）。")
        seed_hosts(db, biz_id, set_id, module_id, start=start)
    else:
        biz_id = seed_business(db)
        set_id = seed_set(db, biz_id)
        module_id = seed_module(db, biz_id, set_id)
        seed_hosts(db, biz_id, set_id, module_id)

    # 校验
    n_host = db.cc_HostBase.count_documents({"bk_supplier_account": "0"})

    # 修复：各模型名称字段标记为必填（前端创建/编辑实例强制必填校验）
    fix_required_fields(db)
    n_rel = db.cc_ModuleHostConfig.count_documents({"bk_biz_id": biz_id})
    print("-" * 64)
    print(f"完成：业务 {SEED_BIZ_NAME}(id={biz_id}) 下，本次新增主机 {SEED_HOST_COUNT} 台，"
          f"该业务关系 {n_rel} 条。")
    print(f"当前 cc_HostBase 主机总数: {n_host}")
    print("Python 后端现在可通过 /search/instances/object/host 等接口读取这些数据。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
