# bk_cmdb_py

bk-cmdb 的 **Python 后端（`app.py`）+ UI 服务（`ui_server.py`）**，用于把 `prod_bin` 的前端 UI 与 bk-cmdb 的 `cmdb` MongoDB 实例在**最小依赖**下对接起来。

本项目当前只做两个组件：

| 组件 | 入口 | 说明 |
|---|---|---|
| **UI 服务** | `ui_server.py` :8085 | 托管 prod_bin 静态资源、渲染登录/首页、真实登录（`admin/admin`），并反向代理 `/api/v3` 到 Python 后端。**不依赖 Go 服务 / ZooKeeper / Redis**。 |
| **Python 后端** | `app.py` :3000 | 业务 / 对象 / 模块 / 用户等 REST，直接读写 `cmdb` 实例数据。 |

> 本说明重点约束 **数据库连接方式**（最近一次重构的核心诉求）：
> **统一连接 bk-cmdb 通过 initdb 初始化的 `cmdb` MongoDB 实例，项目不再维护任何本地 mock 数据。**

---

## 1. 数据库连接要求（核心约定）

| 项 | 说明 |
|---|---|
| **数据源** | bk-cmdb 通过 `initdb` 写入的 **`cmdb`** MongoDB 数据库（真实拓扑 / 主机 / 模型数据） |
| **不再使用** | 项目私有的 `bk_cmdb` 库（历史上存放仿真 mock 数据，**现已清理删除**） |
| **无 mock 初始化** | 已移除 `INIT_DATA` 字典与 `init_mock_data()`；`init_data.py` / `init_mongo_data.py` 不再播种数据 |
| **连接校验** | 启动仅做「MongoDB 引擎是否可达」校验（`verify_db()`），用 `check_db.py` 可手动验证 |
| **多实例关系** | `cmdb_server_py` 直接读取 bk-cmdb 的 `cmdb` 库（共享同一 Mongo 实例） |

### 1.1 连接配置（环境变量）

| 变量 | 默认值 | 含义 |
|---|---|---|
| `MONGODB_URI` | `mongodb://cc:cc@127.0.0.1:27017/cmdb?authSource=cmdb` | Mongo 连接串（指向 `cmdb` 实例） |
| `MONGODB_DB` | `cmdb` | 使用的数据库名（**必须为 `cmdb`**） |
| `SKIP_LOGIN` | `false` | 是否跳过登录；完整系统以 `false` 启动，走真实登录（`admin/admin`） |

> 配置位于 `app/config.py`；`start_ui_system.sh` 在拉起 `app.py` 时显式注入上述变量，`MONGODB_DB=cmdb`。

### 1.2 确认 MongoDB 引擎有效

```bash
cd /workspace/bk_cmdb_py/cmdb_server_py
python3.11 check_db.py
```

预期输出：`MongoDB 引擎连接有效`，并列出 79 个集合、核心集合
（`cc_ApplicationBase` / `cc_HostBase` / `cc_ModuleBase` / `cc_ModuleHostConfig` …）计数均 > 0。
运行时亦可用：

```bash
curl http://127.0.0.1:3000/health      # {"result": true,...}
curl http://127.0.0.1:3000/init/check  # 返回 cmdb 实例的集合与计数
```

---

## 2. 目录与组件

| 组件 | 文件 / 目录 | 端口 | 职责 |
|---|---|---|---|
| Python 后端 | `app.py`（Flask） | 3000 | 业务 / 对象 / 模块 / 用户等 REST，`cmdb` 实例数据读写 |
| **UI 服务** | `ui_server.py`（Flask） | 8085 | 托管 `prod_bin` 静态资源、渲染 `index.html`/`login.html` Go 模板、处理登录、反向代理 `/api/v3` |
| 数据访问层 | `app/models/db.py` | — | `get_db_connection()` / `get_mongo_collection()` / `is_mongo_available()` |
| 连接校验 | `check_db.py` | — | 校验 `cmdb` 实例连接与核心集合 |
| 启动编排（完整系统） | `../start_ui_system.sh` | — | 最小依赖：仅拉起 MongoDB + `app.py` + `ui_server.py` |

---

## 3. 架构与数据流

### 3.1 完整系统模式（最小依赖）

```
浏览器
  │  GET /            →  UI 服务 :8085（无 cookie 则 302 → /login）
  │  POST /login      →  UI 服务校验 admin/admin，下发 bk_token Cookie
  │  /api/v3/*        →  UI 服务反代 → Python 后端 :3000（透传 bk_token）
  ▼
ui_server.py :8085
  ├─ /static/*        → 托管 prod_bin/ui（css/js/img/svg）
  ├─ / /login         → 渲染 index.html / login.html（注入 window.Site/User/Supplier/ESB）
  └─ /api/v3/*        → 反代 app.py :3000
        ▼
app.py :3000 → 直接读 cmdb 实例（cc_ApplicationBase / cc_HostBase / cc_ObjAttDes …）
```

- **登录**：内置管理员 `admin/admin`（与 `common.yaml` `webServer.session.userInfo` 对齐）。`users` 集合不存在时，由 `Config.is_superuser()` + 明文比对兜底，**不写入 MongoDB**。
- **超级管理员**：`admin` 不受 `user_business` 权限表约束（`user_business` 集合在 initdb 后本就缺省），可见全部业务与拓扑。
- **依赖**：仅需 MongoDB（`cmdb` 实例 + initdb 数据）；无需 Go 服务 / ZooKeeper / Redis。

---

## 4. 运行

### 4.1 完整系统（推荐，最小依赖）

```bash
# 仅依赖 MongoDB（cmdb 实例 + initdb 数据），拉起 Python 后端 + UI 服务
bash /workspace/bk_cmdb_py/start_ui_system.sh
# 然后访问 http://127.0.0.1:8085/  账号 admin / admin
```

等价于：

```bash
cd /workspace/bk_cmdb_py/cmdb_server_py
# 后端
MONGODB_URI="mongodb://cc:cc@127.0.0.1:27017/cmdb?authSource=cmdb" \
MONGODB_DB="cmdb" SKIP_LOGIN=false \
python3.11 app.py &
# UI 服务
UI_PORT=8085 BACKEND_URL="http://127.0.0.1:3000" \
PROD_UI_DIR="../prod_bin/ui" python3.11 ui_server.py &
```

> `start_ui_system.sh` 中的 `SKIP_LOGIN=false` 表示走真实登录（不再自动跳过），登录入口使用 `admin/admin` 内置管理员。

---

## 5. 已知事项 / 注意事项

1. **依赖 bk-cmdb initdb**：`cmdb_server_py` 不创建任何集合；`cmdb` 库必须由 bk-cmdb 的 `initdb` 流程先初始化（业务 / 主机 / 模型等数据来源于此）。
2. **集合名以 bk-cmdb 为准**：部分路由直接读取 `cc_ApplicationBase` / `cc_HostBase` / `cc_ObjAttDes` 等真实集合名；个别旧路由曾使用 `cc_BizSet` / `cc_HostModuleRelation` / `cc_BaseModule` 等 mock 命名，已在 fallback 中改为读取真实集合（`cc_BizSetBase` / `cc_ModuleHostConfig`），其余命名差异随路由层逐步对齐。
3. **`bk_cmdb` 库已删除**：本项目的 mock 库已清理，MongoDB 实例仅保留 `cmdb`（initdb 实例）与系统库（`admin` / `config` / `local`）。
4. **鉴权**：`SKIP_LOGIN=false` 走真实登录。内置管理员 `admin/admin`（与 `common.yaml` `webServer.session.userInfo` 对齐）。当 `users` 集合不存在时，由 `Config.is_superuser()` + 明文比对兜底，**不写入 MongoDB**；`admin` 为超级管理员，不受 `user_business` 权限表约束，可见全部业务与拓扑。

---

参考：[集成 SOP](INTEGRATION_SOP.md)
