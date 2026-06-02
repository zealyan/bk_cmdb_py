# BK-CMDB Python 后端架构设计

## 一、项目目标

1. **技术栈转换**：Go 后端 → Python 3.10 + Flask + MongoDB 4.4
2. **数据一致性**：MongoDB 数据结构与原 Go 项目完全一致
3. **数据同步架构**：MongoEngine Signals + AOP 机制
   - 读取：MongoDB
   - 写入：PostgreSQL (前置) → MongoDB (后置)
   - 写入前钩子：支持开关配置

---

## 二、数据库配置

### 2.1 数据库角色定位

| 数据库 | 角色 | 说明 |
|--------|------|------|
| **MongoDB** | **主数据库** | 被项目强依赖，不得用 py-pglite 替代 |
| **py-pglite** | **附属副本库** | 作为开发环境补充，不得强依赖 |
| **PostgreSQL** | 生产环境替代 | 生产部署时替代 py-pglite |

**核心原则**：
- **MongoDB 是主数据库**：所有核心数据必须存储在 MongoDB，是项目的强依赖
- **py-pglite 是附属副本库**：仅作为开发环境补充，用于快速原型和测试
- **不得强依赖 py-pglite**：代码必须能够在没有 py-pglite 的情况下正常工作
- 所有 SQL 语句必须符合 PostgreSQL 标准语法

### 2.2 数据库环境说明

| 环境 | 数据库 | 用途 | 部署方式 |
|------|--------|------|----------|
| **开发环境** | MongoDB + py-pglite | 开发测试 | MongoDB 必需，py-pglite 辅助 |
| **生产环境** | MongoDB + PostgreSQL | 正式部署 | 需独立部署 MongoDB 和 PostgreSQL |

### 2.3 MongoDB 配置

| 配置项 | 值 | 说明 |
|--------|-----|------|
| **Database Name** | `bk_cmdb` | MongoDB 数据库名称 |
| **Connection URI** | `mongodb://localhost:27017/` | 连接地址 |
| **Port** | `27017` | MongoDB 端口 |
| **用途** | 主数据存储/读取源 | 所有读取操作直接访问 MongoDB |

### 2.4 py-pglite 配置（开发环境）

| 配置项 | 值 | 说明 |
|--------|-----|------|
| **Data Directory** | `./pglite_data` | py-pglite 数据存储目录 |
| **Socket Path** | `./pglite_data/.s.PGSQL.5432` | Unix Socket 文件路径 |
| **Database Name** | `postgres` | 默认数据库名 |
| **Schema** | `public` (默认) | 数据库 Schema |
| **用途** | 附属副本/关系型查询 | 仅开发环境补充使用 |
| **Driver** | psycopg[binary] | PostgreSQL 驱动 |
| **管理方式** | Node.js | 使用 `@electric-sql/pglite` + `@electric-sql/pglite-socket` 启动 |
| **连接方式** | Unix Socket | Python 通过 Socket 连接 |
| **Socket 权限** | `777` | 跨进程访问需要 |

**架构说明**：
- **Node.js 管理**：使用 Node.js 启动 PGlite server，避免 Python 包的权限问题
- **Socket 连接**：Python 通过 Unix Socket 连接到 PGlite server
- **权限设置**：数据目录和 socket 文件权限设置为 `777`，确保跨进程访问
- **附属定位**：仅作为开发环境补充，不得替代 MongoDB 作为主数据源

### 2.5 PostgreSQL 配置（生产环境）

| 配置项 | 值 | 说明 |
|--------|-----|------|
| **Host** | `localhost` | PostgreSQL 服务地址 |
| **Port** | `5432` | PostgreSQL 端口 |
| **Database** | `bk_cmdb` | 数据库名称 |
| **Schema** | `public` | 数据库 Schema |
| **Driver** | psycopg[binary] | PostgreSQL 驱动 |
| **用途** | 前置写入/关系型查询 | 生产环境部署 |

---

## 三、架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                         UI Layer                             │
│                   (Vue.js + Webpack)                        │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP/REST
┌─────────────────────────▼───────────────────────────────────┐
│                    Python Backend                            │
│                     (Flask + Gunicorn)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   API Layer   │  │  Logic Layer │  │  Auth Layer  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              AOP / Signals 机制                         │  │
│  │   ┌─────────────────────────────────────────────────┐   │  │
│  │   │  写入前钩子 (Pre-Write Hook)  [可配置开关]      │   │  │
│  │   │  - 数据转换 (Transform)                          │   │  │
│  │   │  - 业务确认 (Validation)                         │   │  │
│  │   │  - 通知触发 (Notification)                       │   │  │
│  │   └─────────────────────────────────────────────────┘   │  │
│  └────────────────────────────────────────────────────────┘  │
└─────────────────────────┬───────────────────────────────────┘
                          │
        ┌─────────────────┴─────────────────┐
        ▼                                   ▼
┌───────────────────────────┐  ┌───────────────────────────┐
│         MongoDB           │  │  py-pglite (开发环境)     │
│    ★ 主数据库 ★           │  │  PostgreSQL (生产环境)    │
│  (不得被替代/强依赖)      │  │  (附属副本库)             │
│                           │  │                          │
│ - cc_ApplicationBase      │  │ - cc_ApplicationBase     │
│ - cc_HostBase             │  │ - cc_HostBase            │
│ - cc_ModuleBase           │  │ - cc_ModuleBase          │
│ - cc_SetBase              │  │ - cc_SetBase             │
│ - cc_PlatBase             │  │ - cc_PlatBase            │
│ - cc_System               │  │ - cc_System              │
│ - users                   │  │ - users                  │
│ - user_business           │  │ - user_business          │
│ - cc_UserCustom           │  │ - cc_UserCustom          │
└───────────────────────────┘  └───────────────────────────┘
```

写入流程:
  1. UI → Backend
  2. AOP 拦截 → 写入前钩子 (可选)
     ├── 数据转换
     ├── 业务确认
     └── 通知触发
  3. 写入 PostgreSQL (前置)
  4. 确认成功后 → 写入 MongoDB (后置)

---

## 四、对象属性系统

### 4.1 属性概述

对象属性（Object Attribute）是蓝鲸配置管理（CMDB）中描述业务模型字段的核心机制。每个属性都包含一组系统标志位，用于控制字段在表单中的显示、编辑、验证等行为。

### 4.2 字段命名转换规则

MongoDB 数据库与前端 API 之间存在字段命名风格的转换：

| MongoDB 字段名 | API 返回字段名 | 数据类型 | 说明 |
|---------------|---------------|---------|------|
| `is_readonly` | `isreadonly` | Boolean | 是否只读 |
| `is_required` | `isrequired` | Boolean | 是否必填 |
| `is_pre` | `ispre` | Boolean | 是否预置字段 |
| `is_only` | `isonly` | Boolean | 是否唯一 |
| `bk_is_system` | `bk_issystem` | Boolean | 是否系统内置 |
| `bk_is_api` | `bk_isapi` | Boolean | 是否 API 创建字段 |

**后端转换代码** ([object_routes.py:124-135](file:///workspace/bk_cmdb_py/app/routes/object_routes.py#L124-L135)):

```python
attr = {
    "isreadonly": doc.get("is_readonly"),
    "isrequired": doc.get("is_required"),
    "ispre": doc.get("is_pre"),
    "isonly": doc.get("is_only"),
    "bk_issystem": doc.get("bk_is_system"),
    "bk_isapi": doc.get("bk_is_api"),
    "default": doc.get("default")
}
for key in ["isreadonly", "isrequired", "ispre", "isonly", "bk_issystem", "bk_isapi"]:
    if attr.get(key) is None:
        attr[key] = False
```

### 4.3 系统属性详解

#### 4.3.1 `bk_is_api` / `bk_isapi`

| 属性 | 值 |
|------|-----|
| **MongoDB 字段** | `bk_is_api` |
| **API 返回字段** | `bk_isapi` |
| **数据类型** | Boolean |
| **用途** | 控制字段在创建模式下是否显示 |

**行为规则**：
- `true`: 在**创建模式**下隐藏该字段（通常用于系统自动生成的 ID 字段）
- `false`: 在创建模式下显示该字段（用户可填写）

**前端逻辑** ([form.vue:193-197](file:///workspace/bk_cmdb_py/ui/src/components/ui/form/form.vue#L193-L197)):

```javascript
checkEditable(property) {
  if (this.type === 'create') {
    return !property.bk_isapi  // bk_isapi=true 时返回 false，字段被隐藏
  }
  return property.editable && !property.bk_isapi && !this.uneditableProperties.includes(property.bk_property_id)
}
```

**典型应用场景**：
- `bk_biz_id`: `bk_is_api=true` → 业务 ID 由系统自动分配，创建时隐藏
- `bk_biz_name`: `bk_is_api=false` → 业务名称需用户填写，创建时显示

#### 4.3.2 `bk_is_system` / `bk_issystem`

| 属性 | 值 |
|------|-----|
| **MongoDB 字段** | `bk_is_system` |
| **API 返回字段** | `bk_issystem` |
| **数据类型** | Boolean |
| **用途** | 标识字段是否为系统内置属性 |

**行为规则**：
- `true`: 系统内置属性，通常由系统自动管理
- `false`: 用户自定义属性

#### 4.3.3 `is_readonly` / `isreadonly`

| 属性 | 值 |
|------|-----|
| **MongoDB 字段** | `is_readonly` |
| **API 返回字段** | `isreadonly` |
| **数据类型** | Boolean |
| **用途** | 控制字段是否只读 |

**行为规则**：
- `true`: 字段在编辑模式下禁用，不可修改
- `false`: 字段可编辑

**前端逻辑** ([form.vue:199-203](file:///workspace/bk_cmdb_py/ui/src/components/ui/form/form.vue#L199-L203)):

```javascript
checkDisabled(property) {
  if (this.type === 'create') {
    return false  // 创建模式下不应用只读限制
  }
  return !property.editable || property.isreadonly || this.disabledProperties.includes(property.bk_property_id)
}
```

#### 4.3.4 `is_required` / `isrequired`

| 属性 | 值 |
|------|-----|
| **MongoDB 字段** | `is_required` |
| **API 返回字段** | `isrequired` |
| **数据类型** | Boolean |
| **用途** | 标记字段是否为必填项 |

**行为规则**：
- `true`: 字段在表单中显示必填标记（红色 `*`），提交时进行验证
- `false`: 字段为可选项

**前端逻辑** ([form.vue:205-207](file:///workspace/bk_cmdb_py/ui/src/components/ui/form/form.vue#L205-L207)):

```javascript
isRequired(property) {
  return property.isrequired
}
```

#### 4.3.5 `is_only` / `isonly`

| 属性 | 值 |
|------|-----|
| **MongoDB 字段** | `is_only` |
| **API 返回字段** | `isonly` |
| **数据类型** | Boolean |
| **用途** | 标记字段值在整个模型中是否唯一 |

**行为规则**：
- `true`: 字段值必须唯一（通常用于 ID 类字段如 `bk_biz_id`、`bk_host_id`）
- `false`: 字段值可以重复

#### 4.3.6 `is_pre` / `ispre`

| 属性 | 值 |
|------|-----|
| **MongoDB 字段** | `is_pre` |
| **API 返回字段** | `ispre` |
| **数据类型** | Boolean |
| **用途** | 标记字段是否为预置字段 |

**行为规则**：
- `true`: 系统初始化时创建的预置字段，不可删除
- `false`: 用户自定义添加的字段

### 4.4 业务对象属性配置示例

以下以**业务（biz）**对象为例，展示各属性的典型配置：

| 属性ID | 属性名称 | bk_is_api | bk_is_system | is_readonly | is_required | is_only | is_pre | 说明 |
|--------|---------|-----------|--------------|-------------|-------------|---------|--------|------|
| `bk_biz_id` | 业务ID | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | 系统自动生成，创建时隐藏 |
| `bk_biz_name` | 业务名称 | ✗ | ✗ | ✗ | ✓ | ✗ | ✓ | 用户必填，创建时显示 |
| `bk_maintainer` | 运维负责人 | ✗ | ✗ | ✗ | ✓ | ✗ | ✓ | 用户必填，创建时显示 |
| `bk_supplier_account` | 开发商账号 | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ | 系统管理，创建时隐藏 |
| `create_time` | 创建时间 | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ | 系统自动记录，只读 |
| `last_time` | 更新时间 | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ | 系统自动更新，只读 |
| `time_zone` | 时区 | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | 用户可选，有默认值 |
| `operator` | 最后修改人 | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ | 系统自动记录，只读 |

### 4.5 表单交互逻辑总结

```
┌─────────────────────────────────────────────────────────────────┐
│                        表单类型                                  │
│                                                                 │
│   ┌─────────────────────┐         ┌─────────────────────────┐   │
│   │    创建模式 (create)  │         │   编辑模式 (update)      │   │
│   └─────────┬───────────┘         └───────────┬─────────────┘   │
│             │                                   │                 │
│             ▼                                   ▼                 │
│   checkEditable():                       checkEditable():         │
│   return !bk_isapi                      return editable          │
│                                           && !bk_isapi            │
│                                           && !uneditableProps     │
│                                                                 │
│   checkDisabled():                       checkDisabled():         │
│   return false (不禁用)                  return !editable         │
│                                           || isreadonly           │
│                                           || disabledProps         │
└─────────────────────────────────────────────────────────────────┘
```

**关键规则**：

1. **创建模式下**：
   - `bk_is_api=true` 的字段**不显示**
   - 所有字段都**不禁用**
   - `is_required=true` 的字段**必须填写**

2. **编辑模式下**：
   - `bk_is_api=true` 的字段**不显示**
   - `is_readonly=true` 或 `editable=false` 的字段**禁用**
   - `is_required` 验证通常不生效（已有值）
