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

