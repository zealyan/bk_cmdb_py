# 蓝鲸 CMDB init_db 数据初始化分析报告

> 源码版本：`bk-cmdb release-v3.10.41`  
> 分析范围：Go 语言编写的数据库初始化（init_db）全流程

---

## 一、整体架构概述

### 1.1 init_db 是什么

"init_db" 在 bk-cmdb 中指数据库的**首次初始化 + 版本化增量升级**机制。它不是一个单次脚本，而是一套由 **admin_server** 的 **migrate 服务** 管理的、按版本号顺序执行的 **升级器链（Upgrader Chain）**。

核心特点：
- **幂等性**：每个版本的升级器可重复执行，通过 `Upsert`（先查后插/更新）确保数据不重复
- **版本追踪**：`cc_System` 表记录当前已执行的 migrate 版本号，重启后自动从断点继续
- **排序执行**：所有注册的升级器按版本号字符串排序后依次执行

### 1.2 代码入口调用链

```
main() [migrate.go]
  └─ app.Run() [app/server.go]
       ├─ 初始化 MongoDB / Redis / WatchDB 连接
       └─ HTTP: POST /migrate/v3/migrate/{distribution}/{ownerID}
            └─ service.migrate() [service/migrate.go]
                 ├─ createWatchDBChainCollections()    ← 创建 watch 事件链表
                 └─ upgrader.Upgrade() [upgrader/register.go]
                      └─ 遍历所有 Upgrader（按版本号排序）
                           ├─ v3.0.8: 建表 + 预置数据
                           ├─ v3.0.9-beta.1 … x18.12.13.01 … 
                           └─ y3.10.202209231617: 最新版本
```

### 1.3 核心文件清单

| 文件 | 职责 |
|------|------|
| `src/scene_server/admin_server/upgrader/register.go` | 升级器注册框架、版本比较、`Upgrade()` 主循环 |
| `src/scene_server/admin_server/upgrader/history/v3.0.8/pkg.go` | **最初始版本的 upgrade() 入口**（建表 + 预置数据） |
| `src/scene_server/admin_server/upgrader/history/v3.0.8/createtable.go` | **所有初始表的创建和索引定义** |
| `src/scene_server/admin_server/upgrader/history/v3.0.8/addPresetObjects.go` | **预置模型/属性/关联/分类/属性分组的种子数据** |
| `src/scene_server/admin_server/upgrader/history/v3.0.8/objAttDescData.go` | **所有预置模型的属性定义**（含 SwitchRow 等） |
| `src/scene_server/admin_server/logics/index.go` | 运行时动态创建模型分片表和索引同步 |
| `src/common/tablenames.go` | 所有表名常量和分片表命名规则 |
| `src/common/definitions.go` | 内置模型 ID 常量（`bk_switch` 等） |

---

## 二、数据库表结构全景

### 2.1 表分类

CMDB 的表分为三类：

| 类别 | 说明 | 举例 |
|------|------|------|
| **元数据表** | 存储模型定义、属性、分类、关联等元信息 | `cc_ObjDes`, `cc_ObjAttDes`, `cc_ObjClassification`, `cc_ObjAsst`, `cc_PropertyGroup`, `cc_ObjectUnique` |
| **内置实例表** | 存储拓扑核心模型（业务/集群/模块/主机/进程/云区域）的实例 | `cc_ApplicationBase`, `cc_SetBase`, `cc_ModuleBase`, `cc_HostBase`, `cc_Process`, `cc_PlatBase` |
| **分片实例表** | 通用模型（如交换机、路由器等）的实例按 objectID 分片 | `cc_ObjectBase_{supplier}_pub_{objID}` |

### 2.2 六张核心元数据表

这是 CMDB 模型驱动架构的基石，**所有元数据表在 v3.0.8 首次创建**：

#### ① cc_ObjClassification — 模型分类表

定义模型的顶层分组，如"主机管理"、"业务拓扑"、"网络"。

| 字段 | 说明 |
|------|------|
| `bk_classification_id` | 分类 ID（有唯一索引），如 `bk_network` |
| `bk_classification_name` | 分类名称，如"网络" |
| `bk_classification_type` | 分类类型，值为 `inner` |
| `bk_classification_icon` | 分类图标 |

初始数据（4 条）：

| ClassificationID | ClassificationName | 说明 |
|---|---|---|
| `bk_host_manage` | 主机管理 | 包含 host、process、plat |
| `bk_biz_topo` | 业务拓扑 | 包含 set、module |
| `bk_organization` | 组织架构 | 包含 biz |
| `bk_network` | 网络 | 包含 bk_switch、bk_router、bk_load_balance、bk_firewall |

#### ② cc_ObjDes — 模型定义表

定义每个 CMDB 模型的元信息。

| 字段 | 说明 |
|------|------|
| `bk_obj_id` | 模型 ID（有唯一索引），如 `bk_switch` |
| `bk_obj_name` | 模型名称（有唯一索引），如"交换机" |
| `bk_classification_id` | 所属分类 ID |
| `bk_supplier_account` | 供应商账号 |
| `ispre` | 是否预置模型（true=内置） |
| `bk_obj_icon` | 模型图标 |
| `position` | 拓扑图位置（JSON） |

#### ③ cc_ObjAttDes — 属性定义表

定义每个模型的字段。

| 字段 | 说明 |
|------|------|
| `bk_obj_id` | 所属模型 ID |
| `bk_property_id` | 属性 ID |
| `bk_property_name` | 属性名称 |
| `bk_property_type` | 属性类型（singlechar/int/enum/longchar/time/user 等） |
| `bk_property_group` | 所属属性分组 |
| `isrequired` | 是否必填 |
| `isonly` | 是否唯一 |
| `ispre` | 是否预置 |
| `editable` | 是否可编辑 |
| `option` | 属性选项（枚举值列表、整数范围等） |

#### ④ cc_PropertyGroup — 属性分组表

定义属性在 UI 上的分组显示。

| 字段 | 说明 |
|------|------|
| `bk_obj_id` | 所属模型 ID |
| `bk_group_id` | 分组 ID |
| `bk_group_name` | 分组名称 |
| `bk_group_index` | 分组排序 |

#### ⑤ cc_ObjAsst — 模型关联表

定义模型之间的关联关系。

| 字段 | 说明 |
|------|------|
| `bk_obj_id` | 源模型 ID |
| `bk_asst_obj_id` | 目标模型 ID |
| `bk_object_att_id` | 关联属性 ID |
| `bk_asst_forward` | 关联方向 |
| `bk_asst_name` | 关联名称 |

#### ⑥ cc_ObjectUnique — 唯一约束表

定义逻辑唯一约束（在 v3.0.8 之后版本创建，由 `x18.11.19.01` 升级器引入）。

| 字段 | 说明 |
|------|------|
| `bk_obj_id` | 所属模型 ID |
| `keys` | 构成唯一的属性组合 |
| `ispre` | 是否预置 |

### 2.3 内置实例表

这些表存储具体业务数据，每个表有独立的 schema 和索引：

| 表名 | 存储内容 | 关键索引 |
|------|---------|---------|
| `cc_ApplicationBase` | 业务实例 | `bk_biz_id`, `bk_biz_name`, `bk_default` |
| `cc_SetBase` | 集群实例 | `bk_set_id`, `bk_parent_id`, `bk_biz_id`, `bk_set_name` |
| `cc_ModuleBase` | 模块实例 | `bk_module_id`, `bk_module_name`, `bk_biz_id`, `bk_set_id`, `bk_parent_id` |
| `cc_HostBase` | 主机实例 | `bk_host_id`, `bk_host_name`, `bk_host_innerip`, `bk_host_outerip` |
| `cc_Process` | 进程实例 | `bk_process_id`, `bk_biz_id` |
| `cc_PlatBase` | 云区域实例 | `bk_supplier_account` |
| `cc_ModuleHostConfig` | 主机-模块关系 | `bk_biz_id`, `bk_host_id`, `bk_module_id`, `bk_set_id` |

### 2.4 分片实例表（通用模型）

对于非内置模型（`IsPre=false`），如交换机、路由器等，其实例存储采用动态分片策略：

```
表名格式: cc_ObjectBase_{supplierAccount}_pub_{objectID}
示例:     cc_ObjectBase_0_pub_bk_switch
```

关联实例表同理：
```
表名格式: cc_InstAsst_{supplierAccount}_pub_{objectID}
示例:     cc_InstAsst_0_pub_bk_switch
```

分片表在 v3.10 引入，由 `y3.10.202104221702` 升级器将原 `cc_ObjectBase` 统一表拆分为按模型分片的表。

### 2.5 系统与辅助表

| 表名 | 用途 |
|------|------|
| `cc_System` | 存储系统配置和版本信息（`type: "version"` 记录当前 migrate 版本） |
| `cc_AuditLog` | 操作审计日志 |
| `cc_History` | 历史记录 |
| `cc_TopoGraphics` | 拓扑图配置 |
| `cc_InstAsst` | 实例关联关系 |
| `cc_Subscription` | 事件订阅配置 |
| `cc_idgenerator` | ID 生成器 |
| `cc_DelArchive` | 删除归档 |
| `cc_HostLock` | 主机锁定记录 |

---

## 三、以"交换机（Switch）"为典型案例的完整分析

### 3.1 交换机模型涉及的所有表

当初始化交换机模型时，数据会写入以下表：

```
┌─────────────────────────────────────────────────────────────┐
│                     元数据层（6 张表）                         │
├──────────────────┬──────────────────────────────────────────┤
│ cc_ObjClassification │ 写入 "bk_network" 分类                   │
│ cc_ObjDes            │ 写入交换机模型定义 (bk_obj_id="bk_switch") │
│ cc_ObjAttDes         │ 写入交换机 11 个属性定义                  │
│ cc_PropertyGroup     │ 写入交换机属性分组                          │
│ cc_ObjAsst           │ 写入交换机与其他模型的关联关系                │
│ cc_ObjectUnique      │ 写入交换机唯一约束（如有）                    │
├──────────────────┼──────────────────────────────────────────┤
│                     实例数据层（2 张表）                       │
├──────────────────┼──────────────────────────────────────────┤
│ cc_ObjectBase_0_pub_bk_switch  │ 交换机实例数据（分片表）     │
│ cc_InstAsst_0_pub_bk_switch    │ 交换机实例关联数据（分片表）  │
└──────────────────┴──────────────────────────────────────────┘
```

**共计 8 张表**：6 张元数据表 + 2 张分片实例表。

### 3.2 交换机模型定义数据

模型定义（写入 `cc_ObjDes`）：

```json
{
  "bk_classification_id": "bk_network",
  "bk_obj_id": "bk_switch",
  "bk_obj_name": "交换机",
  "ispre": false,
  "bk_obj_icon": "icon-cc-switch2",
  "position": "{\"bk_network\":{\"x\":-200,\"y\":-50}}"
}
```

### 3.3 交换机 11 个预置属性

属性数据（写入 `cc_ObjAttDes`，来自 `SwitchRow()` 函数）：

| 序号 | PropertyID | PropertyName | PropertyType | IsRequired | IsOnly | IsPre | 说明 |
|------|-----------|-------------|-------------|-----------|--------|-------|------|
| 1 | `bk_asset_id` | 固资编号 | singlechar | ✅ true | ✅ true | ✅ true | 唯一标识，不可编辑 |
| 2 | `bk_inst_name` | 名称 | singlechar | ✅ true | ❌ false | ✅ true | 实例名称 |
| 3 | `bk_sn` | SN | singlechar | ❌ false | ❌ false | ❌ false | 设备序列号 |
| 4 | `bk_func` | 用途 | singlechar | ❌ false | ❌ false | ❌ false | 设备用途说明 |
| 5 | `bk_vendor` | 厂商 | singlechar | ❌ false | ❌ false | ❌ false | 设备厂商 |
| 6 | `bk_model` | 设备型号 | singlechar | ❌ false | ❌ false | ❌ false | 型号 |
| 7 | `bk_admin_ip` | 管理IP | singlechar | ❌ false | ❌ false | ❌ false | 支持多 IP 格式 |
| 8 | `bk_operator` | 维护人 | singlechar | ❌ false | ❌ false | ❌ false | 维护人员 |
| 9 | `bk_os_detail` | 操作系统详情 | singlechar | ❌ false | ❌ false | ❌ false | 操作系统信息 |
| 10 | `bk_detail` | 详细描述 | longchar | ❌ false | ❌ false | ❌ false | 长文本描述 |
| 11 | `bk_biz_status` | 运营状态 | enum | ❌ false | ❌ false | ❌ false | 枚举：待运营/运营中/已下架 |

> **注意**：`bk_name` 属性在交换机模型初始化时被**显式删除**（见 `addObjAttDescData()` 中末尾的 `db.Table(tablename).Delete()`），统一使用 `bk_inst_name`。

### 3.4 交换机属性分组

属性分组数据（写入 `cc_PropertyGroup`）：

| GroupID | GroupName | GroupIndex | 包含属性 |
|---------|-----------|------------|---------|
| `default` | 基础信息 | 1 | 全部 11 个属性 |

### 3.5 交换机与主机的关联关系

在 `x18.12.13.01` 版本中（`addswitchAssociation.go`），创建了交换机与主机之间的连接关联：

```
bk_switch  ──connect(一对多)──▶  host
关联名称: bk_switch_connect_host
```

写入 `cc_ObjAsst` 表的数据：

```json
{
  "bk_obj_id": "bk_switch",
  "bk_asst_obj_id": "host",
  "bk_asst_name": "bk_switch_connect_host",
  "bk_asst_kind_id": "connect",
  "mapping": "1:n"
}
```

### 3.6 交换机实例分片表索引

由 `RunSyncDBTableIndex()` 在运行时自动为 `cc_ObjectBase_0_pub_bk_switch` 创建默认实例索引：
- `bk_inst_id` (唯一索引)
- `bk_obj_id` + `bk_supplier_account` (复合索引)

---

## 四、数据初始化顺序与依赖关系

### 4.1 v3.0.8 首次初始化的完整顺序

`upgrade()` 函数中的执行顺序是**严格有序**的，每一步依赖前面步骤的完成：

```
Step 1: createTable()              ─── 创建所有物理表 + 索引
         ↓ 依赖：无（最底层）
Step 2: addClassifications()       ─── 写入 4 个模型分类
         ↓ 依赖：cc_ObjClassification 表已存在
Step 3: addPropertyGroupData()     ─── 写入属性分组
         ↓ 依赖：cc_PropertyGroup 表已存在
Step 4: addObjDesData()            ─── 写入 10 个预置模型定义
         ↓ 依赖：cc_ObjDes 表已存在 + 分类数据已写入
Step 5: addObjAttDescData()        ─── 写入所有模型属性
         ↓ 依赖：cc_ObjAttDes 表已存在 + 模型定义已写入
Step 6: addAsstData()              ─── 写入预置关联关系
         ↓ 依赖：cc_ObjAsst 表已存在 + 模型定义已写入
Step 7: addPlatData()              ─── 写入默认云区域实例
         ↓ 依赖：cc_PlatBase 表已存在
Step 8: addSystemData()            ─── 写入系统配置
         ↓ 依赖：cc_System 表已存在
Step 9: addDefaultBiz()            ─── 创建默认业务/集群/模块
         ↓ 依赖：内置实例表 + 云区域数据
Step 10: addBKApp()                ─── 创建蓝鲸业务
         ↓ 依赖：默认业务/集群/模块已创建
```

### 4.2 元数据层的严格依赖链

```
cc_ObjClassification (分类)
    │
    └──▶ cc_ObjDes (模型)  ── 每个模型必须引用一个分类
              │
              ├──▶ cc_PropertyGroup (属性分组)  ── 每个分组引用一个模型
              │
              ├──▶ cc_ObjAttDes (属性)  ── 每个属性引用一个模型 + 一个分组
              │
              ├──▶ cc_ObjAsst (模型关联)  ── 关联两端引用模型
              │
              └──▶ cc_ObjectUnique (唯一约束)  ── 约束引用模型 + 属性
```

### 4.3 实例层依赖元数据层

```
元数据层完成
    │
    ├──▶ 内置实例表 (cc_ApplicationBase, cc_SetBase, cc_ModuleBase, cc_HostBase...)
    │        └── 实例写入时需要 uc_ObjDes 中定义的字段 schema
    │
    └──▶ 分片实例表 (cc_ObjectBase_0_pub_bk_switch...)
             └── 表在 v3.10 后由 RunSyncDBTableIndex() 自动创建
```

### 4.4 完整依赖拓扑图

```
                    ┌──────────────┐
                    │ createTable  │  ← 物理建表 (v3.0.8)
                    └──────┬───────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                 ▼
┌─────────────────┐ ┌─────────────┐ ┌──────────────┐
│addClassifications│ │addProperty  │ │ addSystem/   │
│ (分类: 4条)      │ │ GroupData   │ │ Plat/Default │
└────────┬────────┘ └──────┬──────┘ │ Biz/BKApp    │
         │                 │        └──────────────┘
         ▼                 │
┌─────────────────┐        │
│  addObjDesData  │        │
│ (模型: 10个)     │        │
└────────┬────────┘        │
         │                 │
         ▼                 ▼
┌─────────────────────────────────┐
│        addObjAttDescData        │  ← 属性定义 (引用模型+分组)
│  10个模型的所有属性, 含SwitchRow │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│          addAsstData            │  ← 模型关联 (引用模型)
│   4条预置拓扑关联 + 后续版本新增  │
└─────────────────────────────────┘

         后续版本增量升级 (按时间顺序)
                 │
    ┌────────────┼────────────┬─────────────┐
    ▼            ▼            ▼             ▼
x18.11.19.01  x18.12.13.01  y3.10.*    y3.10.*
创建唯一约束  添加交换机     拆分实例表   同步分片表
cc_ObjectUnique  关联关系    分片化      索引创建
```

---

## 五、Upsert 机制：数据初始化的核心

### 5.1 工作原理

所有种子数据通过 `upgrader.Upsert()` 写入，位于 `src/scene_server/admin_server/upgrader/util.go`：

```go
// 伪代码逻辑
func Upsert(ctx, db, tableName, data, idField, uniqueFields, ignoreUpdateFields) {
    // 1. 根据 uniqueFields 构造查询条件
    condition := {uniqueField1: data.uniqueField1, ...}
    
    // 2. 查询是否已存在
    existing := db.Table(tableName).Find(condition).One(ctx)
    
    // 3. 不存在则 Insert
    if notFound {
        db.Table(tableName).Insert(ctx, data)
        return created
    }
    
    // 4. 已存在则 Update（跳过 ignoreUpdateFields 中的字段）
    db.Table(tableName).Update(ctx, condition, data)
    return updated
}
```

### 5.2 各表的 Upsert 唯一键

| 表 | uniqueFields（用于判断记录是否存在） | ignoreUpdateFields |
|-----|--------------------------------------|-------------------|
| `cc_ObjClassification` | `bk_classification_id` | `id` |
| `cc_ObjDes` | `bk_obj_id` + `bk_classification_id` + `bk_supplier_account` | `id` |
| `cc_ObjAttDes` | `bk_obj_id` + `bk_property_id` + `bk_supplier_account` | — |
| `cc_PropertyGroup` | `bk_obj_id` + `bk_group_id` | `id` |
| `cc_ObjAsst` | `bk_obj_id` + `bk_obj_att_id` + `bk_supplier_account` | `id`, `bk_asst_obj_id` |

这种设计保证了**重复执行 init_db 不会产生重复数据**，是实现幂等性的关键。

---

## 六、通用模型数据迁移指南

### 6.1 一个典型模型实例涉及的全部表

以"自定义一个模型并添加一个实例"为例，需要操作以下表：

```
阶段一：定义模型（元数据）
  ├── cc_ObjClassification     ← 1 条分类记录
  ├── cc_ObjDes                ← 1 条模型定义
  ├── cc_ObjAttDes             ← N 条属性定义 (每个属性 1 条)
  ├── cc_PropertyGroup         ← M 条属性分组 (至少 1 个默认分组)
  ├── cc_ObjAsst               ← K 条模型关联 (如与 host 关联)
  └── cc_ObjectUnique          ← U 条唯一约束 (可选)

阶段二：写入实例（实例数据）
  └── cc_ObjectBase_{supplier}_pub_{objID}  ← 实例分片表 (模型 ID 参与表名)

阶段三：写入实例关联（如有）
  └── cc_InstAsst_{supplier}_pub_{objID}    ← 实例关联分片表
```

### 6.2 通用数据迁移步骤

#### Step 1：创建模型分类

确保目标分类已存在。查询 `cc_ObjClassification`：

```json
{
  "bk_classification_id": "my_category",
  "bk_classification_name": "我的分类",
  "bk_classification_type": "inner",
  "bk_classification_icon": "icon-cc-default"
}
```

#### Step 2：注册模型定义

写入 `cc_ObjDes`：

```json
{
  "bk_classification_id": "my_category",
  "bk_obj_id": "my_model",
  "bk_obj_name": "我的模型",
  "ispre": false,
  "bk_obj_icon": "icon-cc-default"
}
```

#### Step 3：定义属性分组

写入 `cc_PropertyGroup`：

```json
{
  "bk_obj_id": "my_model",
  "bk_group_id": "default",
  "bk_group_name": "基础信息",
  "bk_group_index": 1
}
```

#### Step 4：定义模型属性

对每个属性写入 `cc_ObjAttDes`：

```json
{
  "bk_obj_id": "my_model",
  "bk_property_id": "my_field",
  "bk_property_name": "我的字段",
  "bk_property_type": "singlechar",
  "bk_property_group": "default",
  "isrequired": true,
  "isonly": true,
  "ispre": true,
  "editable": true
}
```

#### Step 5：定义模型关联（可选）

写入 `cc_ObjAsst`，如关联到主机：

```json
{
  "bk_obj_id": "my_model",
  "bk_asst_obj_id": "host",
  "bk_asst_name": "my_model_connect_host",
  "bk_asst_kind_id": "connect",
  "mapping": "1:n"
}
```

#### Step 6：创建分片实例表

通过 admin_server 的 `RunSyncDBTableIndex()` 自动创建表 `cc_ObjectBase_0_pub_my_model`，或手动调用 `CreateTable`。

#### Step 7：写入实例数据

向 `cc_ObjectBase_0_pub_my_model` 写入具体实例。

#### Step 8：写入实例关联（可选）

向 `cc_InstAsst_0_pub_my_model` 写入实例间关联。

### 6.3 关键注意事项

| 注意事项 | 说明 |
|---------|------|
| **分类必须先于模型** | `cc_ObjDes.bk_classification_id` 必须引用已存在的 `cc_ObjClassification` 记录 |
| **模型必须先于属性** | `cc_ObjAttDes.bk_obj_id` 必须引用已存在的模型 |
| **属性分组必须先于属性** | `cc_ObjAttDes.bk_property_group` 必须引用已存在的分组 |
| **表必须先于数据** | 物理表必须在写入数据前创建（含索引） |
| **分片表由后台自动创建** | v3.10 后，非内置模型的实例表由 `RunSyncDBTableIndex()` 自动同步，不能手动建表 |
| **内置模型有专用表** | `biz/set/module/host/process/plat` 有独立表名（如 `cc_HostBase`），不走分片机制 |
| **使用 Upsert 保证幂等** | 重复执行迁移不会产生重复数据 |
| **唯一约束在 v3.0.8 之后版本创建** | `cc_ObjectUnique` 表由 `x18.11.19.01` 升级器引入 |

### 6.4 判断模型走哪种表

```go
// 代码逻辑 (tablenames.go)
func GetInstTableName(objID, supplierAccount string) string {
    switch objID {
    case "biz":        return "cc_ApplicationBase"     // 内置，独立表
    case "set":        return "cc_SetBase"             // 内置，独立表
    case "module":     return "cc_ModuleBase"          // 内置，独立表
    case "host":       return "cc_HostBase"            // 内置，独立表
    case "process":    return "cc_Process"             // 内置，独立表
    case "plat":       return "cc_PlatBase"            // 内置，独立表
    default:
        // 通用模型：走分片表
        return "cc_ObjectBase_" + supplierAccount + "_pub_" + objID
    }
}
```

---

## 七、总结

1. **bk-cmdb 的 init_db 是一个版本化的增量迁移系统**，通过 `cc_System` 表记录当前版本，每次部署按版本号顺序执行所有未执行的升级器
2. **元数据层（6 张表）是模型驱动架构的根基**：分类 → 模型 → 属性分组 → 属性 → 关联 → 唯一约束，形成严格的依赖链
3. **交换机模型涉及 8 张表**：6 张元数据表 + 2 张分片实例表，11 个预置属性，1 条与主机的 connect 关联
4. **实例存储分两类**：内置模型（biz/set/module/host/process/plat）有独立表，通用模型（如 switch）走分片表 `cc_ObjectBase_{supplier}_pub_{objID}`
5. **Upsert 机制保证了数据初始化的幂等性**，重复执行不会产生重复数据
6. **通用数据迁移遵循：分类 → 模型 → 分组 → 属性 → 关联 → 建表 → 写数据的固定顺序**

> **源码文件索引**：本文所有引用均来自 `bk-cmdb release-v3.10.41` 源码，可通过文件路径直接定位。

---

## 八、Supplier Account（供应商账户）多租户机制

> **核心结论**：`bk_supplier_account` 是 bk-cmdb 的多租户隔离字段，也是通用模型实例表名分片的关键参数。同一 MongoDB 库中通过 `bk_supplier_account = "0"` 和 `"1"` 两套数据实现租户隔离。**init_db 只初始化 ownerID="0" 的数据**，第二套 ownerID="1" 需要手动创建。

### 8.1 核心常量定义

`src/common/definitions.go` 中定义了关键常量：

```go
BKDefaultOwnerID  = "0"           // 默认供应商 ID
BKSuperOwnerID    = "superadmin"  // 超级管理员 ID（跳过所有 owner 过滤）
BKOwnerIDField    = "bk_supplier_account"  // MongoDB 字段名
```

HTTP 头传递机制（`definitions.go` line 1072-1075）：

```go
BKHTTPOwner   = "HTTP_BK_SUPPLIER_ACCOUNT"      // 旧版供应商账户名（用于 SetOwnerIDAndAccount 兼容）
BKHTTPOwnerID = "HTTP_BLUEKING_SUPPLIER_ID"      // 新版供应商 ID
```

### 8.2 三层隔离机制

Supplier Account 通过**三层机制**实现同一 MongoDB 库内的数据隔离：

#### 第一层：静态表行级隔离 — `bk_supplier_account` 字段

所有"共享表"（内置模型表、元数据表）的每一行数据都带有 `bk_supplier_account` 字段。例如：

| 表 | 隔离方式 | ownerID="0" 示例 | ownerID="1" 示例 |
|----|---------|----------------|----------------|
| `cc_ApplicationBase` | 字段 | `{bk_biz_id:2, bk_supplier_account:"0"}` | `{bk_biz_id:3, bk_supplier_account:"1"}` |
| `cc_SetBase` | 字段 | `{bk_set_id:10, bk_supplier_account:"0"}` | `{bk_set_id:20, bk_supplier_account:"1"}` |
| `cc_HostBase` | 字段 | `{bk_host_id:1, bk_supplier_account:"0"}` | `{bk_host_id:100, bk_supplier_account:"1"}` |
| `cc_ObjDes` | 字段 | `{bk_obj_id:"bk_switch", bk_supplier_account:"0"}` | 同，ownerID="1"也需此条 |
| `cc_ObjAttDes` | 字段 | `{bk_property_id:"bk_asset_id", bk_supplier_account:"0"}` | 同 |

索引设计也考虑了 supplier account（如 `cc_SetBase`）：

```go
// src/common/index/collections/setbase.go:51
{Name: "bk_supplier_account_1", Keys: bson.D{{"bk_supplier_account", 1}}}
```

#### 第二层：通用模型表名分片 — `cc_ObjectBase_{ownerID}_pub_{objID}`

这是最关键的隔离设计。通用模型（交换机、路由器等）的实例表名**直接嵌入了 supplier account**：

```go
// src/common/tablenames.go:182
func GetObjectInstTableName(objID, supplierAccount string) string {
    return fmt.Sprintf("cc_ObjectBase_%s_pub_%s", supplierAccount, objID)
}
```

**实际效果**：

| 模型 | ownerID="0" 的表 | ownerID="1" 的表 |
|------|-----------------|-----------------|
| 交换机 (bk_switch) | `cc_ObjectBase_0_pub_bk_switch` | `cc_ObjectBase_1_pub_bk_switch` |
| 路由器 (bk_router) | `cc_ObjectBase_0_pub_bk_router` | `cc_ObjectBase_1_pub_bk_router` |
| 实例关联 | `cc_InstAsst_0_pub_bk_switch` | `cc_InstAsst_1_pub_bk_switch` |

`GetInstTableName()`（`tablenames.go:214`）的分发逻辑：

```
if 内置模型 (biz/set/module/host/process/plat/biz_set)
    → 返回固定表名（如 cc_SetBase）
else
    → 返回 cc_ObjectBase_{supplierAccount}_pub_{objID}
```

这意味着两个租户的交换机实例**物理上存在不同的 MongoDB 集合中**，天然隔离。

#### 第三层：查询过滤 — `SetQueryOwner()` 函数

`src/common/util/ownerutil.go` 中定义了查询时的 supplier account 过滤逻辑：

```go
func SetQueryOwner(condition map[string]interface{}, ownerID string) map[string]interface{} {
    if ownerID == common.BKSuperOwnerID {     // "superadmin"
        return condition                        // 无过滤，可看所有数据
    }
    if ownerID == common.BKDefaultOwnerID {     // "0"
        condition[common.BKOwnerIDField] = "0"  // 只看 "0" 的数据
        return condition
    }
    // ownerID = "1" 等非默认值
    condition[common.BKOwnerIDField] = map[string]interface{}{
        common.BKDBIN: []string{"0", ownerID},  // 同时看 "0" 和本租户的数据
    }
    return condition
}
```

**关键行为**：

| 请求方 ownerID | 可见数据 | 设计意图 |
|:---:|---|---|
| `"0"` | 仅 `bk_supplier_account = "0"` | 默认租户，只用自己的数据 |
| `"1"` | `"0"` + `"1"` 两者都可见 | 非默认租户可**继承**默认租户的公共数据 |
| `"superadmin"` | 所有数据，无过滤 | 跨租户管理，系统内部调用 |

> **设计意图**：ownerID="0" 是"公共数据"，所有租户可见。ownerID="1" 是"私有数据"，仅 ownerID="1" 可见。这实现了**数据继承**：租户 1 可以看到公共模型定义，但自己的实例数据对外隔离。

### 8.3 init_db 与 supplier account 的关系

**init_db 只初始化 ownerID="0"**。在 `admin_server/service/migrate.go` 中硬编码：

```go
// migrate.go:43
ownerID := common.BKDefaultOwnerID   // = "0"
updateCfg := &upgrader.Config{
    OwnerID: ownerID,
    User:    common.CCSystemOperatorUserName,
}
// migrate.go:58
preVersion, finishedVersions, err := upgrader.Upgrade(s.ctx, s.db, s.cache, s.iam, updateCfg)
```

然后 `conf.OwnerID` 被传入每一个 upgrader，所有 Upsert 操作的 `bk_supplier_account` 字段都填 `"0"`：

```go
// 以 v3.0.8/addDefauleApp.go:45 为例
defaultBiz[common.BKOwnerIDField] = conf.OwnerID  // = "0"
bizID, _, err := upgrader.Upsert(ctx, db, common.BKTableNameBaseApp, defaultBiz, ...)
```

**这意味着**：
- 默认蓝鲸业务（bizID=2）的 `bk_supplier_account="0"`
- 所有预置模型定义的 `bk_supplier_account="0"`
- 空闲机池、故障机模块的 `bk_supplier_account="0"`
- **不存在任何 ownerID="1" 的初始化数据**

### 8.4 HTTP 请求中 supplier account 的传递链

完整的端到端流程：

```
浏览器 Cookie
  │  Cookie: HTTP_BLUEKING_SUPPLIER_ID=0  (默认)
  │  或 Cookie: HTTP_BLUEKING_SUPPLIER_ID=1  (租户切换后)
  ▼
web_server 中间件 (login.go:64 / httpheader.go:33)
  │  session.Get(WEBSessionOwnerUinKey) → ownerID
  │  c.Request.Header.Add("HTTP_BLUEKING_SUPPLIER_ID", ownerID)
  ▼
web_server → API Server (HTTP 代理转发)
  │  CCHeader() 保留原 header (lib.go:281)
  ▼
API Server → 后端 Scene Server (topo/host/proc/etc.)
  │  go-restful 路由分发
  ▼
后端服务 Handler
  │  ownerID := util.GetOwnerID(header)     // → header.Get("HTTP_BLUEKING_SUPPLIER_ID")
  │  condition = util.SetQueryOwner(cond, ownerID)  // → 添加 bk_supplier_account 过滤
  ▼
MongoDB 查询
  │  db.Table(t).Find({..., bk_supplier_account: {$in: ["0", "1"]}})
```

Cookie 初始化在登录中间件（`userinfo.go:46-48`）：

```go
cookieOwnerID, err := c.Cookie(common.BKHTTPOwnerID)
if cookieOwnerID == "" || err != nil {
    c.SetCookie(common.BKHTTPOwnerID, common.BKDefaultOwnerID, 0, "/", "", false, false)
    // 默认设置为 "0"
}
```

### 8.5 如何实现"同一个库、id=0 和 id=1 两套数据"

完整操作流程：

#### 步骤一：创建 ownerID="1" 的元数据

由于 SetQueryOwner 中 ownerID="1" 可以看到 "0" 的数据（`$in: ["0", "1"]`），**模型定义表不需要为 "1" 再创建一份**。但如果要为 "1" 定制不同的属性/分类，就需要复制一份并修改 `bk_supplier_account="1"`。

#### 步骤二：为 ownerID="1" 创建默认业务

```bash
# 通过 API 创建（需要带上 supplier account header）
curl -X POST http://localhost:8080/api/v3/biz/default/2 \
  -H "HTTP_BLUEKING_SUPPLIER_ID: 1" \
  -H "BK_User: admin" \
  -d '{"bk_biz_name": "租户1业务", "bk_supplier_account": "1", ...}'
```

这会在 `cc_ApplicationBase` 中插入 `{bk_biz_id:3, bk_biz_name:"租户1业务", bk_supplier_account:"1"}`

#### 步骤三：为 ownerID="1" 创建拓扑（set/module/host）

同样通过 API 操作，所有写入请求都会把 header 中的 supplier account 写入数据字段。

#### 步骤四：通用模型实例自动建表

当第一次为 ownerID="1" 创建交换机实例时，系统会调用：

```go
// src/scene_server/admin_server/logics/index.go: syncModelShardingTable()
tableName := common.GetObjectInstTableName("bk_switch", "1")
// = "cc_ObjectBase_1_pub_bk_switch"
// MongoDB 自动创建这个集合
```

**不需要手动建表**，MongoDB 会在第一次 Insert 时自动创建。

#### 步骤五：运行时数据隔离效果

```
租户 0 的用户:
  Cookie: HTTP_BLUEKING_SUPPLIER_ID=0
  可见: cc_ApplicationBase 中 bk_supplier_account="0" 的业务
        cc_ObjectBase_0_pub_bk_switch 中的交换机实例

租户 1 的用户:
  Cookie: HTTP_BLUEKING_SUPPLIER_ID=1
  可见: cc_ApplicationBase 中 bk_supplier_account ∈ {"0","1"} 的业务
        cc_ObjectBase_0_pub_bk_switch + cc_ObjectBase_1_pub_bk_switch 中的交换机实例
```

### 8.6 v3.0.9-beta.1 的 supplier account 修复

历史版本中存在一个修复迁移（`fixes_supplier_account.go`），将早期没有 `bk_supplier_account` 字段的数据统一补填为 `"0"`：

```go
// fixes_supplier_account.go:25-33
condition := map[string]interface{}{
    common.BKOwnerIDField: map[string]interface{}{"$in": []interface{}{nil, ""}},
}
data := map[string]interface{}{common.BKOwnerIDField: common.BKDefaultOwnerID}
db.Table(tablename).Update(ctx, condition, data)
```

涉及 **21 张核心表**（包括 `cc_ApplicationBase`、`cc_HostBase`、`cc_ObjDes`、`cc_ObjAttDes` 等），确保所有遗留数据都有正确的 supplier account。

### 8.7 潜在问题与注意事项

| 问题 | 说明 |
|------|------|
| **init_db 只生成 ownerID="0"** | 如果要部署多租户，需要额外的初始化脚本或 API 调用为每个租户创建基础数据 |
| **默认租户数据可见性** | ownerID="1" 可以**看到和修改** ownerID="0" 的共享表数据（因为 `$in: ["0", "1"]`）。真正的隔离仅在通用模型的**分片实例表**层面 |
| **元数据表不隔离** | `cc_ObjDes`、`cc_ObjAttDes` 等元数据表是共享的，所有租户共用同一套模型定义。如果一个租户修改了模型属性，会影响所有租户 |
| **内置模型实例隔离不彻底** | 业务、集群、模块在同一张表里（如 `cc_ApplicationBase`），通过 `bk_supplier_account` 字段区分。ownerID="1" 仍能通过 API 查询到 ownerID="0" 的业务数据 |
| **superadmin 权限过大** | `BKSuperOwnerID = "superadmin"` 跳过所有 owner 过滤，系统内部服务（IAM 同步、云同步、操作服务）广泛使用此身份 |

---

## 九、CLI 与 HTTP API 数据导入接口

> **结论先行**：bk-cmdb 提供了一套完整的通用模型实例数据导入能力，覆盖 CLI 命令行工具和 HTTP API 两大入口。**通用模型（如交换机）的实例支持通过 Excel 批量导入和 REST API 批量创建两种方式**。

### 9.1 CLI 命令行工具

#### 9.1.1 cmdb_ctl — 运维管理 CLI

**入口文件**：`src/tools/cmdb_ctl/main.go`  
**框架**：`github.com/spf13/cobra`  
**全局参数**：所有子命令共用，通过 PersistentFlags 注册（`app/config/config.go`）：

| 参数 | 环境变量 | 默认值 | 说明 |
|------|---------|--------|------|
| `--mongo-uri` | `MONGO_URI` | — | MongoDB 连接 URI，例如 `mongodb://127.0.0.1:27017/cmdb` |
| `--mongo-rs-name` | — | `rs0` | MongoDB 副本集名称 |
| `--zk-addr` | `ZK_ADDR` | — | ZooKeeper 地址（仅 zk/auth 子命令需要） |
| `--redis-addr` | — | `127.0.0.1:6379` | Redis 地址（仅 snapshot/redis 子命令需要） |
| `--redis-mastername` | — | — | Redis Sentinel 主节点名 |
| `--redis-pwd` | — | — | Redis 密码 |
| `--redis-sentinelpwd` | — | — | Redis Sentinel 密码 |
| `--redis-database` | — | `0` | Redis 数据库编号 |

---

##### ① `cmdb_ctl db` — MongoDB 直接数据操作

源码：`src/tools/cmdb_ctl/cmd/dbOperation.go`，仅依赖 MongoDB，连接方式为 `local.NewMgo()`。

###### db show — 列出所有集合名称

```bash
cmdb_ctl db show --mongo-uri mongodb://127.0.0.1:27017/cmdb
```

**输出示例**：
```
cc_ApplicationBase
cc_HostBase
cc_ModuleBase
cc_SetBase
cc_ObjDes
cc_ObjAttDes
cc_ObjClassification
cc_PropertyGroup
cc_ObjAsst
cc_ObjectUnique
cc_ObjectBase_0_pub_bk_switch
cc_System
...
total collection num is 42
```

**源码逻辑**（`runShowDbDataCmd`，line 278-314）：
1. 通过 `connstring.Parse()` 从 MongoDB URI 中解析数据库名
2. 调用 `ListCollectionNames()` 列出所有集合
3. 逐行打印集合名和总数

---

###### db find — 查询集合数据

```bash
cmdb_ctl db find \
  --mongo-uri mongodb://127.0.0.1:27017/cmdb \
  --collection cc_ObjDes \
  --condition '{"bk_obj_id":"bk_switch"}' \
  --resfilter "bk_obj_id,bk_obj_name,bk_classification_id" \
  --num 10 \
  --pretty
```

**参数详解**：

| 参数 | 必填 | 默认值 | 说明 |
|------|:----:|--------|------|
| `--collection` | ✅ | — | 集合名称 |
| `--condition` | ❌ | `""` | 查询条件，**必须是 JSON 格式字符串** |
| `--resfilter` | ❌ | `""` | 返回字段过滤，多个字段用**英文逗号**分隔 |
| `--num` | ❌ | `5` | 返回记录数上限 |
| `--pretty` | ❌ | `false` | 是否使用 JSON Pretty 格式输出 |

**输出示例**（`--pretty`）：
```json
[
    {
        "bk_classification_id": "bk_network",
        "bk_obj_id": "bk_switch",
        "bk_obj_name": "交换机"
    }
]
total data num is 1
```

**源码逻辑**（`runFindDbDataCmd`，line 225-276）：
1. `mapstr.NewFromInterface(condition)` 将 JSON 字符串转为 MongoDB 查询条件
2. `resfilter` 按逗号 `strings.Split` 拆分为字段数组，传入 `Fields()` 做投影
3. `Find(cond).Fields(filter...).Limit(num).Sort("create_time")` 执行查询并按创建时间升序排列
4. `--pretty` 时使用 `json.Indent` 格式化输出；否则 `json.Marshal` 压缩输出
5. 额外执行一次 `.Count()` 输出匹配总数

**更多查询示例**：

```bash
# 查看所有模型分类
cmdb_ctl db find \
  --mongo-uri mongodb://127.0.0.1:27017/cmdb \
  --collection cc_ObjClassification \
  --pretty

# 查看交换机所有属性
cmdb_ctl db find \
  --mongo-uri mongodb://127.0.0.1:27017/cmdb \
  --collection cc_ObjAttDes \
  --condition '{"bk_obj_id":"bk_switch"}' \
  --resfilter "bk_property_id,bk_property_name,bk_property_type,isrequired,isonly" \
  --num 20 \
  --pretty

# 查看交换机实例数据（分片表）
cmdb_ctl db find \
  --mongo-uri mongodb://127.0.0.1:27017/cmdb \
  --collection cc_ObjectBase_0_pub_bk_switch \
  --pretty

# 查看 cc_System 表确认当前版本
cmdb_ctl db find \
  --mongo-uri mongodb://127.0.0.1:27017/cmdb \
  --collection cc_System \
  --condition '{"type":"version"}' \
  --pretty

# 查看指定业务下的所有集群
cmdb_ctl db find \
  --mongo-uri mongodb://127.0.0.1:27017/cmdb \
  --collection cc_SetBase \
  --condition '{"bk_biz_id":2}' \
  --num 50 \
  --pretty
```

---

###### db delete — 删除集合数据

```bash
cmdb_ctl db delete \
  --mongo-uri mongodb://127.0.0.1:27017/cmdb \
  --collection cc_ObjectBase_0_pub_bk_switch \
  --condition '{"bk_inst_name":"test-switch-01"}'
```

**参数详解**：

| 参数 | 必填 | 说明 |
|------|:----:|------|
| `--collection` | ✅ | 集合名称 |
| `--condition` | ✅ | 删除条件，**必须是 JSON 格式字符串** |

**安全限制**（源码 line 36-38）：
- **最大删除数量**：1000 条（`maxDeleteNum = 1000`）
- 若匹配数据 > 1000 条：**直接报错拒绝**，不会执行删除
- 若匹配数据 < 300 条：一次性 `Delete(ctx, cond)` 执行
- 若匹配数据 300~1000 条：**分批次删除**：
  1. 先 `Find(cond).Sort("_id").Fields("_id").Limit(BKMaxPageSize)` 查出所有待删 `_id`
  2. 每批 300 条（`maxDeleteBatchNum = 300`），使用 `$in` 按 `_id` 精确删除
  3. 批次间 `sleep 50ms` 避免对 MongoDB 造成过大压力

**输出示例**：
```
 delete total data num is 3
```

**源码逻辑**（`runDelDbDataCmd`，line 142-223）：
1. `mapstr.NewFromInterface(condition)` 解析 JSON 条件
2. `Find(cond).Count(ctx)` 先统计匹配数 — **这一步决定了是否触发上限拒绝**
3. 根据匹配数选择一次性删除或分批删除
4. 打印删除总数

---

##### ② `cmdb_ctl migrate-check` — 迁移前数据一致性校验

源码：`src/tools/cmdb_ctl/cmd/migrate_check.go`，仅依赖 MongoDB，连接方式为 `config.NewMongoService()`。

###### migrate-check --check-all — 一键全量检查

```bash
cmdb_ctl migrate-check \
  --mongo-uri mongodb://127.0.0.1:27017/cmdb \
  --check-all
```

**执行内容**：依次运行 `runUniqueCheck()` + `runProcCheck(false)`，即唯一约束检查 + 孤立进程检查。

**输出示例**：
```
=================================
INFO: start checking unique constraints

INFO: start searching for all object ids
INFO: start searching unique constraints for object bk_switch
INFO: start searching object attributes for object bk_switch
=================================
INFO: start searching unique constraints for object bk_set
INFO: start searching object attributes for object bk_set
...
INFO: checking unique constraints done

=================================
INFO: start checking process with no relation
INFO: checking process with no relation done
```

---

###### migrate-check unique — 检查唯一约束

```bash
cmdb_ctl migrate-check unique \
  --mongo-uri mongodb://127.0.0.1:27017/cmdb
```

**执行流程**（`checkUnique()`，line 114-176）：

```
1. getAllObjectIDs()
   └─ cc_ObjDes.Distinct("bk_obj_id") 获取所有模型 ID

2. 遍历每个模型：
   ├─ SatisfyMongoCollLimit(objID)   → 检查模型 ID 是否合法
   ├─ getObjAttrMap(objID)            → cc_ObjAttDes 读取该模型所有属性
   │   ├─ SatisfyMongoFieldLimit()    → 检查属性 ID 是否合法
   │   └─ 特殊处理：host 的 bk_cloud_id → FieldTypeInt
   │                 host 的 IP 字段 → FieldTypeList
   ├─ getObjectUniques(objID)         → cc_ObjectUnique 读取该模型唯一约束
   └─ checkObjectUnique(objID, ...)   → 核心检查逻辑:
       ├─ 验证每个 unique key 的属性存在且类型有效
       ├─ 使用 MongoDB Aggregation Pipeline:
       │   {$match: {<各字段>: {$type: <dbType>}}}
       │   {$group: {_id: {<字段组合>}, total: {$sum: 1}}}
       │   {$match: {total: {$gt: 1}}}
       └─ 若存在重复数据 → 打印 ERROR + 重复项 JSON

3. 输出检查结果
```

**检查范围**：
- 内置模型（biz/set/module/host/process/plat）：查各自的独立表（`cc_SetBase` 等）
- 通用模型（switch/router 等）：查 `cc_ObjectBase` 通用实例表

**典型输出（发现问题时）**：
```
ERROR: object(bk_switch) unique(1) has duplicate items([{"attributes":{"bk_asset_id":"ASSET001"},"total":2}])
```

---

###### migrate-check process — 检查孤立进程

```bash
# 仅检查，不清理
cmdb_ctl migrate-check process \
  --mongo-uri mongodb://127.0.0.1:27017/cmdb
```

**执行流程**（`checkProc()`，line 365-407）：
```
1. getProcWithNoRelation(ctx)
   └─ 分页遍历 cc_ProcessTemplate 中所有进程
   └─ 对每批进程 ID，查 cc_ProcessInstanceRelation 是否有对应记录
   └─ 收集所有无关联关系的进程 ID

2. 若存在无关联进程 → 分页查询 cc_ProcessTemplate 获取完整信息
   └─ 以 JSON 格式打印所有孤立进程数据（含 ERROR 前缀）
```

**输出示例（发现问题时）**：
```
=================================
INFO: start checking process with no relation
ERROR: processes has no relations, need to delete, data: [{"bk_process_id":123,"bk_process_name":"orphan_proc",...}]
INFO: checking process with no relation done
```

**典型使用场景**：
- 数据迁移前确认没有"悬挂"进程数据
- 业务拓扑清理后验证进程关联完整性

---

###### migrate-check process --clear-proc — 清理孤立进程

```bash
# 检查并清理无关联关系的进程
cmdb_ctl migrate-check process \
  --mongo-uri mongodb://127.0.0.1:27017/cmdb \
  --clear-proc
```

**执行流程**（`clearProc()`，line 409-442）：
```
1. 同 checkProc，先查出所有孤立进程 ID
2. 分批执行 Delete（每批 BKMaxPageSize 条）：
   cc_ProcessTemplate.Delete({bk_process_id: {$in: [孤立ID列表]}})
3. 打印已清理的进程 ID 列表
```

**输出示例**：
```
=================================
INFO: start clearing processes with no instances
INFO: clear processes successful, ids: [123, 456, 789]
INFO: clearing process with no relation done
```

> ⚠️ **注意**：`--clear-proc` 是**不可逆**操作，执行前建议先用不带 `--clear-proc` 的 `process` 子命令确认待清理数据。

---

##### ③ `cmdb_ctl topo` — 业务拓扑完整性检查

源码：`src/tools/cmdb_ctl/cmd/topo.go`，仅依赖 MongoDB，连接方式为 `config.NewMongoService()`。

```bash
cmdb_ctl topo \
  --mongo-uri mongodb://127.0.0.1:27017/cmdb \
  --bizId 2
```

**参数**：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--bizId` | `2` | 蓝鲸业务 ID（默认值 2 对应"蓝鲸"默认业务） |

**执行流程**（`checkTopo()`，line 97-108）：

```
1. searchMainlineModel() — 构建主线模型层级关系
   └─ cc_ObjAsst.Find({bk_asst_id: "bk_mainline"})
      → 找到所有主线关联（如 biz→set→module 及自定义层级）
      → 构建 objectParentMap: {子模型ID → 父模型ID}
      → 收集所有参与主线的 general 模型 ID 列表

2. searchMainlineInstance() — 收集所有主线实例
   ├─ cc_ApplicationBase.Find({bk_biz_id: bizID})
   │   → 获取业务实例，提取 supplierAccount（租户）
   │   → 存入 instanceMap["biz:{bizID}"]
   ├─ cc_SetBase.Find({bk_biz_id: bizID})
   │   → 提取 setID、parentInstanceID、default 字段
   │   → 存入 instanceMap["set:{setID}"]
   ├─ cc_ModuleBase.Find({bk_biz_id: bizID})
   │   → 提取 moduleID、parentInstanceID、default 字段
   │   → 存入 instanceMap["module:{moduleID}"]
   └─ 对每个主线 general 模型：
       cc_ObjectBase_{supplier}_{objID}.Find({bk_obj_id, bk_biz_id})
       → 提取 instID、parentInstID、default
       → 存入 instanceMap["{objID}:{instID}"]

3. checkMainlineInstanceTopo() — 逐实例校验父子关系
   遍历 instanceMap 中每个实例：
   ├─ parentInstanceID == 0 → 跳过（顶层节点）
   ├─ 空闲机池（default=1 的 set）→ 父节点检查 biz
   ├─ 普通节点 → 通过 objectParentMap 查找应有的父模型 ID
   │   → 拼父 key = "{父模型ID}:{parentInstanceID}"
   │   → 在 instanceMap 中查找父实例是否存在
   └─ 若父实例缺失：
       ├─ 从对应表中再次查询确认
       ├─ 找不到 → stderr: "found no parent instance"
       ├─ 找到多个 → stderr: "found too many parent instances"
       └─ 找到唯一一个 → 补入 instanceMap
```

**输出示例**：
```
=====================
start check
start searching mainline model
start searching mainline instance
start checking mainline instance topo
end check
```

**发现拓扑断裂时的错误输出**：
```
instance: 100 of model: bk_set found no parent instance by parentObjectID bk_switch and parentInstanceID: 50
```

**典型使用场景**：
- 数据迁移后验证业务拓扑结构是否完整
- 排查模型实例层级关系断裂问题
- 在版本升级前确认主线拓扑无异常

> **注意**：`topo` 子命令是**只读检查**，不会修改任何数据。遇到父实例缺失时仅输出 stderr 警告，不会自动修复。

---

##### 全部子命令一览

| 子命令 | 文件位置 | 仅需 MongoDB | 功能说明 |
|--------|---------|:-----------:|---------|
| `db find` | `cmd/dbOperation.go` | ✅ | 查询 MongoDB 集合数据 |
| `db delete` | `cmd/dbOperation.go` | ✅ | 删除 MongoDB 集合数据 |
| `db show` | `cmd/dbOperation.go` | ✅ | 显示所有集合列表 |
| `migrate-check` | `cmd/migrate_check.go` | ✅ | 迁移前数据一致性检查（唯一约束、孤立进程等） |
| `topo` | `cmd/topo.go` | ✅ | 检查业务拓扑完整性 |
| `snapshot` | `cmd/snapshot.go` | ❌ | 检查主机快照状态（需 Redis） |
| `auth check` | `cmd/auth.go` | ❌ | 权限校验（需 ZK） |
| `redis` | `cmd/redis.go` | ❌ | Redis 数据操作（需 Redis） |
| `watch` | `cmd/watch.go` | ❌ | 监听 CMDB 事件流（HTTP 客户端） |
| `checkconf` | `cmd/conf.go` | ❌ | 校验 YAML 配置文件格式 |
| `echo` | `cmd/echo.go` | ❌ | HTTP 请求测试 |
| `limiter` | `cmd/limiter.go` | ❌ | API 限流规则管理（HTTP） |
| `shutdown` | `cmd/shutdown.go` | ❌ | 操作系统进程信号 |
| `log` | `cmd/log.go` | ❌ | 日志文件读取 |

> **注意**：`cmdb_ctl` 侧重于运维管理和诊断，**不包含通用模型实例的数据导入功能**。`db find/delete` 提供 MongoDB 直接读写能力，可用于手动数据修复。

#### 9.1.2 admin_server bkbiz — 蓝鲸业务拓扑导入导出

**入口文件**：`src/scene_server/admin_server/command/command.go`  
**框架**：`github.com/spf13/pflag`

##### 命令行语法

```bash
# 导入模式
admin_server bkbiz --import --file <json_path> --config <cfg_path> [--dryrun] [--biz_name <name>]

# 导出模式（当前未实现）
admin_server bkbiz --export --file <json_path> --config <cfg_path> [--mini] [--scope <scope>]
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--import` | bool | — | 导入模式 |
| `--export` | bool | — | 导出模式（当前**未实现**，`export.go` 返回 `unrealized` 错误） |
| `--file` | string | — | **必填**，JSON 文件路径 |
| `--config` | string | `conf/api.conf` | 配置文件路径，读取 MongoDB 连接信息 |
| `--dryrun` | bool | false | 干运行模式，仅打印将要执行的操作，不实际写入 |
| `--mini` | bool | false | 精简模式（导出时仅导出必要字段） |
| `--scope` | string | `all` | 导出范围：`biz` / `process` / `all` |
| `--biz_name` | string | `蓝鲸` | 目标业务名称（默认`蓝鲸`业务） |

##### 配置文件格式

`--config` 参数指向的配置文件（默认 `conf/api.conf`）中需包含 MongoDB 连接信息：

```yaml
mongodb:
  host: 127.0.0.1:27017
  usr: ""
  pwd: ""
  database: cmdb
  maxOpenConns: 3000
  maxIdleConns: 1000
  mechanism: ""
  rsName: rs0
  socketTimeoutSeconds: 30
```

> **只需要 MongoDB 配置**，无需 Redis 或 ZooKeeper 配置。

##### 导入执行流程（源码级）

`importBKBiz()` 函数 (`import.go` line 51-94) 的完整执行链路：

```
1. 读取 JSON 文件 → json.Decode → BKTopo 结构体
2. getBKBizID()      → 从 cc_ApplicationBase 查询业务ID (bk_biz_name = "蓝鲸")
3. getSetParentID()  → 从 cc_SetBase 查询 set 的父节点 ID
4. allowInit()       → 安全检查:
   ├─ cc_System 是否存在 "cc_init_bk_biz_init" 标记 → 已初始化则禁止重复导入
   └─ cc_ModuleHostConfig 中该业务是否有主机 → 有主机则禁止导入
5. FilterBKTopo()    → 数据校验 & 缓存:
   ├─ cacheServiceCategory()     → 缓存内置+业务服务分类 (cc_ServiceCategory)
   ├─ filterBKTopoProc()        → 校验进程属性并转为 ProcessTemplate
   ├─ filterBKTopoServiceTemplate() → 校验服务模板绑定的进程是否存在
   ├─ filterBKTopoSet()         → 校验 set 数据
   └─ filterBKTopoModule()      → 校验 module 引用的 set 和 service_template
6. ClearBKTopo()     → 清理旧数据:
   ├─ cc_ProcessTemplate  → 删除该业务所有进程模板
   ├─ cc_SetBase          → 删除该业务非默认 set
   ├─ cc_ServiceTemplate  → 删除该业务所有服务模板
   └─ cc_ModuleBase       → 删除该业务非默认 module
7. InitBKTopo()      → 写入新数据:
   ├─ initBKServiceCategory() → 写入 cc_ServiceTemplate + cc_ProcessTemplate
   ├─ initBKTopoSet()         → 写入 cc_SetBase
   └─ initBKTopoModule()      → 写入 cc_ModuleBase
8. recordInitLog()   → cc_System 写入 "cc_init_bk_biz_init" 标记
```

##### JSON 数据结构定义（types.go）

```go
// 顶层结构
type BKTopo struct {
    Proc               []map[string]interface{}  // 进程定义列表
    ServiceTemplateArr []BKServiceTemplate       // 服务模板列表
    Topo               BKBizTopo                 // 集群和模块拓扑
}

// 服务模板
type BKServiceTemplate struct {
    Name                string    // 服务模板名称
    ServiceCategoryName []string  // 服务分类 [一级名称, 二级名称]
    BindProcess         []string  // 绑定的进程名称列表
    BindProcessUUID     []string  // 绑定的进程UUID列表
}

// 业务拓扑
type BKBizTopo struct {
    SetArr    []map[string]interface{}  // 集群列表
    ModuleArr []BKBizModule             // 模块列表
}

// 业务模块
type BKBizModule struct {
    SetName         string                  // 所属集群名称
    ServiceTemplate string                  // 绑定的服务模板名称
    Info            map[string]interface{}  // 额外信息(如模块类型等)
}
```

##### 完整 JSON 数据示例

以下是一个标准的蓝鲸业务拓扑 JSON 文件示例：

```json
{
  "proc": [
    {
      "bk_func_name": "mysql",
      "bk_process_name": "mysqld",
      "user": "mysql",
      "work_path": "/usr/local/mysql/bin",
      "start_cmd": "./mysqld_safe --defaults-file=/etc/my.cnf &",
      "stop_cmd": "mysqladmin -uroot shutdown",
      "restart_cmd": "",
      "face_stop_cmd": "kill -9 $(cat /var/run/mysqld/mysqld.pid)",
      "reload_cmd": "",
      "pid_file": "/var/run/mysqld/mysqld.pid",
      "auto_start": false,
      "proc_num": 1,
      "priority": 1,
      "timeout": 30,
      "bk_start_check_secs": 5,
      "bk_start_param_regex": "",
      "description": "MySQL 数据库服务"
    },
    {
      "bk_func_name": "bk-cmdb",
      "bk_process_name": "cmdb_webserver",
      "user": "root",
      "work_path": "/data/bkee/cmdb/server/bin",
      "start_cmd": "./cmdb_webserver &",
      "stop_cmd": "pkill cmdb_webserver",
      "restart_cmd": "",
      "face_stop_cmd": "kill -9 $(pgrep cmdb_webserver)",
      "reload_cmd": "",
      "pid_file": "",
      "auto_start": true,
      "proc_num": 1,
      "priority": 2,
      "timeout": 60,
      "bk_start_check_secs": 3,
      "bk_start_param_regex": "",
      "description": "CMDB Web 服务"
    },
    {
      "bk_func_name": "nginx",
      "bk_process_name": "nginx",
      "user": "root",
      "work_path": "/usr/local/nginx/sbin",
      "start_cmd": "./nginx",
      "stop_cmd": "./nginx -s quit",
      "restart_cmd": "./nginx -s reload",
      "face_stop_cmd": "kill -9 $(cat /var/run/nginx.pid)",
      "reload_cmd": "./nginx -s reload",
      "pid_file": "/var/run/nginx.pid",
      "auto_start": true,
      "proc_num": 1,
      "priority": 1,
      "timeout": 30,
      "bk_start_check_secs": 2,
      "bk_start_param_regex": "",
      "description": "Nginx 反向代理"
    }
  ],
  "service_template": [
    {
      "name": "mysql_service",
      "service_category_name": ["数据库", "MySQL"],
      "bind_proc": ["mysqld"],
      "bind_proc_uuid": []
    },
    {
      "name": "cmdb_service",
      "service_category_name": ["默认分类", "默认分类"],
      "bind_proc": ["cmdb_webserver"],
      "bind_proc_uuid": []
    },
    {
      "name": "nginx_service",
      "service_category_name": ["Web服务", "Nginx"],
      "bind_proc": ["nginx"],
      "bind_proc_uuid": []
    }
  ],
  "topo": {
    "set": [
      {
        "bk_set_name": "cmdb_set",
        "bk_set_desc": "CMDB 核心集群",
        "bk_set_env": "3"
      },
      {
        "bk_set_name": "db_set",
        "bk_set_desc": "数据库集群",
        "bk_set_env": "3"
      }
    ],
    "module": [
      {
        "bk_set_name": "cmdb_set",
        "service_template": "cmdb_service",
        "info": {}
      },
      {
        "bk_set_name": "cmdb_set",
        "service_template": "nginx_service",
        "info": {
          "bk_module_type": "1"
        }
      },
      {
        "bk_set_name": "db_set",
        "service_template": "mysql_service",
        "info": {
          "bk_module_type": "2"
        }
      }
    ]
  }
}
```

##### 进程模板支持的字段

从 `convProcTemplateProperty()` 函数 (`import.go` line 558) 提取，JSON 中 `proc` 数组的每个元素支持以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `bk_func_name` | string | 功能名称 |
| `bk_process_name` | string | 进程名称 |
| `user` | string | 启动用户 |
| `work_path` | string | 工作路径 |
| `start_cmd` | string | 启动命令 |
| `stop_cmd` | string | 停止命令 |
| `restart_cmd` | string | 重启命令 |
| `face_stop_cmd` | string | 强制停止命令 |
| `reload_cmd` | string | 进程重载命令 |
| `pid_file` | string | PID 文件路径 |
| `auto_start` | bool | 是否自动拉起 |
| `proc_num` | int | 启动数量 |
| `priority` | int | 启动优先级 |
| `timeout` | int | 操作超时时长（秒） |
| `bk_start_check_secs` | int | 启动检查等待秒数 |
| `bk_start_param_regex` | string | 启动参数正则 |
| `description` | string | 描述 |

> 注意：`bind_ip`、`port`、`protocol` 三个字段在代码中已被注释禁用 (`import.go` line 623-633, 665-673, 735-744)。

##### 实际使用示例

```bash
# 1. 准备配置文件 conf/api.conf（包含 MongoDB 连接信息）

# 2. 准备 JSON 数据文件 bk_biz_topo.json

# 3. 干运行模式：预览将要执行的操作
./cmdb_adminserver bkbiz --import --file ./bk_biz_topo.json --config ./conf/api.conf --dryrun

# 4. 正式执行导入
./cmdb_adminserver bkbiz --import --file ./bk_biz_topo.json --config ./conf/api.conf

# 预期输出:
#   importing 蓝鲸 business from ./bk_biz_topo.json
#   %s business has been backup to ./backup_bk_biz_2024_01_15_10_30_00.json
#   蓝鲸 business has been import from ./bk_biz_topo.json
```

##### 安全机制

| 检查项 | 源码位置 | 说明 |
|--------|---------|------|
| **禁止重复导入** | `allowInit()` line 100-107 | `cc_System` 中存在 `cc_init_bk_biz_init` 标记则拒绝 |
| **禁止业务有主机时导入** | `allowInit()` line 110-117 | `cc_ModuleHostConfig` 中该业务已有主机则拒绝 |
| **自动备份** | `backup()` line 35-48 | 导入前自动将现有拓扑导出为 JSON 备份文件 |
| **先清再建** | `ClearBKTopo()` line 316-351 | 导入前删除旧的进程模板、服务模板、集群、模块 |
| **进程与服务模板绑定校验** | `filterBKTopoProc()` / `filterBKTopoServiceTemplate()` | 服务模板声明绑定的进程名必须在 proc 数组中存在 |
| **模块的 set 和 template 引用校验** | `filterBKTopoModule()` | module 的 `bk_set_name` 和 `service_template` 必须引用已存在的名称 |

##### 涉及的数据表

在导入过程中，`admin_server bkbiz` 直接读写的 MongoDB 表：

| 操作 | 表名 | 说明 |
|------|------|------|
| 读 | `cc_ApplicationBase` | 查找"蓝鲸"业务的 ID |
| 读 | `cc_SetBase` | 查找 set 的父节点 ID |
| 读 | `cc_System` | 检查是否已初始化 |
| 读 | `cc_ModuleHostConfig` | 检查业务下是否有主机 |
| 读 | `cc_ServiceCategory` | 缓存服务分类数据 |
| **删** | `cc_ProcessTemplate` | 清除旧进程模板 |
| **删** | `cc_SetBase` | 清除旧非默认 set |
| **删** | `cc_ServiceTemplate` | 清除旧服务模板 |
| **删** | `cc_ModuleBase` | 清除旧非默认 module |
| **写** | `cc_ServiceTemplate` | 写入服务模板 |
| **写** | `cc_ProcessTemplate` | 写入进程模板 |
| **写** | `cc_SetBase` | 写入集群 |
| **写** | `cc_ModuleBase` | 写入模块 |
| **写** | `cc_System` | 写入初始化标记 |

##### 限制

- 仅用于**蓝鲸业务拓扑初始化**，不支持通用模型实例导入
- 有 `allowInit` 检查，要求目标业务下无主机且未初始化过
- 不允许重复导入（需手动清除 `cc_System` 中的 `cc_init_bk_biz_init` 标记才可重入）
- 导出功能未实现（`export.go` 直接返回 `unrealized`）
- 仅依赖 MongoDB，无需 Redis/ZK

#### 9.1.3 mongo_script — MongoDB 数据修复脚本

**目录**：`src/tools/mongo_script/`，包含 JavaScript 编写的 MongoDB 直接操作脚本：

| 脚本 | 功能 |
|------|------|
| `fix_inner_model.js` | 修复内置模型数据 |
| `fix_duplicated_service_instance_id.js` | 修复重复的服务实例 ID |
| `fix_max_primary_id.js` | 修复最大主键 ID |
| `fix_module_missed_fields.js` | 修复模块缺失字段 |
| `fix_service_category_field.js` | 修复服务分类字段 |
| `migrate_time_field.js` | 迁移时间字段格式 |
| `clear_redundancy_servicetemplate.js` | 清理冗余服务模板 |

#### 9.1.4 CLI 工具依赖分析：是否仅需 MongoDB？

> **核心结论**：两个 CLI 工具的**核心数据操作子命令均只依赖 MongoDB**，但 cmdb_ctl 的其余运维子命令有额外依赖。

##### cmdb_ctl 各子命令依赖一览

经过对 `src/tools/cmdb_ctl/cmd/` 下 14 个子命令的逐一源码分析：

| 子命令 | 依赖 MongoDB | 依赖 Redis | 依赖 ZooKeeper | 说明 |
|--------|:-----------:|:----------:|:-------------:|------|
| **`db find`** | ✅ | ❌ | ❌ | 直接连接 MongoDB 执行查询 |
| **`db delete`** | ✅ | ❌ | ❌ | 直接连接 MongoDB 执行删除 |
| **`db show`** | ✅ | ❌ | ❌ | 直接连接 MongoDB 列出集合 |
| **`migrate-check`** | ✅ | ❌ | ❌ | 迁移前校验唯一约束、孤立进程等 |
| **`topo`** | ✅ | ❌ | ❌ | 检查业务拓扑完整性 |
| `snapshot` | ❌ | ✅ | ❌ | 检查 Redis 中的主机快照 |
| `redis` | ❌ | ✅ | ❌ | Redis 数据扫描、删除操作 |
| `zk` | ❌ | ❌ | ✅ | ZooKeeper 节点查询 |
| `auth` | ❌ | ❌ | ✅ | 通过 ZK 服务发现调用 IAM 权限 API |
| `watch` | ❌ | ❌ | ❌ | HTTP 客户端，连接 CMDB watch 事件流 |
| `echo` | ❌ | ❌ | ❌ | HTTP 客户端，向指定 URL 发送请求 |
| `conf` | ❌ | ❌ | ❌ | 纯文件读取，解析 YAML 配置 |
| `limiter` | ❌ | ❌ | ❌ | HTTP 客户端，管理 API 限流规则 |
| `shutdown` | ❌ | ❌ | ❌ | 操作系统进程信号操作 |
| `log` | ❌ | ❌ | ❌ | 读取日志文件 |

**源码证据**：

- `db` 子命令 (`dbOperation.go` line 227)：只调用 `newMongo()` → `local.NewMgo()`，无任何 Redis/ZK 引用
- `migrate-check` 子命令 (`migrate_check.go`)：只调用 `config.NewMongoService()`，无 Redis/ZK 引用
- `topo` 子命令 (`topo.go`)：只调用 `config.NewMongoService()`，无 Redis/ZK 引用
- `snapshot` 子命令 (`snapshot.go` line 24)：`import ccRedis "configcenter/src/storage/dal/redis"` — **需要 Redis**
- `zk` 子命令 (`zk.go`)：`import config` → `config.NewZkService()` — **需要 ZooKeeper**
- `auth` 子命令 (`auth.go` line 33)：`import "configcenter/src/common/backbone/service_mange/zk"` — **需要 ZooKeeper**

`cmdb_ctl` 的 `--mongo-uri` 参数是全局 `PersistentFlags`，**所有子命令都能看到该参数**，但非数据子命令不使用它。不传 `--zk-addr` 对于 `db/migrate-check/topo` 等子命令**不会造成任何影响**。

##### admin_server bkbiz 依赖分析

```go
// command.go line 72-78 — 唯一的服务依赖
mongoConfig, err := cc.Mongo("mongodb")  // 从配置文件读取 MongoDB 连接串
db, err := local.NewMgo(mongoConfig.GetMongoConf(), 0)  // 连接 MongoDB
```

从 `command.go` 和 `import.go` 的源码可以确认：

- ✅ **仅依赖 MongoDB**：代码中只通过 `local.NewMgo()` 连接 MongoDB
- ✅ **不依赖 Redis**：无任何 Redis 相关 import
- ✅ **不依赖 ZooKeeper**：无任何 ZK 相关 import
- 需读取一个本地配置文件（`--config` 参数，默认 `conf/api.conf`），从中获取 MongoDB 连接信息

##### 数据操作依赖总结

```
                    核心数据操作场景（仅需 MongoDB）
                    ┌─────────────────────────────┐
                    │                             │
              ┌─────┴──────┐          ┌───────────┴──────────┐
              │  cmdb_ctl   │          │  admin_server bkbiz  │
              │  db find     │          │  --import            │
              │  db delete   │          │  --export (未实现)    │
              │  db show     │          │                      │
              │  migrate-    │          └──────────┬───────────┘
              │  check       │                     │
              │  topo        │              ┌──────┴──────┐
              └──────┬───────┘              │   MongoDB   │
                     │                      │   Service   │
                     └──────────────────────┤             │
                                            └─────────────┘

                    完整运维场景（需全栈依赖）
                    ┌──────────────────────────────────────┐
                    │  cmdb_ctl full                       │
                    │  ├── db/migrate-check/topo  → MongoDB│
                    │  ├── snapshot/redis         → Redis  │
                    │  └── zk/auth                → ZK     │
                    └──────────────────────────────────────┘
```

**结论**：如果仅需数据导入/查询/校验操作，`cmdb_ctl` 的 `db`、`migrate-check`、`topo` 子命令以及 `admin_server bkbiz` **都只需要 MongoDB 服务即可运行**，无需 Redis 和 ZooKeeper。

### 9.2 HTTP API 接口

#### 9.2.1 接口全景图

bk-cmdb 的数据导入相关 API 分布在三个服务中：

```
用户/外部系统
    │
    ├──▶ web_server (Gin框架)     ← Excel 文件上传/下载，面向用户
    │     ├── POST /importtemplate/:bk_obj_id           下载 Excel 导入模板
    │     ├── POST /insts/object/:bk_obj_id/import      通用实例 Excel 导入
    │     ├── POST /insts/object/:bk_obj_id/export      通用实例 Excel 导出
    │     ├── POST /hosts/import                        主机 Excel 导入
    │     ├── POST /hosts/export                        主机 Excel 导出
    │     ├── POST /hosts/update                        主机 Excel 批量更新
    │     ├── POST /netdevice/import                    网络设备 Excel 导入
    │     ├── POST /netdevice/export                    网络设备 Excel 导出
    │     ├── POST /object/object/:bk_obj_id/import     模型属性 Excel 导入
    │     ├── POST /object/object/:bk_obj_id/export     模型属性 Excel 导出
    │     ├── POST /object/importmany                   批量导入模型（ZIP/YAML）
    │     └── POST /object/importmany/analysis          批量导入前分析
    │
    ├──▶ apiserver (go-restful)    ← API 网关，统一路由分发（/api/v3）
    │     └── 根据 URL 前缀分发到后端服务
    │
    └──▶ topo_server (go-restful)  ← 实例/模型/关联的 CRUD API
          ├── POST /createmany/instance/object/{bk_obj_id}   批量创建实例（JSON）
          ├── POST /create/instance/object/{bk_obj_id}/by_import  Excel 导入实例（内部）
          ├── POST /import/instassociation/{bk_obj_id}       导入实例关联
          ├── POST /createmany/instassociation               批量创建实例关联
          ├── POST /createmany/object                        批量创建模型（含属性）
          └── POST /createmany/object/by_import              通过 YAML 导入批量创建模型
```

#### 9.2.2 通用实例 Excel 导入完整流程

这是对通用模型实例迁移**最为关键**的接口链：

```
┌──────────────────────────────────────────────────────────────────┐
│                    通用实例 Excel 导入全链路                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  [1] 下载模板                                                      │
│   POST /importtemplate/{bk_obj_id}                                 │
│   参数: POST form { bk_biz_id }                                    │
│   响应: .xlsx 文件流                                                │
│   实现: web_server/service/host.go:BuildDownLoadExcelTemplate()    │
│         ├── 根据 objID 获取模型属性列表                              │
│         ├── 生成含字段名表头的 Excel 文件                             │
│         └── 生成注释 Sheet 页（字段说明）                             │
│                                                                    │
│  [2] 上传 Excel                                                    │
│   POST /insts/object/{bk_obj_id}/import                            │
│   参数: multipart/form-data                                         │
│         file:  Excel 文件                                           │
│         params: JSON { bk_biz_id, op, association_cond,           │
│                        object_unique_id }                          │
│   实现: web_server/service/inst.go:ImportInst()                    │
│         ├── 保存上传文件到临时目录                                   │
│         ├── 用 xlsx 库打开并解析                                     │
│         └── 调用 s.Logics.ImportInsts()                            │
│                                                                    │
│  [3] 解析 Excel 数据                                                │
│   web_server/logics/inst.go:ImportInsts()                          │
│         ├── GetImportInsts() → GetExcelData() 逐行解析字段值         │
│         │   └── 将 Excel 行映射为 map[int]map[string]interface{}   │
│         ├── 构造请求参数:                                            │
│         │   { "input_type": "excel",                               │
│         │     "BatchInfo": { 行号: {字段:值} },                     │
│         │     "bk_biz_id": <bizID> }                               │
│         └── CoreAPI.ApiServer().AddInstByImport() → API 调用        │
│                                                                    │
│  [4] API 路由转发                                                   │
│   apiserver/service/url.go: 根据路径分发给 topo_server               │
│                                                                    │
│  [5] 批量写入数据库                                                  │
│   topo_server/service/inst.go:CreateInstsByImport()                │
│         ├── 校验: 禁止对内置模型(biz/set/module/host等)使用通用API    │
│         ├── 校验: 禁止对主线模型(biz/set/module)使用通用API           │
│         ├── 校验: 模型是否存在                                       │
│         ├── 反序列化为 metadata.InstBatchInfo                       │
│         └── s.Logics.InstOperation().CreateInstBatch()             │
│              └── 写入 cc_ObjectBase_{supplier}_pub_{objID}         │
│                                                                    │
│  [6] 处理关联关系（如果 Excel 包含 association 工作表）               │
│   web_server/logics/inst.go:handleExcelAssociation()               │
│         └── CoreAPI.ApiServer().ImportAssociation()                │
│              └── topo_server:ImportInstanceAssociation()           │
│                   └── 写入 cc_InstAsst_{supplier}_pub_{objID}      │
└──────────────────────────────────────────────────────────────────┘
```

#### 9.2.3 关键数据结构

**Excel 导入请求（web_server → API Server）**：

```json
{
    "input_type": "excel",
    "bk_biz_id": 2,
    "BatchInfo": {
        "4": {
            "bk_asset_id": "SW-001",
            "bk_inst_name": "核心交换机-A",
            "bk_sn": "SN123456",
            "bk_vendor": "Huawei",
            "bk_model": "CE12800",
            "bk_admin_ip": "10.0.0.1",
            "bk_operator": "admin",
            "bk_biz_status": "2"
        },
        "5": {
            "bk_asset_id": "SW-002",
            "bk_inst_name": "核心交换机-B",
            "bk_model": "CE12800"
        }
    }
}
```

**Excel 导入请求参数（用户侧）**：

```json
{
    "bk_biz_id": 2,
    "op": 0,
    "association_cond": {},
    "object_unique_id": 0
}
```

| 参数字段 | 类型 | 说明 |
|---------|------|------|
| `bk_biz_id` | int64 | 业务 ID |
| `op` | int64 | 操作类型：0=导入实例，1=仅导入关联 |
| `association_cond` | map | 指定导入关联关系时使用的唯一键映射 |
| `object_unique_id` | int64 | 自关联时指定左对象的唯一索引 ID |

#### 9.2.4 batch 批量创建 API（JSON 方式）

除了 Excel 上传，还可以通过 REST JSON API 批量创建实例：

```
POST /api/v3/createmany/instance/object/{bk_obj_id}
```

请求体格式：

```json
{
    "details": [
        {
            "bk_asset_id": "SW-003",
            "bk_inst_name": "接入交换机-01",
            "bk_sn": "SN789012",
            "bk_vendor": "Cisco",
            "bk_model": "Nexus 9000",
            "bk_admin_ip": "10.0.1.1"
        },
        {
            "bk_asset_id": "SW-004",
            "bk_inst_name": "接入交换机-02"
        }
    ]
}
```

**代码实现**：`topo_server/service/inst.go:CreateManyInstance()`，同样有内置模型和主线模型的检查限制。

#### 9.2.5 模型批量导入（YAML/ZIP）

支持通过 ZIP 包或 YAML 格式批量导入模型定义，用于跨环境迁移模型结构：

```
POST /api/v3/object/importmany/analysis    ← 先分析导入内容
POST /api/v3/object/importmany             ← 执行导入
```

**实现**：`web_server/service/object.go:BatchImportObjectAnalysis()`、`BatchImportObject()`  
**核心逻辑**：`web_server/logics/object.go`

#### 9.2.6 实例关联批量导入

```
POST /api/v3/import/instassociation/{bk_obj_id}
POST /api/v3/createmany/instassociation
```

**实现**：`topo_server/service/object_association.go:ImportInstanceAssociation()`

#### 9.2.7 Excel 导入的 op 参数

`op` 参数控制 Excel 的不同用途：

| op 值 | 含义 | 说明 |
|-------|------|------|
| 0 | 导入实例 + 关联 | 默认模式，导入实例数据及 Excel 中的关联工作表 |
| 1 | 仅导入关联 | 仅处理 Excel 的 `association` 工作表，不导入实例 |

### 9.3 源代码文件索引

| 层级 | 文件 | 职责 |
|------|------|------|
| **web_server 路由** | `src/web_server/service/service.go` | 所有 Excel 导入导出路由注册 |
| **web_server 实例导入** | `src/web_server/service/inst.go` | `ImportInst()` handler，接收 Excel 上传 |
| **web_server 主机导入** | `src/web_server/service/host.go` | `ImportHost()`、`BuildDownLoadExcelTemplate()` |
| **web_server 导入逻辑** | `src/web_server/logics/inst.go` | `ImportInsts()`、`GetImportInsts()`、`importInsts()` |
| **web_server Excel 解析** | `src/web_server/logics/excel.go` | `GetExcelData()`、`BuildExcelFromData()`（705 行） |
| **topo_server 路由** | `src/scene_server/topo_server/service/service_initfunc.go` | 实例/模型相关路由注册 |
| **topo_server 实例 API** | `src/scene_server/topo_server/service/inst.go` | `CreateInstsByImport()`、`CreateManyInstance()` |
| **topo_server 关联 API** | `src/scene_server/topo_server/service/object_association.go` | `ImportInstanceAssociation()` |
| **API 网关路由** | `src/apiserver/service/url.go` | 统一路由分发到后端服务 |
| **CLI 入口** | `src/tools/cmdb_ctl/main.go` | cmdb_ctl CLI 入口 |
| **bkbiz CLI** | `src/scene_server/admin_server/command/command.go` | bkbiz 导入导出命令 |
| **bkbiz 导入** | `src/scene_server/admin_server/command/import.go` | JSON 业务拓扑导入实现 |
| **模型路由** | `src/common/mapping.go` | `IsInnerModel()`、`IsInnerMainlineModel()` 判断 |

---

## 十、以交换机为例的完整导入实战

### 10.1 交换机属于"通用模型"，支持批量导入

从 `IsInnerModel()` 源码可知，交换机（`bk_switch`）不在内置模型列表中，因此：

- ✅ **可以使用 Excel 导入**：`POST /insts/object/bk_switch/import`
- ✅ **可以使用 JSON 批量创建**：`POST /createmany/instance/object/bk_switch`
- ❌ **不能使用主机专用接口**：如 `POST /hosts/import` 仅适用于 `host` 模型

### 10.2 交换机 Excel 导入操作步骤

```bash
# Step 1: 下载交换机导入模板
curl -X POST "http://cmdb-web/importtemplate/bk_switch" \
  -F "bk_biz_id=2" \
  -o switch_template.xlsx

# Step 2: 用户打开 switch_template.xlsx，按模板填写交换机数据
#   ┌──────────────┬─────────────────┬──────────┬────────┬──────────┬─────────────┐
#   │ bk_asset_id*  │ bk_inst_name*   │ bk_sn    │ bk_vendor │ bk_model │ bk_admin_ip │ ...
#   ├──────────────┼─────────────────┼──────────┼────────┼──────────┼─────────────┤
#   │ SW-001        │ 核心交换机-A     │ SN123456 │ Huawei   │ CE12800  │ 10.0.0.1    │
#   │ SW-002        │ 核心交换机-B     │ SN789012 │ Cisco    │ Nexus9K  │ 10.0.0.2    │
#   └──────────────┴─────────────────┴──────────┴────────┴──────────┴─────────────┘

# Step 3: 上传 Excel 执行导入
curl -X POST "http://cmdb-web/insts/object/bk_switch/import" \
  -F "file=@switch_template.xlsx" \
  -F 'params={"bk_biz_id":2,"op":0}'

# 响应:
# {
#   "result": true,
#   "bk_error_code": 0,
#   "bk_error_msg": "",
#   "data": {
#     "success": ["SW-001", "SW-002"],
#     "error": []
#   }
# }
```

### 10.3 交换机 JSON 批量创建操作步骤

```bash
# Step 1: 直接通过 API 批量创建
curl -X POST "http://cmdb-api/api/v3/createmany/instance/object/bk_switch" \
  -H "Content-Type: application/json" \
  -d '{
    "details": [
      {
        "bk_asset_id": "SW-010",
        "bk_inst_name": "汇聚交换机-01",
        "bk_sn": "SN-AGG-001",
        "bk_vendor": "Huawei",
        "bk_model": "S6730",
        "bk_admin_ip": "10.1.0.1",
        "bk_func": "汇聚层",
        "bk_operator": "admin",
        "bk_biz_status": "2",
        "bk_detail": "三楼机房汇聚交换机"
      }
    ]
  }'

# Step 2: 批量创建交换机与主机的关联
curl -X POST "http://cmdb-api/api/v3/createmany/instassociation" \
  -H "Content-Type: application/json" \
  -d '{
    "bk_obj_id": "bk_switch",
    "details": [
      {
        "bk_inst_id": <switch_inst_id>,
        "bk_asst_inst_id": <host_inst_id>,
        "bk_obj_asst_id": "bk_switch_connect_host"
      }
    ]
  }'
```

### 10.4 交换机导入的完整路径对照

```
┌─────────────────────┬──────────────────────────────────────────┐
│  数据层              │  操作方式                                 │
├─────────────────────┼──────────────────────────────────────────┤
│ 模型定义（元数据）     │  init_db 预置 (v3.0.8)                   │
│ 属性定义             │  init_db 预置 (SwitchRow)                 │
│ 模型关联             │  init_db 预置 (x18.12.13.01)              │
│ 属性分组             │  init_db 预置 (default 分组)               │
│ 唯一约束             │  可选，通过 API 添加                       │
├─────────────────────┼──────────────────────────────────────────┤
│ 实例数据             │  ✅ Excel 导入 / ✅ JSON 批量创建           │
│ 实例关联             │  ✅ Excel 关联工作表 / ✅ JSON 批量创建     │
└─────────────────────┴──────────────────────────────────────────┘
```

### 10.5 导入限制与约束

| 限制条件 | 说明 | 源码位置 |
|---------|------|---------|
| **禁止对内置模型使用通用 API** | `biz/set/module/host/process/plat` 不能用 `CreateInstsByImport` 或 `CreateManyInstance` | `topo_server/service/inst.go` 中的 `IsInnerModel()` 检查 |
| **禁止对主线模型使用通用 API** | `biz/set/module` 不能用通用创建接口 | `topo_server/service/inst.go` 中的 `IsMainlineObject()` 检查 |
| **交换机不受限制** | `bk_switch` 是通用模型，可以正常使用所有批量导入接口 | `common/mapping.go:IsInnerModel()` 返回 false |
| **Excel 模板依赖模型属性** | 模板字段由 `cc_ObjAttDes` 中定义的属性动态生成 | `web_server/logics/excel.go` |
| **分片表需先创建** | 实例表由 `RunSyncDBTableIndex()` 后台自动创建，新模型需等待同步完成 | `logics/index.go` |

---

## 十一、总结（更新）

1. **bk-cmdb 的 init_db 是一个版本化的增量迁移系统**，通过 `cc_System` 表记录当前版本，每次部署按版本号顺序执行所有未执行的升级器
2. **元数据层（6 张表）是模型驱动架构的根基**：分类 → 模型 → 属性分组 → 属性 → 关联 → 唯一约束，形成严格的依赖链
3. **交换机模型涉及 8 张表**：6 张元数据表 + 2 张分片实例表，11 个预置属性，1 条与主机的 connect 关联
4. **实例存储分两类**：内置模型（biz/set/module/host/process/plat）有独立表，通用模型（如 switch）走分片表 `cc_ObjectBase_{supplier}_pub_{objID}`
5. **Upsert 机制保证了数据初始化的幂等性**，重复执行不会产生重复数据
6. **通用数据迁移遵循：分类 → 模型 → 分组 → 属性 → 关联 → 建表 → 写数据的固定顺序**
7. **✅ 存在 CLI 接口**：`cmdb_ctl` 运维工具（侧重诊断，不直接导入实例）、`admin_server bkbiz`（JSON 格式蓝鲸业务拓扑导入）
8. **✅ 存在 HTTP API 接口**：完整的 Excel 导入/导出、JSON 批量创建、关联批量导入，通用于所有非内置模型（含交换机）
9. **数据迁移推荐路径**：元数据用 init_db 版本升级 → 实例数据用 Excel 导入或 JSON 批量创建 API
