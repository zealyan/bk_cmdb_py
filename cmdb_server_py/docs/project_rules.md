# BK-CMDB Python 后端项目规则

## 一、前置条件

### 1.1 基础环境要求

| 依赖 | 版本要求 | 说明 |
|------|----------|------|
| Python | 3.10 | 后端开发语言 |
| MongoDB | 4.4+ (端口 27017) | **必须依赖的主数据库** |
| Node.js | 16+ | 前端构建环境 |

### 1.2 核心框架

| 框架 | 版本要求 | 用途 |
|------|----------|------|
| Flask | >=2.3.0 | Web 框架 |
| Flask-Cors | >=4.0.0 | 跨域支持 |
| Flask-SQLAlchemy | >=3.1.0 | SQLAlchemy Flask 集成 |

### 1.3 ORM 组件

| 组件 | 版本要求 | 用途 |
|------|----------|------|
| PyMongo | >=4.0.0 | MongoDB 官方驱动 |
| MongoEngine | >=0.28.0 | MongoDB ORM，含 Signals 机制 |
| py-pglite | >=0.5.0 | **附属副本库** 开发环境 PostgreSQL 模拟器 |
| psycopg[binary] | >=3.3.0 | PostgreSQL 驱动（py-pglite 依赖） |

### 1.4 数据库角色定位

| 数据库 | 角色 |  说明 |
|--------|------|------|
| **MongoDB** | **唯一主数据库** | 所有数据必须存储在 MongoDB |
| **PostgreSQL** | **附属库做同步审核、全文检索**  | 生产部署使用，开发环境用pglite替代 |

**重要原则**：
- **⚠️ MongoDB 是唯一的主数据库**：所有数据必须存储在 MongoDB，是项目的强依赖
- **py-pglite 是附属副本库**：仅作为开发环境补充，用于快速原型和测试
- **不得强依赖 py-pglite**：代码必须能够在没有 py-pglite 的情况下正常工作
- 数据库访问层必须保持足够的抽象，兼容两种数据库
- 所有 SQL 语句必须符合 PostgreSQL 标准语法
- **⚠️ 绝对禁止使用内存数据库回退**：**必须使用 MongoDB 进行所有数据读写操作，不能使用任何内存数据库回退机制**

### 1.5 数据库环境说明

| 环境 | 数据库 | 用途 | 管理方式 |
|------|--------|------|----------|
| **开发环境** | MongoDB + py-pglite | MongoDB 必需（主），py-pglite 辅助（副本） | Node.js 管理 pglite |
| **生产环境** | MongoDB + PostgreSQL | 主数据库 + 前置写入库 | 独立服务 |

**py-pglite 架构调整**：
- **Node.js 管理**：使用 `@electric-sql/pglite` + `@electric-sql/pglite-socket` 启动 PGlite server
- **Socket 连接**：Python 通过 Unix Socket 连接到 PGlite server
- **权限设置**：数据目录和 socket 文件权限设置为 `777`，确保跨进程访问
- **认证方式**：升级 PGlite 包版本，使用新的 API，移除认证配置，使用默认信任模式
- **附属定位**：仅作为开发环境补充，不得替代 MongoDB 作为主数据源

### 1.6 数据库抽象要求

**必须遵守的抽象原则**：
1. **连接管理抽象**：通过配置切换 py-pglite（Socket）和 PostgreSQL（TCP）连接
2. **SQL 语法兼容**：使用标准 PostgreSQL 语法，避免 py-pglite 特定功能
3. **表结构一致**：MongoDB 和 PostgreSQL 表结构保持完全一致
4. **初始化逻辑统一**：同一套初始化脚本支持两种数据库
5. **Socket 权限管理**：确保 pglite_data 目录和 socket 文件权限为 `777`
6. **MongoDB 优先**：所有核心功能必须以 MongoDB 为主数据源

---

## 二、开发优先原则

### 2.0 错误排查优先原则（重中之重）

**⚠️ 遇到前端错误时，优先排查并修改后端代码，而不是先修改前端**

**核心原则**：
1. **优先排查后端**：当遇到前端报错时，首先假设是后端API问题，而不是前端问题
2. **先查后端**：先检查后端API是否正确实现，数据格式是否正确
3. **数据格式优先**：确保后端返回数据格式必须与原API完全一致
4. **不要假设前端问题**：不要轻易认为是前端bug，先验证后端
5. **UI不轻易修改**：除非100%确定后端完全正确，才考虑UI调整
6. **调试优先级**：调试时优先测试后端API，用Postman等工具先确认后端正确

**错误处理流程**：
```
前端报错 → 1. 检查后端API返回 → 2. 检查数据库数据 → 3. 检查后端代码 → 4. 最后才考虑前端
```

**调试建议**：
- 使用 Postman 或 curl 直接调用API，确认返回正确
- 检查前端Network请求，看返回数据是否完整
- 对比原项目的API调用记录，确保格式一致
- 先修复后端代码，而不是修改前端

---

### 2.1 UI 源码修改规则（重要）

**⚠️ 禁止修改UI源码，违反者将被追责**

#### 2.1.1 核心原则
- **绝对禁止修改UI源码**：严格禁止修改 `/workspace/bk_cmdb_py/ui/` 目录下的任何代码
- **接口兼容性优先**：确保后端API与原有接口完全兼容，接口格式不能随意变更
- **向后兼容性**：任何后端变更都不能破坏现有前端功能
- **功能一致性**：前端功能应保持原样，仅通过后端适配实现需求
- **严格禁止理由**：UI代码是参考原项目的实现，修改会破坏与原项目的一致性

#### 2.1.2 强制执行规则
- **后端唯一性**：所有功能实现和问题修复必须通过修改后端代码完成
- **前端零修改**：不得以任何理由修改前端代码，即使"最小改动"也不允许
- **API适配原则**：如果前端需要的功能后端未实现，必须实现后端API而非修改前端
- **数据格式适配**：如果后端数据格式与前端期望不一致，必须修改后端返回格式

#### 2.1.3 违规处理
- 发现修改UI源码的行为将进行追责
- 如需修改前端，必须经过充分讨论和审批
- 任何临时性或快速修复都不能作为修改前端的理由

#### 2.1.4 API设计原则
- **保持接口格式**：后端API返回格式必须与前端期望的格式完全一致
- **字段兼容性**：不要移除或重命名现有字段，新增字段应提供默认值
- **错误处理**：保持原有的错误码和错误信息格式
- **功能完整性**：所有前端调用的API都必须在后端完整实现

---

## 三、数据库使用规范

### 3.1 MongoDB 主数据库要求

**⚠️ 所有数据操作必须使用 MongoDB**

1. **必须使用 MongoDB 作为唯一数据源**
   - 所有数据的读写操作必须通过 MongoDB 完成
   - 禁止使用 Python 内存字典、列表等作为数据存储
   - 禁止使用文件系统作为数据存储
   - **绝对禁止任何内存数据库回退机制**

2. **MongoDB 连接失败时应该返回错误**
   - 不能有任何内存数据回退逻辑
   - 连接失败时直接抛出错误或返回 500 状态码
   - 保证 MongoDB 是唯一的数据来源

3. **默认数据必须初始化到 MongoDB**
   - 所有默认数据、测试数据必须在启动时写入到 MongoDB
   - 使用 `init_mock_data()` 函数（在 [app/models/db.py](file:///workspace/bk_cmdb_py/app/models/db.py#L299) 中定义）初始化
   - 不能在代码中硬编码默认数据，除非用于调试排查

4. **数据库访问方式**
   - 使用 `db` 对象访问，例如：`db.cc_ApplicationBase.find({})`
   - 使用 `update_one`、`insert_one` 等 PyMongo API
   - 所有集合名按照 BK-CMDB 规范命名（例如：`cc_ApplicationBase`、`cc_ObjAttDes`）

### 3.2 数据库初始化

**MongoDB 初始化流程**：

1. 启动时检查 MongoDB 连接
2. 调用 `init_mock_data()` 初始化所有默认数据
3. 确保所有必要的集合和文档都存在

**初始化数据集合**（在 [app/models/db.py](file:///workspace/bk_cmdb_py/app/models/db.py#L18) 中定义）：
- `cc_ObjectBase` - 对象模型定义
- `cc_ObjAttDes` - 对象属性定义
- `cc_ObjAttGroup` - 属性分组定义
- `cc_ObjClassification` - 对象分类定义
- `cc_ApplicationBase` - 业务数据
- `cc_PlatBase` - 云区域数据
- `users` - 用户数据
- `user_business` - 用户业务关联
- `cc_System` - 系统配置
- `auth_policies` - 权限策略

---

## 四、开发环境工具

### 4.1 Skip Login 功能（开发环境）

**⚠️ 仅用于开发环境，生产环境必须关闭！**

Skip Login 允许开发者在不输入用户名密码的情况下自动登录系统。

#### 4.1.1 启用方式

通过环境变量启用：

```bash
# 启用 Skip Login（使用默认 admin 用户）
export SKIP_LOGIN=true

# 可选：指定自动登录的用户（默认 admin）
export SKIP_LOGIN_USER=admin

# 启动后端服务
cd /workspace/bk_cmdb_py
source venv/bin/activate
python app.py
```

#### 4.1.2 工作原理

Skip Login 实现参考了 Go 原版 BK-CMDB 的实现方式：

**Go 实现参考**：
- 文件：[skip_login.go](file:///workspace/bk-cmdb-release-v3.10.41/src/web_server/middleware/user/plugins/register/skip_login.go)
- 实现：[userinfo.go](file:///workspace/bk-cmdb-release-v3.10.41/src/web_server/middleware/user/plugins/method/skip/userinfo.go)
- 配置键：`webServer.login.version = "skiplogin"`

**Python 实现**：
- 配置文件：[config.py](file:///workspace/bk_cmdb_py/app/config.py#L83-L85)
- 认证逻辑：[user_routes.py](file:///workspace/bk_cmdb_py/app/routes/user_routes.py#L41-L83)
- 登录接口：[user_auth()](file:///workspace/bk_cmdb_py/app/routes/user_routes.py#L92-L177)

#### 4.1.3 功能特性

当 Skip Login 启用时：
1. ✅ 所有 API 请求自动使用管理员身份，无需 Token 验证
2. ✅ `/user/auth` 登录接口自动登录配置的用户
3. ✅ `/user/info` 接口返回管理员用户信息
4. ✅ 所有需要 `@require_auth` 装饰器的接口自动放行
5. ✅ 前端无需输入用户名密码即可访问所有功能

#### 4.1.4 安全警告

**⚠️ 重要提醒**：
- **禁止在生产环境启用**：Skip Login 会绕过所有身份验证
- **仅本地开发使用**：确保在安全的开发环境中使用
- **自动配置**：生产环境应移除 `SKIP_LOGIN=true` 环境变量

#### 4.1.5 Go vs Python 实现对比

| 特性 | Go 实现 | Python 实现 |
|------|---------|------------|
| 配置方式 | config.yaml | 环境变量 |
| 配置文件键 | `webServer.login.version = "skiplogin"` | `SKIP_LOGIN=true` |
| 默认用户 | admin | admin（可配置） |
| Cookie 处理 | Cookie: `BKHTTPOwnerID` | Cookie: `bk_token` |
| 会话管理 | Redis Session | Python Session |

---

## 五、项目结构说明

### 5.1 目录组织
```
/workspace/bk_cmdb_py/
├── app/              后端Flask应用
├── ui/               前端应用（⚠️ 尽量不要修改）
├── docs/             文档
├── scripts/          脚本工具
├── venv/             Python虚拟环境
└── ...
```

### 5.2 开发边界
- **后端开发**：专注于 `/workspace/bk_cmdb_py/app/` 目录
- **前端使用**：仅使用 `/workspace/bk_cmdb_py/ui/` 目录，不做修改
- **API对接**：确保后端API与前端完美适配

