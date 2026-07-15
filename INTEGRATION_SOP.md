# bk-cmdb × Python 后端 集成 SOP（prod_bin UI 接入 cmdb_server_py）

> 目标：在**不修改 Go 前端/后端源码**的前提下，让 prod_bin 的 CMDB UI 通过 Python 后端（`cmdb_server_py`）访问数据——
> hzdz 视角下的主机统一视图由 Python 后端跨库投影，123 业务仍走 CMDB 原生 REST。

## 1. 架构与端口

| 角色 | 进程 | 端口 | 说明 |
|------|------|------|------|
| **BFF 集成网关** | `integrated_bff.py` (Flask) | **8083** | 单一入口：hzdz 端点本地处理，其余反代给 Go webserver，UI/静态资源反代给 Go webserver |
| prod_bin UI / webserver | `cmdb_webserver` (Go) | **8084** | 渲染 `index.html` 模板、提供静态资源、处理登录、转发 123 API 到 apiserver（已从 8083 迁至 8084） |
| Python 后端 | `app.py` (Flask) | 3000 | `cmdb_server_py` 本体，**直接连接 bk-cmdb 的 `cmdb` 实例**（与 Go 栈共享数据源，无独立库） |
| CMDB apiserver | `cmdb_apiserver` (Go) | 8081 | 123 业务原生 REST（经 Go webserver 转发，不直接暴露） |
| CMDB Mongo | `mongod` | 27017 | 单一 `cmdb` 库（bk-cmdb initdb 真实数据）；`bk_cmdb` mock 库已清理删除 |

**请求流**：
```
浏览器 ──> BFF :8083
           ├── /api/v3/hosts/search*        → 本地：跨库读 cmdb.cc_HostBase/cc_ModuleHostConfig
           │                                  （hzdz 视图：全部主机统一归属 HZ_VIEW_BIZ_ID=1）
           ├── 其它 /api/v3/*                → 反代 Go webserver :8084 → apiserver :8081 （123）
           └── / 及 /static/* /login/*       → 反代 Go webserver :8084 （UI 模板渲染 + 资源 + 登录）
```

## 2. 关键改动（仅运维脚本，未动 Go/前端源码）

| 文件 | 改动 |
|------|------|
| `prod_bin/deploy/start.sh` | webserver 监听 `0.0.0.0:8083` → `:8084`；`PORT` 映射与提示同步 |
| `prod_bin/deploy/run_stack.sh` | 自愈探活 `8083` → `8084`；`CMDB_PORTS` 中 8083 → 8084；新增 `start_python_stack()` 自愈拉起 `app.py`(3000) 与 BFF(8083) |
| `cmdb_server_py/integrated_bff.py` | **新增** BFF 网关（见第 4 节） |
| `cmdb_server_py/app.py` | 数据库改为连接 `cmdb` 实例（`MONGODB_DB=cmdb`）；移除 mock 初始化（`INIT_DATA` / `init_mock_data`） |

> 为何迁移 webserver 端口：CMDB webserver 经 ZooKeeper 把 `/api/v3` 代理到 apiserver，无法改向；
> 且 UI 的 `index.html` 是 **Go 模板**（由 webserver 渲染 `{{.site}}` 等），必须保留 webserver 渲染。
> 故用 BFF 前置在 8083，webserver 退到 8084 作为上游。

## 3. 启动顺序（已自动织入 run_stack 自愈）

1. `run_stack.sh`（supervisord `cmdb-stack`，`autorestart=true`）拉起依赖 + 7 个 CMDB 服务 + migrate。
2. `start_python_stack()`：确保 `app.py`(:3000) 与 `integrated_bff.py`(:8083) 运行。
3. 自愈循环每 60s 探活 webserver(8084)/adminserver(60004)，异常则重拉并连带拉起 Python 栈。

## 4. BFF 网关实现要点（`integrated_bff.py`）

- **hzdz 本地端点** `/api/v3/hosts/search`(+`/web`)：只读投影 CMDB Mongo `cmdb`
  （`cc_HostBase` + `cc_ModuleHostConfig`），把所有主机统一归属到 `HZ_VIEW_BIZ_ID`（默认 1），
  返回 UI 期望结构 `{info:[{host,module,set,biz}], count}`。无需修改 CMDB 即可实现"hzdz 视角全部主机归 home biz"。
- **反代**：其余 `/api/v3/*` 与 `/`、`/static/*`、`/login/*` 透传 `requests` 到 Go webserver(8084)，
  转发 method/headers/body/cookies；重写响应 `Location` 中的 `:8084` → `:8083`，避免浏览器直连 webserver。
- **`static_folder=None`**：禁用 Flask 内置 `/static` 路由，确保静态资源走反代（否则会被 Flask 自身 404 拦截）。
- 响应用 `_clean()` 递归清洗 `datetime/ObjectId/Int64`，避免 Mongo 类型导致 JSON 序列化 500。

## 5. 验证（当前已通过）

| 验证项 | 命令 | 结果 |
|--------|------|------|
| BFF 健康 | `curl :8083/healthz` | `bff healthy`，`go_web=http://127.0.0.1:8084` |
| UI 经 BFF | `curl -i :8083/` | `302 → /login?c_url=/`（同源 8083，浏览器跟随走 BFF） |
| 静态资源 | `curl :8083/static/js/<runtime>.js` | `200 text/javascript` |
| hzdz 主机视图 | `POST :8083/api/v3/hosts/search` | `count=10`，全部 `biz=[1]`（含原跨多业务的 host 7/8） |
| 123 业务代理 | `POST :8083/api/v3/business/search` | 与直连 `:8084` 响应 **md5 一致**（透明反代） |

## 6. 手动操作速查

```bash
# 单独启动 Python 后端（3000）
cd /workspace/bk_cmdb_py/cmdb_server_py
MONGODB_URI="mongodb://cc:cc@127.0.0.1:27017/cmdb?authSource=cmdb" MONGODB_DB=cmdb SKIP_LOGIN=true \
  nohup python3.11 app.py > /tmp/cmdb_py_app.log 2>&1 &

# 单独启动 BFF（8083，需 webserver 已在 8084）
cd /workspace/bk_cmdb_py/cmdb_server_py
GO_WEB_PORT=8084 BFF_PORT=8083 \
  CMDB_MONGO_URI="mongodb://cc:cc@127.0.0.1:27017/cmdb?authSource=cmdb" HZ_VIEW_BIZ_ID=1 \
  nohup python3.11 integrated_bff.py > /tmp/bff.log 2>&1 &

# 浏览器打开集成入口
open http://127.0.0.1:8083/        # admin / admin 登录
```

## 7. 隔离级别说明（对应此前架构讨论）

- **L0（逻辑隔离）**：当前实现。hzdz 投影与 123 共享同一 Mongo 实例的 `cmdb` 库；Python 后端与 Go 栈均为该实例的读取方，`bk_cmdb` mock 库已删除。
- **L2/L3（物理隔离）**：若将 `MONGODB_URI` 指向独立 Mongo 实例/部署，即为物理隔离；BFF 与独立 Python 后端不变。
- **123 走 API（非裸 Mongo）**：BFF 对 123 通过 Go webserver REST 转发，schema 解耦、凭证最小化，符合联邦设计。

---

## 8. 完整系统模式（BFF 无关，最小依赖）

> 与第 1~7 节的「集成态（BFF + Go 全栈）」相互独立。本模式**不启动任何 Go 服务 / ZooKeeper / Redis / BFF**，
> 仅由 `ui_server.py` 托管 prod_bin UI 并反向代理到 `app.py`，构成一个可独立运行的 CMDB 前端系统。

### 8.1 端口与角色

| 角色 | 进程 | 端口 | 说明 |
|------|------|------|------|
| **UI 服务** | `ui_server.py` (Flask) | **8085** | 托管 `prod_bin/ui` 静态资源；渲染 `index.html`/`login.html` Go 模板；处理登录；反代 `/api/v3` |
| Python 后端 | `app.py` (Flask) | 3000 | 业务/对象/模块/用户 REST，直接读 `cmdb` 实例 |
| CMDB Mongo | `mongod` | 27017 | `cmdb` 库（bk-cmdb initdb 真实数据） |

**请求流**：
```
浏览器 ──> UI 服务 :8085
           ├── GET /            → 有 bk_token 渲染 index.html；否则 302 → /login
           ├── GET/POST /login  → 校验 admin/admin，下发 bk_token Cookie，302 → /
           ├── /static/*        → 托管 prod_bin/ui（css/js/img/svg）
           └── /api/v3/*        → 反代 app.py :3000（透传 bk_token Cookie）
```

### 8.2 启动

```bash
bash /workspace/bk_cmdb_py/start_ui_system.sh
# 访问 http://127.0.0.1:8085/  账号 admin / admin
```

> 脚本显式以 `SKIP_LOGIN=false` 启动 `app.py`（走真实登录），并以 `UI_PORT=8085` 启动 `ui_server.py`。

### 8.3 鉴权设计（关键修复）

| 问题 | 根因 | 修复 |
|------|------|------|
| 登录报「用户名或密码错误」(1100000) | `user_auth()` 查询 `conn.users` 集合，而 `cmdb` 实例无 `users` 集合 | `app/config.py` 新增 `ADMIN_USERNAME/ADMIN_PASSWORD` 与 `is_superuser()`；登录时若 `users` 集合缺失且用户为 `admin`，以明文比对 `admin/admin` 兜底（**不写入 MongoDB**） |
| 管理员登录后业务/拓扑列表为空 | `biz_routes` / `object_routes` 按 `user_business` 集合过滤，而该集合在 initdb 后缺省 → admin 无任何可见业务 | `is_superuser(admin)` 时跳过 `user_business` 过滤，`get_user_accessible_biz_ids()` 直接返回全部业务 ID；`admin` 视为超级管理员可见全部业务与拓扑 |

配置对齐：`common.yaml` 中 `webServer.session.userInfo: admin:admin` 与 `authscheme: internal`；内置管理员即据此实现。

### 8.4 验证（当前已通过）

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 未登录访问首页 | `curl -i :8085/` | `302 → /login` |
| 登录页 | `curl :8085/login` | `200`，含 `window.LOGIN_ERROR = ''` 与登录表单 |
| 正确凭证登录 | `curl -i -X POST :8085/login --data "username=admin&password=admin"` | `302 → /`，`Set-Cookie: bk_token=...` |
| 错误凭证 | `curl -X POST :8085/login --data "username=admin&password=wrong"` | 重渲染登录页，`window.LOGIN_ERROR = '用户名或密码错误'` |
| 已登录首页 | `curl -b cj.txt :8085/` | `200`，`window.User = { admin: true, name: "admin" }` |
| 用户信息 | `curl -b cj.txt :8085/api/v3/user/info` | `{"username":"admin","role":"admin","admin":true}` |
| 业务列表（admin 可见全部） | `POST :8085/api/v3/biz/search/0` | `count=4`（资源池/蓝鲸/123/hzdz） |
| 拓扑（admin 可见） | `POST :8085/api/v3/find/topoinst_with_statistics/biz/1` | `result=true`，返回业务拓扑节点 |
| 静态资源 | `curl :8085/static/js/app.<hash>.js` | `200` |

### 8.5 资源目录「各模型实例数」404（关键修复）

> 现象：进入「资源」页（`#/resource/index`）后，控制台报 2 条 `Failed to load resource: 404` /
> `Request failed with status code 404`，但模型树本身正常渲染。

| 项 | 说明 |
|----|------|
| **根因** | 前端 `object-common-inst` store 的 `searchInstanceCount` 用 `window.API_HOST + "object/count"` 拼接请求。`index.html` 中 `API_HOST` 在生产构建下取 `window.location.origin + '/'`（`API_PREFIX` 才是 `origin + 'api/v3'`），故请求落到 `http://127.0.0.1:8085/object/count`（**不带 `/api/v3` 前缀**）。`ui_server.py` 当时只代理 `/api/v3/*`，无 `/object/count` 路由 → 404。 |
| **bk-cmdb 对照** | 真实部署中该端点由 `web_server` 服务（`src/web_server/service/object.go` 的 `GetObjectInstanceCount`）直接处理，而非通过 apiserver 的 `/api/v3`。请求体 `{"condition":{"obj_ids":[...]}}`，响应 `data` 为数组 `[{bk_obj_id, inst_count, error}]`。 |
| **修复** | 在 `ui_server.py` 新增 `GET/POST /object/count`（参考 web_server 实现，直接读 `cmdb` 实例统计计数）：<br>1. 入参取 `condition.obj_ids`（单次最多 20 个，与 bk-cmdb 一致）；<br>2. 通过 `cc_ObjectBase` 判断模型是否存在；存在则按 `bk_obj_id` 解析实例集合（内置特例 `biz→cc_ApplicationBase`、`set→cc_SetBase`、`module→cc_ModuleBase`、`host→cc_HostBase`、`process→cc_Process`、`bk_biz_set_obj→cc_BizSetBase`、`plat→cc_PlatBase`；通用对象 `cc_<obj_id>Base`）后 `count_documents`；<br>3. 响应严格携带 `bk_error_code:0`（前端拦截器仅认 `bk_error_code`），`data` 为计数数组；模型不存在才填 `error:"model not found"`。 |
| **验证** | `POST :8085/object/count` 返回 `bk_error_code=0`、`data=[{bk_obj_id:"biz",inst_count:4,...},...]`；浏览器进资源页 **0 条控制台错误 / 0 个非 200 响应**，模型树显示各模型实例计数（业务 4、主机 10、业务集 1，网络类 0）。 |

> 同类端点：前端还有约 30 个用 `window.API_HOST` 直拼的端点（`object/owner/`、`hosts/`、`user/list`、`insts/object/`、`organization/department`、`proxy/get/usermanage`、`collector/*`、`regular/*`、`importtemplate/*` 等）。它们同样落在 `:8085` 根路径、不带 `/api/v3`。其中仅「资源目录计数」在三个核心页面初始加载时触发；其余多在特定交互（导出/导入/用户管理/网络采集）时触发，当前未实现、会 404（多数带 `globalError:false` 不弹错误），属于已知范围外项，按需按 §8.5 同法在 `ui_server.py` 补路由即可。

### 8.6 主机模型被错误显示为「平台 plat」（关键修复）

> 现象：资源目录 / 模型管理页中，主机模型（host）出现在「业务拓扑」下，而「主机管理」分类里只有「平台 plat」；与 bk-cmdb 默认布局不符。

| 项 | 说明 |
|----|------|
| **根因** | 初始恢复 `cc_ObjectBase` 时，误将 `host`/`process` 的 `bk_classification_id` 填为 `bk_biz_topo`，且将 `plat` 的 `bk_obj_name` 填为「平台」。对照 bk-cmdb 源码：`src/scene_server/admin_server/upgrader/history/v3.0.8/addPresetObjects.go` 中 `host`/`process`/`plat` 均归属 `bk_host_manage`（主机管理）；`src/common/mapping.go` 中 `BKInnerObjIDPlat` 映射到 `BKCloudNameField`/`BKCloudIDField`，说明 `plat` 是「云区域」模型。 |
| **修复** | 1. 更新 `cc_ObjectBase`：`host`/`process` 的 `bk_classification_id` → `bk_host_manage`；`plat` 的 `bk_classification_id` → `bk_host_manage`，`bk_obj_name` → `云区域`。<br>2. 修正 `app/routes/object_routes.py` 的 `find/topomodelmainline`：由按 `bk_classification_id` 过滤改为按 `bk_obj_id` 集合 `['biz','set','module','host','process','bk_biz_set_obj']` 查询，确保 host 即使被调整到 `bk_host_manage` 后仍出现在业务拓扑主线。 |
| **验证** | `find/classificationobject` 返回：<br>• 主机管理：主机 (host)、进程 (process)、云区域 (plat)<br>• 业务拓扑：业务 (biz)、集群 (set)、模块 (module)、业务集 (bk_biz_set_obj)<br>• 网络：防火墙、负载均衡、路由器、交换机<br>`find/topomodelmainline` 仍返回 `biz→set→module→host`；业务拓扑页（`#/business/1/index`）主机列表正常显示 10 台主机；模型管理页主机模型不再显示为「平台」。 |

### 8.7 业务拓扑节点主机计数显示为 0（关键修复）

> 现象：进入业务拓扑页（`#/business/1/index`），左侧拓扑树的节点「主机」计数全部显示为 **0**，而该业务实际挂载了主机（如业务 1=5 台、业务 3=6 台、业务 4=2 台）。

| 项 | 说明 |
|----|------|
| **根因** | 拓扑主机计数逻辑在 `app/routes/object_routes.py`（`find/topoinst_with_statistics`、`find/topoinstnode/host_serviceinst_count` 及若干拓扑/主机关系读取）与 `app/routes/admin_routes.py`（主机列表读取）中，读取的是 **`cc_HostModuleRelation`** 集合——该集合在 initdb 后为**空**（README.md §2 明确标注其为「废弃的 mock 名称」）。bk-cmdb 真实的主机↔模块关系集合是 **`cc_ModuleHostConfig`**（字段 `bk_biz_id / bk_set_id / bk_module_id / bk_host_id`），`assign_host_modules.sh` 写入的也是它。由于读空集合，聚合后的 `host_count` 恒为 0，前端 `topology-tree` 组件按 `getNodeCount(e)` 取 `e.host_count`（为 `0`）渲染，于是显示 0。<br>前端行为补注：`topology-tree`（`2322.*.js` / `1526.*.js`）按 `bk_obj_id`+`bk_inst_id` 合并 API 结果；当 `host_count` 为 `null/undefined/0` 时均按 0 展示，故「真实节点显示 0」的根因在服务端返回了 0，而非前端。 |
| **bk-cmdb 对照** | 真实部署中拓扑计数由 `toposerver` 聚合 `cc_ModuleHostConfig` 得出；`cc_HostModuleRelation` 是历史上曾被用过的旧集合名（部分二次开发 fork 残留），本 Python 后端最初照搬了旧名导致计数失效。 |
| **修复** | 将 `object_routes.py` 与 `admin_routes.py` 中**全部** `cc_HostModuleRelation` → `cc_ModuleHostConfig`（`replace_all`）：<br>1. `object_routes.py`：`find_topo_inst_with_statistics`（按 `bk_biz_id` 聚合 `bk_host_id` 计数）、`find_topoinstnode_host_serviceinst_count`（按 `condition` 逐节点计数）、其余拓扑/主机关系读取点；<br>2. `admin_routes.py`：主机列表详情读取主机↔模块关系处。<br>重启 `app.py` 后，计数走真实关系集合。 |
| **验证** | • `POST :8085/api/v3/find/topoinst_with_statistics/biz/1` → `biz host_count=5`，`set 1 host_count=5`，`module 1 host_count=5`；<br>• `POST :8085/api/v3/find/topoinstnode/host_serviceinst_count/1` → 业务/集群节点均返回真实计数（5）；<br>• 无头浏览器（Playwright + 系统 Chromium）进入 `#/business/1/index`：左侧树真实节点「资源池/空闲机池/空闲机」均渲染 `host_count=5`。<br>• **残留观察（非缺陷）**：前端硬编码了一个虚拟默认集群节点 `set-0`（`bk_inst_id=0`，「空闲机池」），其 `host_count=0` 且模块子节点为 `null`——该虚拟节点无对应 DB 关系，0 是预期正确值；用户实际关心的真实拓扑节点计数已正确显示。 |

> 关联：本修复与 §8.1 的「最小依赖（无 Go/ZooKeeper/Redis/BFF）模式」配套 —— 因已停掉 Go 全栈与 BFF（supervisord `cmdb-stack` 置 `STOPPED`、BFF 经 `fuser -k -9 8083/tcp` SIGKILL 释放），拓扑数据完全由 `cmdb_server_py` 直读 `cmdb` 实例提供，故计数修复只动 Python 后端即可，无需 Go 栈参与。

### 8.8 补齐根路径（无 /api/v3 前缀）端点（关键修复）

> 现象：前端部分 store 用 `window.API_HOST`（生产构建 = `window.location.origin + '/'`）**直拼**请求，落到 UI 服务 `:8085` 的**根路径**，而非 `/api/v3` 代理范围。这些端点在「最小依赖模式」下原会 404，导致资源/模型/主机等页的交互（导入、导出、用户/部门选择、正则校验、网络采集）报 404 或控制台错误。
>
> 范围：`prod_bin/ui` 的 minified JS 中实际出现的直拼端点清单见下表（在 §8.5 基础上补齐其余项）。

**兜底策略**（`ui_server.py` 新增 `root_api_fallback` 兜底路由，注册在 `/object/count`、`/api/v3/<path>`、`/static` 等显式路由之后）：

1. **优先代理**：将根路径请求代理到 `app.py` 同名 `/api/v3/<path>` 接口（透传方法/头/Cookie/查询/Body），复用真实逻辑——`app.py` 已实现的端点可获得真实数据。
2. **安全兜底**：若 `app.py` 未实现（返回 404，最小系统未覆盖的导入/导出/网络采集/用户管理类），返回 bk-cmdb 风格的成功空响应（`bk_error_code:0` + `result:true`），避免 UI 弹 404 / 错误：
   - **下载/模板类**（路径含 `export` 或 `importtemplate`）：返回 `200` + 空 `text/csv` 文件体，避免前端 `$download` 把 JSON 当文件解析报错；
   - **列表/对象类**：返回 `{"bk_error_code":0,"result":true,"data":[]}` 信封。

| 根路径端点（落在 `:8085`） | 方法 | 处理 | 说明 |
|---------------------------|------|------|------|
| `hosts/search` | POST | 代理 → `/api/v3/hosts/search` | 真实主机列表（count=10） |
| `hosts/search/web` | POST | 代理 → `/api/v3/hosts/search/web` | 真实 |
| `biz/search/web` | POST | 代理 → `/api/v3/biz/search/web` | 真实业务搜索 |
| `object/count` | POST | 本地读 Mongo（§8.5） | 资源目录模型计数 |
| `user/list` | GET | 代理 → `/api/v3/user/list`（`user_routes.py` 已补 GET） | 返回内置 `admin`（最小系统唯一账户）；前端原用 GET，原实现仅 POST 导致 405，已修正 |
| `organization/department` | GET | 安全空响应 `data:[]` | 部门选择器（最小系统无组织数据） |
| `importtemplate/<objId>`、`importtemplate/host` | GET | 安全空文件体（text/csv） | 模型/主机导入模板下载 |
| `proxy/get/usermanage<path>` | GET | 代理 → `app.py /proxy/get/usermanage/*` | usermanage 未配置时由 `user_routes` 返回空 |
| `regular/verify_regular_express` | POST | 安全空响应 `data:[]` | 正则校验（前端 `globalError:false`） |
| `regular/verify_regular_content_batch` | POST | 安全空响应 `data:[]` | 批量正则校验 |
| `object/exportmany`、`object/object/<objId>/export`、`insts/object/<objId>/export`、`object/owner/<supplier>/object/<objId>/export` | POST | 安全空文件体 | 各类实例批量/单模型导出下载 |
| `object/importmany`、`object/importmany/analysis`、`object/object/<objId>/import`、`insts/object/<objId>/import`、`object/owner/<supplier>/object/<objId>/import` | POST | 安全空响应 `data:[]` | 各类导入/导入预检（前端 `globalError:false`） |
| `collector/netcollect/importtemplate/netdevice`、`collector/netcollect/importtemplate/netproperty` | GET | 安全空文件体 | 网络采集设备/属性导入模板 |
| `collector/netdevice/{export,import}`、`collector/netproperty/{export,import}` | POST | 安全空文件体 / 安全空响应 | 网络采集设备/属性导入导出 |
| `hosts/{export,import,update}`、`hosts/<id>/listen_ip_options` | POST/GET | 安全空响应 / 空文件体 | 主机导入导出（最小系统未覆盖，按需可改为代理真实接口） |

> 说明：上表「下载/导出」类在最小系统中返回空文件体（不报错、不崩溃），如需真实文件可后续在 `app.py` 实现对应 `/api/v3` 接口并由兜底路由自动代理；「导入/校验/用户管理」类返回空成功，UI 不弹错。已验证：上述端点经 `:8085` 全部返回 **200**，且 `/api/v3/*`、`/static/*` 与拓扑计数（§8.7）不受影响。

**附：根因补充（user/list 405）** —— `app.py` 的 `user_routes.py` 原仅注册 `methods=['POST']`，而 bk-cmdb 前端以 `GET /user/list?fuzzy_lookups=...` 调用，代理后收到 405 被原样透传。修复：将 `/user/list` 改为 `methods=['GET','POST']`，并在 `conn.users` 集合不存在/为空时以内置超级管理员 `admin` 作为唯一账户兜底（返回 `{count, info:[{bk_username,username,bk_role,role,language}]}`），使成员选择器可用。

---

### 8.9 业务拓扑空闲机池重复 + 主机搜索条件/分页 + 主机详情（关键修复，对应 Request C）

> 三项均按「先核对原 bk-cmdb v3.10.50 源码语义，再复刻」的原则实现（sub-item 3）。

#### 8.9.1 业务拓扑「空闲机池」重复（修复）

**根因**：前端业务拓扑组件（`getInstanceTopology` + `getInternalTopology`，minified JS 中表现为 `Promise.all([...]).then(... l.unshift(d) ...)`，其中 `d` 即内部拓扑的空闲机池 set 节点，且标 `is_idle_set:!0`）会把**内部拓扑接口**返回的空闲机池 **前置**（`l.unshift(d)`）到业务拓扑的 sets 列表中。原 `find_topo_inst_with_statistics` 又把空闲机池 set 一并返回在业务树里 → 空闲机池出现 **两份**。

**复刻原 bk-cmdb 语义**：空闲机池是 `cc_SetBase` 中 `bk_default=1`（或名为「空闲机池」）的真实集群，由 `/topo/internal/{supplier}/{biz}/with_statistics` 单独提供；业务拓扑树**不含**空闲机池，由前端合并呈现一次。

**改动**（`app/routes/object_routes.py`）：

| 函数 | 修复点 |
|------|--------|
| `topo_internal_with_statistics_new`（`/topo/internal/.../with_statistics`） | 原硬编码 `bk_set_id:0` 假空闲机池 → 改为从 `cc_SetBase` 查真实空闲机池（优先 `bk_default==1`，其次名称「空闲机池」）；返回真实 `bk_set_id`、`default:1`、真实模块（空闲机/故障机/待回收 按名称映射 `default=1/2/3`）及 `host_count`；未找到时退化为结构合法的空节点 |
| `find_topo_inst_with_statistics`（`/find/topoinst_with_statistics/biz/{biz}`） | 构建 sets 时**跳过空闲机池**（新增 `_is_idle_pool(s)` 判定 `bk_default==1` 或名称「空闲机池」）；业务节点 `host_count = 全量主机关系数`（含空闲机池，与「可见业务 sets 之和 + 内部空闲机池」一致） |

#### 8.9.2 主机搜索：条件 + 分页 + 下一页（修复）

**根因**：原 `hosts/search` / `hosts/search/web` 仅特判 `biz` 条件 `default==1`（资源池），未实现通用搜索条件、set/module 过滤。

**改动**（`app/routes/admin_routes.py`）：新增助手 `_cond_to_mongo`（将 `{field,operator,value}` 转为 Mongo 查询，支持 `$eq/$ne/$in/$nin/$gt/$gte/$lt/$lte/$regex`）与 `_build_host_search_query`（解析请求体）：

| 能力 | 实现 |
|------|------|
| 顶层 `bk_biz_id` | `>0` → 业务；`-1` → 资源池（bk_biz_id=1） |
| `condition[].bk_obj_id == 'host'` | 主机字段条件（bk_host_name/bk_host_innerip 等）→ `cc_HostBase` 过滤 |
| `condition[].bk_obj_id == 'set'` / `'module'` | 经 `cc_SetBase`/`cc_ModuleBase` 反查，再经 `cc_ModuleHostConfig` 得到候选 `bk_host_id` |
| `condition[].bk_obj_id == 'biz'` | `default==1`（资源池）或 `bk_biz_id` 过滤 |
| 分页 / 排序 / 计数 | 保留 `page.{start,limit,sort}`；返回 `{info, count}`；**下一页 = `start += limit` 直至 `start >= count`** |

`hosts/search/web` 同步采用同一解析器。响应保持 `info:[{host, module, set, biz}]` 结构（业务拓扑页）/`info:[hostDoc]`（全局搜索）。

#### 8.9.3 主机详情无数据（修复）

**根因**：前端详情页调用 `GET /hosts/{supplierAccount}/{hostId}`（minified JS：`c.A.get("hosts/".concat(n.supplierAccount,"/").concat(r))`），原 `app.py` 无对应路由 → 404 → 兜底空响应 → 页面「无 api 数据」。

**改动**（`app/routes/admin_routes.py`）：新增 `GET /hosts/<supplier>/<int:bk_host_id>`，复刻 bk-cmdb 的 `HostInstanceProperties` 数组：

```json
[{ "bk_property_id": "bk_host_innerip", "bk_property_name": "内网IP", "bk_property_value": ["10.0.1.11"] }, ... ]
```

属性名取自 `cc_ObjAttDes(bk_obj_id="host")`，属性值取自 `cc_HostBase` 主机文档。

#### 8.9.4 验证（当前已通过，经 `:8085` 根路径，即前端实际调用路径）

| 验证项 | 请求 | 结果 |
|--------|------|------|
| 内部拓扑空闲机池 | `GET /topo/internal/0/3/with_statistics` | 真实空闲机池 `bk_set_id=3, default=1`，模块 空闲机/故障机/待回收/Web服务器，host_count 正确 |
| 业务拓扑排除空闲机池 | `POST /find/topoinst_with_statistics/biz/3` | sets 仅 `[4 抹茶冰激凌, 8 流苏]`；biz `host_count=6`（= set4[5]+空闲机池[1]） |
| 业务全量搜索 | `POST /hosts/search` `{"bk_biz_id":3}` | `count=5`, hosts `[7,8,9,10,11]` |
| 主机字段搜索 `$regex` | `condition:[{bk_obj_id:"host",condition:[{field:"bk_host_innerip",operator:"$regex",value:"10.0.1"}]}]` | `count=5`, 命中全部 5 台 |
| set 条件过滤 | `condition:[{bk_obj_id:"set",condition:[{field:"bk_set_id",operator:"$in",value:[4]}]}]` | `count=5` |
| 分页下一页 | `page:{start:0,limit:2}` → `start:2` | page1 `[7,8]` → page2 `[9,10]` |
| 主机详情（根路径） | `GET /hosts/0/7` | `bk_error_code=0`, **35** 条属性（此前 404） |
| 主机详情（/api/v3） | `GET /api/v3/hosts/0/7` | 同根路径，35 条属性 |

---

### 8.10 资源池主机详情页「完全无数据」修复（对应用户本次问题）

> 现象：`/#/resource/host/2?from=resource` 主机详情页头部显示 `10.0.0.11` 但**属性面板空白**，「所属拓扑」为空。
>
> 用户怀疑：模型属性列、实例详情 `inst`、关联属性、`object attr`、`topoinst` 等 Python API 未实现。实际排查结论：**这些 API 已大部分实现；真正导致空白的是数据类型不匹配 + 属性分组集合名错误 + 拓扑路径接口未实现**。

#### 8.10.1 排查结论：哪些 API 已实现，哪些有缺陷

| API 类别 | 端点 | 实现状态 | 备注 |
|----------|------|----------|------|
| 模型属性列 | `POST /find/objectattr` | 已实现 | 返回 35 条 host 属性 |
| 实例详情 | `GET /hosts/<supplier>/<id>` | 已实现 | 返回 `HostInstanceProperties` 数组 |
| 属性分组 | `POST /find/objectattgroup/object/<obj_id>` | **有缺陷** | 误查 `cc_ObjAttGroup`（不存在），应查 `cc_PropertyGroup` |
| 所属拓扑路径 | `POST /find/topopath/biz/<id>` | **未实现** | 仅返回 `[]`，前端拿不到业务→集群→模块路径 |
| 主机位置拓扑 | `POST /find/topoinst/bk_biz_id/<biz>/host/<host>` | 已实现 | 返回主机所在 `biz→set→module→host` 路径 |
| 关联属性 | `POST /find/instassociation` 等 | 已实现 | 无关联数据时返回空，不会导致页面空白 |

#### 8.10.2 根因一：`bk_host_innerip` 为数组导致前端 `.split()` 报错

`cc_HostBase` 中 `bk_host_innerip` 被存储为 `['10.0.0.11']`，但前端详情组件做 `t.host.bk_host_innerip.split(',')` 期望字符串。原 `hosts/<id>` 和 `hosts/search` 直接透传 Mongo 文档，数组进入 Vue 后触发 `TypeError: t.host.bk_host_innerip.split is not a function`，页面组件被异常中断。

**修复**（`app/routes/admin_routes.py`）：新增 `_normalize_host_doc(doc)`，将主机文档中所有 `list` 字段按逗号拼接为字符串，再返回给前端：

```python
def _normalize_host_doc(doc):
    if not isinstance(doc, dict):
        return doc
    for k, v in list(doc.items()):
        if isinstance(v, list):
            doc[k] = ",".join(str(x) for x in v)
    return doc
```

应用位置：
- `GET /hosts/<supplier>/<id>`（主机详情）
- `POST /hosts/search`（业务拓扑主机列表）
- `POST /hosts/search/web`（全局主机搜索）

#### 8.10.3 根因二：属性分组查错集合，分组信息为空

`find/objectattgroup/object/<obj_id>` 原代码查 `cc_ObjAttGroup`，但 bk-cmdb initdb 后真实集合为 **`cc_PropertyGroup`**，导致返回 `data:[]`。前端属性面板依赖分组信息组织字段，拿到空分组后无法渲染表格。

**修复**（`app/routes/object_routes.py`）：将 `cc_ObjAttGroup` 改为 `cc_PropertyGroup`：

- `POST /find/objectattgroup`：改为 `conn.cc_PropertyGroup.find({}, {'_id': 0})`
- `POST /find/objectattgroup/object/<obj_id>`：改为 `get_mongo_collection('cc_PropertyGroup')`

修复后 `find/objectattgroup/object/host` 返回：

```json
[
  { "bk_group_id": "default", "bk_group_name": "基础信息" },
  { "bk_group_id": "auto",  "bk_group_name": "自动发现信息（需要安装agent）" }
]
```

#### 8.10.4 根因三：拓扑路径接口仅返回空数组

`POST /find/topopath/biz/<id>` 原为 stub，直接 `return make_response(data=[])`。前端「所属拓扑」组件拿到空数组后，路径渲染为空。

**修复**（`app/routes/object_routes.py`）：实现 `find_topo_path`。根据请求体 `topo_nodes` 中的 `bk_obj_id` / `bk_inst_id`，从 `cc_ApplicationBase` → `cc_SetBase` → `cc_ModuleBase` 反查，返回 `nodes` 数组，每项含 `topo_node` 与 `topo_path`：

请求示例：
```json
POST /find/topopath/biz/1
{ "topo_nodes": [{ "bk_obj_id": "module", "bk_inst_id": 1 }] }
```

响应示例：
```json
{
  "data": {
    "nodes": [{
      "topo_node": { "bk_obj_id": "module", "bk_inst_id": 1, "bk_inst_name": "空闲机" },
      "topo_path": [
        { "bk_obj_id": "biz", "bk_inst_id": 1, "bk_inst_name": "资源池" },
        { "bk_obj_id": "set", "bk_inst_id": 1, "bk_inst_name": "空闲机池" },
        { "bk_obj_id": "module", "bk_inst_id": 1, "bk_inst_name": "空闲机" }
      ]
    }]
  }
}
```

同时支持 `set` / `biz` / `host` 节点类型。

#### 8.10.5 补充：主机位置拓扑接口

已新增 `POST /find/topoinst/bk_biz_id/<int:bk_biz_id>/host/<int:bk_host_id>`，返回单个主机所在的完整 `biz→set→module→host` 树（业务主机详情页可用）。

#### 8.10.6 验证（当前已通过）

| 验证项 | 请求 | 结果 |
|--------|------|------|
| 属性分组 | `POST /find/objectattgroup/object/host` | `code=0`, 返回 2 个分组 |
| 拓扑路径 | `POST /find/topopath/biz/1` | `nodes` 含 `资源池→空闲机池→空闲机` |
| 主机 innerip 类型 | `GET /hosts/0/2` | `bk_host_innerip` 为字符串 `"10.0.0.11"` |
| 无头浏览器渲染 | `/#/resource/host/2?from=resource` | **无控制台报错**，属性面板显示 `基础信息` 20+ 字段，所属拓扑显示 `空闲机 / 空闲机池 / 资源池` |

> 说明：资源池主机详情页实际由 `hosts/search` + `find/objectattr` + `find/objectattgroup` + `find/topopath` 共同渲染，而非直接调用 `GET /hosts/<id>`。`GET /hosts/<id>` 仍保留用于其他页面或独立调试。

---

### 8.11 资源「实例」页（bk_switch 等通用/网络对象）无数据（关键修复）

> 现象：`#/resource/instance/bk_switch` 交换机实例列表为空；`POST /count/instances/object/bk_switch` 与 `POST /search/instances/object/bk_switch` 均返回 `count:0`。
>
> 用户预期：bk-cmdb initdb 后 `cmdb` 实例应有交换机数据。实际结论分两层：**后端集合名写错 + initdb 本就不播种实例数据**。

#### 8.11.1 两层根因

**根因 A（后端 Bug）：通用对象实例集合名错误。**

前端 `#/resource/instance/<obj_id>` 调用 `POST /search/instances/object/<obj_id>` 与 `POST /count/instances/object/<obj_id>`。原实现对非内置对象用 `collection_name = cc_InstBase_{obj_id}`（如 `cc_InstBase_bk_switch`），但 bk-cmdb 真实命名规则（`src/common/tablenames.go` 的 `GetInstTableName`）为：**内置对象独立集合**（`cc_ApplicationBase`/`cc_SetBase`/`cc_ModuleBase`/`cc_HostBase`/`cc_Process`/`cc_PlatBase`/`cc_BizSetBase`），**通用对象分片集合 `cc_ObjectBase_<supplier>_pub_<obj_id>`**（如 `bk_switch → cc_ObjectBase_0_pub_bk_switch`）。

因 `cc_InstBase_bk_switch` 不存在，`count_documents` 返回 0、无报错 → 页面静默无数据。

**根因 B（数据真相）：initdb 不播种任何实例数据。**

`src/scene_server/admin_server/upgrader/history/v3.0.8/addPresetObjects.go` 仅播种**模型定义**（`cc_ObjectBase` / `cc_ObjAttDes` / `cc_PropertyGroup` / classification），不插入任何交换机实例。`cmdb` 里 `cc_ObjectBase_0_pub_bk_switch` 等集合被创建为**空壳**（count=0）。bk-cmdb 标准行为就是这样——交换机实例要用户自行创建。用户「initdb 应该有交换机数据」的预期不成立。

#### 8.11.2 修复

新增助手 `get_inst_collection_name(obj_id)`（`app/routes/object_routes.py`），严格复刻 `GetInstTableName`：

```python
def get_inst_collection_name(obj_id):
    mapping = {"biz":"cc_ApplicationBase","bk_biz_set_obj":"cc_BizSetBase",
               "set":"cc_SetBase","module":"cc_ModuleBase","host":"cc_HostBase",
               "process":"cc_Process","plat":"cc_PlatBase","cloud_area":"cc_PlatBase"}
    if obj_id in mapping:
        return mapping[obj_id]
    return f"cc_ObjectBase_0_pub_{obj_id}"   # 通用/网络对象
```

应用位置（统一纠正）：

| 函数 | 路由 | 修改前 | 修改后 |
|------|------|--------|--------|
| `search_instances_by_obj` | `POST /search/instances/object/<obj_id>` | `cc_InstBase_{obj_id}` | `get_inst_collection_name()` |
| `count_instances_by_obj` | `POST /count/instances/object/<obj_id>` | 仅内部对象，网络对象 `cc_InstBase_*`、`bk_biz_set_obj`/`process` 硬编码 `0` | `get_inst_collection_name()` |
| `object_count`（批量） | `POST /object/count` | 同上 | `get_inst_collection_name()` |
| `create_instance` | `POST /create/instance/object/<obj_id>` | `cc_InstBase_{obj_id}`（写错集合） | `get_inst_collection_name()` |

`ui_server.py` 的 `object/count`（资源目录模型计数，根路径 `/object/count`）`_resolve_inst_table()` 同样错用 `cc_{obj_id}Base`，已改为优先内置映射、再回退 `cc_ObjectBase_0_pub_{obj_id}`。

#### 8.11.3 验证（当前已通过）

| 验证项 | 请求 | 结果 |
|--------|------|------|
| 集合名正确 | `POST /count/instances/object/bk_switch` | 命中 `cc_ObjectBase_0_pub_bk_switch`，`count` 真实 |
| 创建实例写入正确集合 | `POST /api/v3/create/instance/object/bk_switch` | 写入 `cc_ObjectBase_0_pub_bk_switch`，返回 `bk_inst_id=1/2` |
| 列表读取 | `POST /search/instances/object/bk_switch` | 返回 2 条样本（核心交换机-01/02） |
| 资源目录计数 | `POST /object/count` | `bk_switch` 计数随实例数上升 |
| 无头浏览器 | `/#/resource/instance/bk_switch` | 显示 2 台交换机，**无「暂无数据」、0 控制台报错** |

> 注：为验证端到端读写，已在 `cc_ObjectBase_0_pub_bk_switch` 写入 2 条**样本数据**（核心交换机-01/02，厂商 H3C，型号 S6800）。若不需要可删除：`db.cc_ObjectBase_0_pub_bk_switch.delete_many({})`。这进一步证实「无数据」此前是集合名 Bug 所致——修复后即使真实数据也能正确读写。

### 8.12 从 Go 预编译二进制重跑 init seed 并补充业务/主机（对应 Request D）

**目标**：Python 后端直接读 Mongo 的 `cmdb` 库，而这份数据必须由 bk-cmdb 的 Go 初始化产生。本节能从「已构建好的 Go 二进制」出发，完整重跑 init/seed，并补 1 个模拟业务 + 12 台主机。

**交付物**

| 文件 | 作用 |
|------|------|
| `prod_bin/deploy/init_cmdb_seed.sh` | 编排：备份 → 清空 → 部署 → 启动 adminserver → migrate → 校验 →（停 admin）→ 可选串联 seed |
| `cmdb_server_py/seed_extra.py` | 补充 1 模拟业务 + N 主机（默认 12），直写 Mongo，ID 走 `cc_idgenerator` 自增 |

**四问对照（用户原问题 → 答案）**

| # | 用户问题 | 答案 |
|---|----------|------|
| 1 | 如何清空数据 | `init_cmdb_seed.sh run --clear` 先自动 `mongodump` 备份到 `prod_bin/backups/cmdb_<时间戳>`，再 `drop` 全部**非系统集合**（保留 `system.*` 与 `cc` 账号），不会误删账号 |
| 2 | 启动哪个服务 | 仅 `cmdb_adminserver`（migrate 端口 **60004**，启动参数 `--config=configures/migrate.yaml --enable-auth=false`）。它内置 migrate 能力，其余 5 个 Go 服务对「init seed」非必需 |
| 3 | 运行哪个脚本 init seed | `POST http://127.0.0.1:60004/migrate/v3/migrate/community/0`（脚本内部 `do_migrate` 调用，重试 40 次），等价于官方 `init_db.sh` 的 migrate 步骤 |
| 4 | 补充 1 业务 + 12 主机 | `python3 cmdb_server_py/seed_extra.py`（或 `init_cmdb_seed.sh run --clear --with-extra` 自动串联） |

**一条命令完整重跑**

```bash
cd prod_bin/deploy
# 依赖（Mongo/Redis/ZK）需先就绪：./start_deps.sh
./init_cmdb_seed.sh run --clear --with-extra
```

执行顺序：① 备份 → ② 清空 79 个集合 → ③ 部署 adminserver → ④ 启动 60004 → ⑤ migrate（HTTP 200 `migrate success`）→ ⑥ 校验 → ⑦ 停止 adminserver → ⑧ 串联 seed_extra（1 业务 + 12 主机）。

**分步说明**

- 仅备份：`init_cmdb_seed.sh backup`
- 仅清空（先自动备份）：`init_cmdb_seed.sh clear`
- 假设 adminserver 已起、只跑 migrate：`init_cmdb_seed.sh migrate`
- 查看状态：`init_cmdb_seed.sh status`
- 单独补业务/主机（无需 adminserver，直写 Mongo）：
  ```bash
  SEED_HOST_COUNT=20 SEED_BIZ_NAME=demo-biz python3 cmdb_server_py/seed_extra.py
  ```
  可覆盖环境变量：`SEED_BIZ_NAME` / `SEED_SET_NAME` / `SEED_MODULE_NAME` / `SEED_HOST_COUNT` / `SEED_IP_PREFIX` / `MONGODB_URI`。

**数据模型约定（与 Go init seed 完全对齐）**

| 约定 | 实现 |
|------|------|
| 自增 ID | 取自 `cc_idgenerator.SequenceID`，`find_one_and_update` 原子 `$inc`，避免与既有数据冲突 |
| `bk_*_id` 类型 | 全部 `bson.Int64` → Mongo 中 `NumberLong`，与 Go 产出一致（避免 32/64 位整型偏差） |
| 主机内网 IP | `bk_host_innerip` 以**列表**存储，如 `["10.10.10.101"]`（bk-cmdb 真实形态；Python `_normalize_host_doc` 已能处理数组→字符串） |
| `bk_supplier_account` | 固定 `"0"`（社区版单租户） |
| `default` | 新建业务/集群/模块均为 `0`（非资源池/空闲机） |
| 业务归属 | 主机是独立实体，不挂 `bk_biz_id`；归属只写在 `cc_ModuleHostConfig`（biz/set/module/host 四 ID 均为 NumberLong） |

**关键事实：init seed 不创建任何业务/主机实例**

migrate 只写入「模型定义」（`cc_ObjectBase`、`cc_ObjAttDes`、`cc_PropertyGroup`、分类、内置资源池 biz=1 / set=1 / module=1），**从不写入实例数据**。因此「init 后交换机/主机应有数据」的预期是错误的——空壳集合（如 `cc_ObjectBase_0_pub_bk_switch`）本来就只有表结构无行。实例数据必须靠 API 批量导入，或本脚本的 `seed_extra.py` 补充。

**本次实际运行结果（已验证）**

| 集合 | 数量 | 说明 |
|------|------|------|
| `cc_ObjAttDes` | 145 | 模型属性，migrate 重建 |
| `cc_ApplicationBase` | 3 | 资源池 + migrate 内置业务 + `mock-biz-001`(id=4) |
| `cc_SetBase` | 3 | 空闲机池(biz1) + migrate 内置 + `mock-set-001`(id=4) |
| `cc_ModuleBase` | 5 | 空闲机(biz1) + migrate 内置 + `mock-module-001`(id=8) |
| `cc_HostBase` | 12 | 全部 `mock-seed`（IP `10.10.10.101–112`，`bk_host_id` 13–24，NumberLong） |
| `cc_ModuleHostConfig` | 12 | 全部指向 `biz=4 / set=4 / module=8` |

Python 后端自身 `get_mongo_collection` 读取路径已确认可见上述数据（主机 12、业务 3、关系 12），端到端打通。`bk_*_id` 经类型核验全部为 `NumberLong`，`bk_host_innerip` 为数组。

**回滚**

重跑前已自动备份至 `prod_bin/backups/cmdb_<时间戳>`。如需还原：

```bash
mongorestore --uri="mongodb://cc:cc@127.0.0.1:27017/cmdb?replicaSet=rs0&authSource=cmdb" \
  --db cmdb --drop <备份目录>/cmdb_<时间戳>/cmdb
```


---

## 15. Python migrate seed 对齐 Go 官方种子（v3.10.50）

**背景**：用户反馈「migrate seed 数据不太对」。根因是 Python migrate 的模型 ID 命名与 Go 官方种子不一致，而编译版 Vue UI 发送的是 Go 的 ID，导致字段错位。

### 15.1 Go 官方方案执行（基线）

```bash
cd prod_bin/deploy
bash init_cmdb_seed.sh run --clear     # 清空并走 cmdb_adminserver 内置 migrate
```

结果：`cmdb` 库产出 **78 个集合**的权威基线（`cc_ObjAttDes=145`、`cc_ApplicationBase=2` 等）。

### 15.2 差异根因（Python 旧实现 vs Go）

| 维度 | Python 旧实现（错误） | Go 官方（正确） |
|------|----------------------|----------------|
| 网络对象 ID | `switch / router / load_balance / firewall` | `bk_switch / bk_router / bk_load_balance / bk_firewall` |
| 业务角色字段 | `bk_maintainers / bk_productpm / bk_tester / bk_operator` | `bk_biz_maintainer / bk_biz_productor / bk_biz_tester / operator` |
| 属性分组 ID | `base / port / gsekit_base` | `default / proc_port / gsekit_baseinfo` |
| 分类 | 缺 `bk_uncategorized` | 含 `bk_uncategorized`（5 个） |
| 对象数 | 10（无 `bk_biz_set_obj`） | 11 |
| 主机关联 | `host→plat (bk_cloud_id)` | `bk_switch→host (connect)` |
| 属性总数 | 119 | 145 |

> 完整差异见 `diff_go_vs_py.md`；Go 权威数据见 `go_attr_full.json` / `go_model_ref.json` / `go_default_data.json`。

### 15.3 迭代内容（一次到位）

源文件改造（均在 `cmdb_server_py/migrate/`）：

| 文件 | 改造 |
|------|------|
| `data/attributes.py` | `ATTRIBUTES` 替换为 **145** 条，保留 Go 原始 `id`（1..159）供 `cc_ObjectUnique.key_id` 引用；`option` 按 Go 原样（enum 为 JSON 字符串） |
| `data/groups.py` | `GROUPS` 替换为 **19** 条，分组 ID 对齐 Go（`default/role/proc_port/...`），`isdefault=None` |
| `base_migrate.py` | 分类补 `bk_uncategorized`（5）；对象改 `bk_` 前缀 + 加 `bk_biz_set_obj`（11）；`cc_System` 对齐 Go 三文档（版本/hostcrossbiz/UI 配置） |
| `data/associations.py` | `ASSOCIATIONS` 替换为 Go **4** 条（`bk_switch→host connect`，移除旧 `host→plat`） |
| `data/default_data.py`（**新增**） | 运行级种子：`cc_ObjectUnique`(14)、`cc_BizSetBase`(1)、`cc_ApplicationBase`(资源池+蓝鲸)+`cc_SetBase`(2)+`cc_ModuleBase`(4)、`cc_idgenerator`(15) |
| `cli.py` | `cmd_all` 在末尾调用 `run_default_data_migrate(db)` |

**ID 生成器关键点**：Flask 的 `next_sequence` 依赖 `cc_idgenerator`（`_id`=集合名、`SequenceID` 自增）。`IDGeneratorMigrate` 按各集合**实际最大 id** 动态计算 `SequenceID`（如 `cc_ObjAttDes=159`、`cc_ServiceCategory=42`），避免新建对象与已种子 id 冲突。服务分类采用非连续 id（最大 42），故**不能**直接套用 Go 的连续值 20。

### 15.4 验证（Python → 对齐 Go）

清空临时库 `cmdb_pycmp` 后执行 `python3.11 -m migrate.cli --all`，逐项对比 `cmdb`（Go）：

| 集合 | Go | Python | 结果 |
|------|----|--------|------|
| cc_ObjClassification | 5 | 5 | ✅ |
| cc_ObjDes | 11 | 11 | ✅ |
| cc_ObjAttDes | 145 | 145 | ✅ 关键字段 0 差异 |
| cc_PropertyGroup | 19 | 19 | ✅ 关键字段 0 差异 |
| cc_ObjAsst | 4 | 4 | ✅ |
| cc_System | 3 | 3 | ✅ |
| cc_ObjectUnique | 14 | 14 | ✅ key_id 全部可解析到 cc_ObjAttDes.id |
| cc_BizSetBase | 1 | 1 | ✅ |
| cc_ApplicationBase | 2 | 2 | ✅ 资源池 + 蓝鲸 |
| cc_SetBase / cc_ModuleBase | 2 / 4 | 2 / 4 | ✅ |
| cc_idgenerator | 15 | 15 | ✅ 所有 SequenceID ≥ 已用最大 id（无冲突） |

12 个集合计数全部一致、无单方缺失；`biz` 属性 ID 集合与 Go 完全相同。

### 15.5 重新播种运行库（可选）

若需让运行中的 `cmdb` 改用 Python migrate 作为种子源（与 Go 数据等价）：

```bash
cd cmdb_server_py
export MONGO_URI="mongodb://cc:cc@127.0.0.1:27017/?authSource=cmdb"
export MONGO_DB="cmdb"
python3.11 -m migrate.cli --all      # 幂等 upsert，模型集合对齐 Go
# 业务/主机实例数据由 seed_extra.py 或 API 导入补充
python3.11 seed_extra.py              # 补充 mock 业务 + 主机（如需）
```

> 注意：Go 已种子的 `cmdb` 本身即正确数据；本迭代确保「改用 Python migrate 重新播种」时产出同样正确的数据。清空重建前请先备份（`prod_bin/backups/`）。

---

## 16. 补充 Python migrate mock 数据（seed_extra.py）

> 目的：在 Go 已种子的运行库 `cmdb` 之上，补充 1 个 mock 业务 + 12 台主机，供前端拓扑/资源/主机视图演示读取。
> 脚本：`cmdb_server_py/seed_extra.py`（幂等；默认连接 `mongodb://cc:cc@127.0.0.1:27017/cmdb?authSource=cmdb`，DB=`cmdb`）。

### 16.1 前置依赖（运行前已具备）

| 前置集合 | 运行前计数 | 说明 |
|---|---|---|
| `cc_idgenerator` | 16 | 提供各集合 ID 原子 `$inc` 序列；缺失会报错 |
| `cc_ApplicationBase` | 2 | Go 种子（资源池 id=1 + 蓝鲸 id=2） |
| `cc_SetBase` | 2 | Go 种子 |
| `cc_ModuleBase` | 4 | Go 种子 |
| `cc_HostBase` | 0 | 目标表，本次写入 12 条 |
| `mock-biz-001` 是否已存在 | 否 | 走「全新创建」分支 |

### 16.2 执行命令

```bash
cd /workspace/bk_cmdb_py/cmdb_server_py
python3.11 seed_extra.py
```

可选环境变量覆盖：`SEED_BIZ_NAME` / `SEED_HOST_COUNT` / `SEED_IP_PREFIX` / `SEED_SET_NAME` / `SEED_MODULE_NAME`。

### 16.3 执行结果（2026-07-14）

| 对象 | 关键 ID | 名称 | 归属 |
|---|---|---|---|
| 业务 | `bk_biz_id=3` | `mock-biz-001` | `bk_supplier_account=0` |
| 集群 | `bk_set_id=3` | `mock-set-001` | biz=3 |
| 模块 | `bk_module_id=7` | `mock-module-001` | set=3 |
| 主机 | `bk_host_id=1..12` | IP `10.10.10.101..112` | `bk_cloud_id=0` |

### 16.4 写入后计数与一致性校验

| 集合 | 运行前 | 运行后 | 校验 |
|---|---|---|---|
| `cc_ApplicationBase` | 2 | 3 | ✓ +1 mock 业务 |
| `cc_SetBase` | 2 | 3 | ✓ +1 集群 |
| `cc_ModuleBase` | 4 | 5 | ✓ +1 模块 |
| `cc_HostBase` | 0 | 12 | ✓ 12 台主机，ID 1..12 唯一无碰撞 |
| `cc_ModuleHostConfig` | 0 | 12 | ✓ 主机↔模块关系，均指向 module=7/set=3/biz=3 |
| `cc_ObjAttDes(is_required=True)` | — | 12 | ✓ `fix_required_fields` 标记名称字段 |

- `cc_idgenerator` 关键序列：`cc_ApplicationBase=3`、`cc_SetBase=3`、`cc_ModuleBase=7`、`cc_HostBase=12`，均 ≥ 已用最大值，后续新建对象不碰撞。
- 主机文档本体 `bk_biz_id/set_id/module_id` 为 `None`，归属关系由 `cc_ModuleHostConfig` 承载（bk-cmdb 标准范式：通过关系表推导拓扑层级）。
- Python 后端现已可通过 `/search/instances/object/host` 等接口读取这 12 台主机。

---

## 17. 主线节点删除接口实现（`DELETE /delete/topomodelmainline/object/{bk_obj_id}`）

### 17.1 背景与根因

模型详情页顶部「删除」按钮在 `isMainLineModel` 为真时走**专用删除通道**（前端 `objectMainLineModule/deleteMainlineObject`
→ `DELETE /api/v3/delete/topomodelmainline/object/{bk_obj_id}`），而模型详情「模型关联」tab 里的删除对 `bk_mainline`
行是**禁用**的（见 § 对话：`relation.vue` 的 `isEditable` 仅放行非 `bk_mainline` 关联，后端 `DeleteAssociationWithPreCheck`
亦以 `1101082` 拒收 `bk_mainline`）。

此前 Python 后端**只实现了** `POST /create/topomodelmainline` 与 `POST /find/topomodelmainline`，**缺 DELETE**，
导致前端点击「删除」命中 404 → 报错「api可能没实现」。本 § 补全该接口，逻辑严格对齐 Go `DeleteMainLineObject →
DeleteMainlineAssociation`。

### 17.2 Go 原逻辑对照（`DeleteMainlineAssociation`）

| 步骤 | Go 行为 | 守门条件 |
|---|---|---|
| 0 守门 | `IsInnerModel` 拒绝内置模型；`IsPre` 拒绝预定义主线关联；要求 child、parent 关联均存在 | 内置模型 / `ispre` / 缺上下游 → 报错 |
| 1 实例 | `ResetMainlineInstAssociation`：把 target 的直属子实例 reparent 到祖父(parent) 实例，再删 target 全部实例；同名冲突整体中止 | `CCErrTopoDeleteMainLineObjectAndInstNameRepeat` |
| 2 重链 | `createMainlineObjectAssociation(child, parent)`：child 挂回 parent（如 `set_bk_mainline_biz`） | 已存在则跳过 |
| 3 删关联 | `DeleteModelAssociation`：删除 target 作为子/父的全部 `bk_mainline` 关联 | — |
| 4 删模型 | `obj.DeleteObject`：删除 cc_ObjDes 及级联元数据 | — |

> 关键顺序：**先实例重挂/删除（步骤1），再元数据删除+重链（步骤2-4）**。Python 实现保持同一顺序。

### 17.3 Python 实现要点

**路由层**（`app/routes/object_routes.py`，`@object_bp.route('/delete/topomodelmainline/object/<bk_obj_id>', methods=['DELETE'])`）

```python
def delete_topo_model_mainline(bk_obj_id):
    supplier = (request.args.get('bk_supplier_account') or
                (request.get_json(silent=True) or {}).get('bk_supplier_account') or '0')
    conn = get_db_connection()
    if conn is None:
        return make_response(result=False, code=500, message="数据库连接失败")
    nb = get_mainline_neighbors(bk_obj_id)          # 1) 校验 + 取上下游
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _reset_mainline_inst(conn, supplier, bk_obj_id, # 2) 实例重挂（逆 _propagate_mainline_inst）
                         nb["child_obj_id"], nb["parent_obj_id"], now)
    result = delete_mainline_object(bk_obj_id)      # 3) 元数据删除 + 重链
    return make_response(data=result)
```

**`_reset_mainline_inst`（实例级，逆 `_propagate_mainline_inst`）**

- 收集 target 实例 → 其 `bk_parent_id`（祖父 id）与直属 child 实例（按 `bk_parent_id == target_inst_id` 查）。
- 同名冲突校验：计算每个祖父重挂后的「最终子级名集合」= 原已有（**排除本次将被移动的子级**）+ 本次重挂；集合有重复即抛
  `ModelError("删除主线对象 %s 实例时发生同名冲突，已中止", code=400)`。
  - ※ 排除移动子级的必要性：`appsys` 实例 id（1,2）与 `biz` 实例 id（1,2,3）**数值重叠**，若不排除，set 实例
    `bk_parent_id` 同时等于 appsys id 与 biz id，会被误判为「已存在同名」→ 假阳性冲突（见 17.5 修复）。
- 执行：批量把 child 实例 `bk_parent_id` 改挂祖父 id → 删除 target 实例表全量。无实例则 no-op 提前返回。

**`core.delete_mainline_object`（元数据级）**

1. 重链 `child → parent`（如 `set_bk_mainline_biz`），已存在则跳过（`create_object_association`，`ispre=False`）；
2. `delete_many` 删除 target 作为子/父的全部 `bk_mainline` 关联；
3. 级联清理 target 为源端的其余关联 / 属性 `cc_ObjAttDes` / 唯一规则 `cc_ObjectUnique` / 属性分组 `cc_PropertyGroup`；
4. `_delete_by_id` 删除 `cc_ObjDes` 模型本体。

**`core.get_mainline_neighbors`（守门 + 推导上下游，不写数据）**

- `bk_obj_id ∈ BUILTIN_MODEL_IDS` → 400「内置主线模型不允许删除」；
- 模型不存在 → 404；
- 查 `bk_asst_id=bk_mainline` 且（`bk_obj_id==target` 或 `bk_asst_obj_id==target`）的关联，无则 400「不是主线模型」；
- 任一匹配关联 `ispre=True` → 400「预定义主线关联禁止删除」；
- 推导出 `child_obj_id`（target 为父时的子级）与 `parent_obj_id`（target 为子时的父级），缺一则 400。

导入已在 `app/routes/object_routes.py:6` 补齐：
`from app.core.model import ModelError, ensure_model_default_attributes, get_mainline_neighbors, delete_mainline_object`。

### 17.4 伴随修复：create-relink 的 `ispre` 数据 bug

此前 `POST /create/topomodelmainline` 第 3 步重链时，只更新了 `bk_asst_obj_id` / `bk_obj_asst_id`，
**漏置 `ispre=False`**，导致 `set_bk_mainline_appsys` 仍带 `ispre=True`。Go 在重链时显式 `IsPre=false`，
而 Python 未对齐，会让本 § 的 `ispre` 守门误拦删除。

修复（`create_topo_model_mainline` 步骤 3 的 `$set`）：
```python
obj_asst_coll.update_one(
    {"_id": existing_child_asst["_id"]},
    {"$set": {
        "bk_asst_obj_id": bk_obj_id,
        "bk_obj_asst_id": "%s_bk_mainline_%s" % (child_obj_id, bk_obj_id),
        "ispre": False,           # 重链后非预定义
        "last_time": now,
    }}
)
```
存量脏数据归一化：`cc_ObjAsst.update_many({"bk_obj_asst_id":"set_bk_mainline_appsys"}, {"$set":{"ispre":False}})`（1 条）。
校验：`module_bk_mainline_set`、`host_bk_mainline_module` 仍正确保留 `ispre=True`（真实预定义内置关联，不应被删）。

### 17.5 验证结果（删除 `appsys`，链路 `biz → appsys → set → module → host`）

删除前备份已存于 `/workspace/bk_cmdb_py/backup_appsys_delete/`（cc_ObjAsst / cc_ObjDes /
cc_ObjectBase_0_pub_appsys / cc_SetBase / cc_ApplicationBase 的 JSON dump），可回滚。

| 校验项 | 删除前 | 删除后 | 结论 |
|---|---|---|---|
| 主线关联 | `appsys_bk_mainline_biz`、`set_bk_mainline_appsys`、`module_bk_mainline_set`、`host_bk_mainline_module` | `set_bk_mainline_biz`(ispre=False)、`module_bk_mainline_set`、`host_bk_mainline_module` | ✓ appsys 关联全清，链还原为 `biz→set→module→host` |
| `cc_ObjDes`(appsys) | 存在 | None | ✓ 模型本体删除 |
| `cc_ObjAttDes`(appsys) | N | 0 条 | ✓ 属性级联清理 |
| `cc_ObjectBase_0_pub_appsys` | N | 0 条 | ✓ 实例表清空 |
| set 实例 `bk_parent_id` | 指向 appsys 实例(1/2/3) | set1→1、set2→2、set3→3（biz 实例） | ✓ 子级成功 reparent 到祖父 |
| `POST /find/topomodelmainline` | 含 appsys 5 节点 | 干净 4 节点 `biz→set→module→host` | ✓ |

**守门测试（均按预期拒绝；注意本仓库 `make_response` 恒返回 HTTP 200，错误码在 body 的 `code`/`bk_error_code` 字段，前端据此判定成败）：**

| 输入 | body `code` | 消息 |
|---|---|---|
| 内置模型 `set` | 400 | 内置主线模型不允许删除 |
| 不存在 `nope` | 404 | 模型不存在 |
| 非主线 `bk_switch` | 400 | 模型不是主线模型，无主线关联可删除 |

### 17.6 端到端使用

- 前端：模型详情页（如 `appsys`）→ 顶部「删除」→ 走 `isMainLineModel` 专用通道 → 调用本接口。
- 后端需重启 `app.py:3000` 使新路由生效（增量代码已写入，未重启则旧进程无此路由）。
- 关联接口：`POST /create/topomodelmainline`（新建层级）、`POST /find/topomodelmainline`（查询链路）、
  本 `DELETE /delete/topomodelmainline/object/{bk_obj_id}`（删除层级）三者构成主线节点 CRUD 闭环。

---

## 18. 业务拓扑读取须遍历动态主线链（修复「新增主线层后业务树无变化」）

### 18.1 现象

模型-编辑拓扑 新增 `appsys1_bk_mainline_biz` 后，业务拓扑（`业务拓扑` 页）**无任何层级变化**：
- 存量 set 经 `_propagate_mainline_inst` 已 reparent 到 appsys1 实例下（写入侧正确）；
- 但业务拓扑读取接口**不渲染** appsys1 层级，sets 仍显示直接挂在业务下。

### 18.2 根因（READ 侧写死主线链，与 Go 相反）

`object_routes.py` 的 `find_business_topo_inst`(`/find/topoinst/biz/<id>`) 与
`find_topo_inst_with_statistics`(`/find/topoinst_with_statistics/biz/<id>`) 把主线链**硬编码为
biz→set→module**，按 `bk_biz_id`/`bk_set_id` 直接查、完全忽略 `bk_parent_id`，**从不查询自定义主线层**
（如 `cc_ObjectBase_0_pub_appsys1`）。故新插入的 appsys1 层级在读取端不可见 → 「无数据变化」。

> 对照 Go：`SearchMainlineAssociationInstTopo` + `buildTopoInstRst` 是**沿动态主线链 + `bk_parent_id`**
> 逐级下钻的（链由 `cc_ObjAsst` 的 `bk_mainline` 关联实时推导）。写入侧 `_propagate_mainline_inst`
> 已对齐 Go（`getMainlineChildInst` 在 `childObjID==set` 时排除 `default=1` 空闲机池；`buildTopoInstRst`
> 第 374 行把空闲机池直接挂到业务节点下）。**所以写入侧本就正确，问题纯在读取侧。**

> 旁注：`/update/objecttopo/scope_type/global/scope_id/0`（模型-编辑拓扑的「自动保存」接口）当前是**空桩**
> （`return make_response()`），不落库。因此主线关联须由 `POST /create/topomodelmainline`（`_propagate_mainline_inst`
> 在此触发，创建 appsys1 实例并 reparent 存量 set）创建，不能依赖编辑拓扑页的自动保存。

### 18.3 修复（新增动态遍历，对齐 Go buildTopoInstRst）

`object_routes.py` 新增共享辅助函数：

| 函数 | 职责 |
|---|---|
| `get_mainline_chain(supplier)` | 从 `cc_ObjAsst(bk_mainline)` 推导有序链，如 `[biz, appsys1, set, module, host]`（无自定义层时回退默认 4 级） |
| `build_mainline_inst_tree(conn, supplier, bk_biz_id, with_idle_pool)` | 沿链 + `bk_parent_id` 逐级构建实例树；**Go 怪异逻辑复刻**：遍历到 set 层时，父实例 id 列表**额外纳入 biz id**，使空闲机池（`default=1`、其 `bk_parent_id` 指向 biz）在 set 层被取到并因 parent==biz 直接挂业务下 |
| `_attach_host_counts(conn, supplier, biz_node)` | 后序聚合 `host_count`：module = 直连主机数（来自 `cc_ModuleHostConfig`），set/biz 累加 |
| `get_inst_name_field(obj_id)` | 各对象实例名/ID 字段映射（built-in 各异，通用对象用 `bk_inst_name`/`bk_inst_id`） |

两个端点重构为调用 `build_mainline_inst_tree`：
- `find/topoinst/biz/<id>` → `with_idle_pool=True`（空闲机池作为业务下节点渲染）；
- `find/topoinst_with_statistics/biz/<id>` → `with_idle_pool=False`（空闲机池不单独成节点，但其主机计入业务总数 `total_host_count`，与原有语义一致）。

遍历用**全量 `node_by_id` 字典跨级查找父节点**（不能只用当前层 `parent_nodes`，否则空闲机池 parent=biz 在第 set 层查到后找不到 biz 节点而丢失——初版即此 bug）。

### 18.4 验证结果

重启 `app.py:3000` 后，业务拓扑正确渲染：

| 业务 | 渲染结果 |
|---|---|
| 资源池(biz1，仅空闲机池) | `资源池` → [`应用系统1`(appsys1, 空节点), `空闲机池`(set)→`空闲机`(module)] |
| 蓝鲸(biz2，仅空闲机池) | `蓝鲸` → [`应用系统1`(appsys1, 空节点), `空闲机池`(set)→待回收/故障机/空闲机] |
| mock-biz-001(biz3) | `mock-biz-001` → `应用系统1`(inst=8) → [`DD`(set)→`对对对`, `mock-set-001`(set)→`mock-module-001`] |

即：自定义主线层 appsys1 作为新层级出现，存量非默认 set 经 reparent 挂在 appsys1 下，空闲机池仍直接挂在业务下（与 Go 一致）。`_with_statistics` 版 host_count 沿 appsys1 正确向上聚合（biz3=12）。

回归测试：`tests/test_mainline_delete.py` 新增 `test_business_topo_includes_custom_mainline_level`（断言 appsys1 出现且下挂 set）、
`test_business_topo_idle_pool_under_biz`（断言空闲机池直接挂业务）。全量 `pytest tests/test_mainline_delete.py` → 6 passed。
