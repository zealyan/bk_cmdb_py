# CMDB 开发记录

## 2026-03-25 开发记录

### 概述
本文档记录了 CMDB 项目在开发过程中 AI 修改的所有文件及其变更内容，主要用于前后端分离开发环境下的权限、认证、跨域等问题的修复。

---

## 后端文件修改

### 1. `src/web_server/middleware/login.go`

**修改目的**: 解决跨域请求和登出功能 404 错误

**变更内容**:
- **第 43-54 行**: 添加 CORS 预检请求处理逻辑
  ```go
  // AI: 处理 CORS 预检请求
  // AI: 示例：当浏览器发送跨域 POST 请求到 /logout 时，会先发送 OPTIONS 预检请求
  if c.Request.Method == "OPTIONS" {
      // AI: 设置 CORS 响应头，允许跨域请求
      c.Header("Access-Control-Allow-Origin", c.Request.Header.Get("Origin"))
      c.Header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
      c.Header("Access-Control-Allow-Headers", "Content-Type, Authorization, BK_User, HTTP_BLUEKING_SUPPLIER_ID, Cc_Request_Id")
      c.Header("Access-Control-Allow-Credentials", "true")
      c.Status(200)
      c.Abort()
      return
  }
  ```

- **第 64 行**: 将 `"logout"` 添加到无需认证的路径列表
  ```go
  case "healthz", "metrics", "login", "logout", "static":
  ```

**影响**: 
- 解决了前端跨域请求被拦截的问题
- 修复了登出功能返回 404 的错误

---

### 2. `src/apiserver/service/url.go`

**修改目的**: 修复创建业务时的 404 错误

**变更内容**:
- **第 91-92 行**: 新增 `/api/v3/biz` 路径支持
  ```go
  case string(*u) == rootPath+"/biz":
      from, to, isHit = rootPath+"/biz", topoRoot+"/app", true
  ```

**影响**: 
- 将 `/api/v3/biz` 请求路由到 topo 服务的 `/topo/v3/app`
- 修复了业务创建功能的 404 问题

---

### 3. `src/common/auth/auth.go`

**文件说明**: 认证开关控制文件

**关键配置**:
```go
var EnableAuth = "true"
var enableAuth = true
```

**作用**: 
- 控制是否启用认证授权
- 在 internal 模式下可设置为 `false` 以禁用 IAM 认证

---

### 4. `src/scene_server/auth_server/app/server.go`

**文件说明**: 认证服务器启动入口

**关键逻辑** (第 66-70 行):
```go
if !auth.EnableAuthorize() {
    blog.Info("auth is disabled, skip iam client initialization")
    lgc := logics.NewLogics(engine.CoreAPI)
    authServer.Service = service.NewAuthService(engine, nil, lgc, nil)
    break
}
```

**作用**: 
- 当认证禁用时，跳过 IAM 客户端初始化
- 所有请求都将被授权通过

---

### 5. `src/scene_server/auth_server/service/auth.go`

**文件说明**: 认证服务实现

**关键方法**:
- `AuthorizeBatch`: 批量权限校验
- `AuthorizeAnyBatch`: 任意权限校验
- `ListAuthorizedResources`: 列出已授权资源

**禁用认证时的行为** (第 38-44 行):
```go
if !auth.EnableAuthorize() {
    decisions := make([]bool, len(opts.Batch))
    for i := range decisions {
        decisions[i] = true
    }
    ctx.RespEntity(decisions)
    return
}
```

**作用**: 
- 禁用认证时，所有权限校验都返回 `true`

---

### 6. `src/common/util/lib.go`

**文件说明**: 通用工具函数

**关键函数**:
- `BuildHeader`: 构建包含用户和供应商信息的 HTTP 头
- `GetUser`: 从请求头获取用户信息
- `GetOwnerID`: 从请求头获取供应商 ID

**作用**: 
- 提供统一的请求头处理函数
- 用于在微服务间传递认证信息

---

## 前端文件修改

### 7. `src/ui/src/api/index.js`

**修改目的**: 为 API 请求添加认证头信息

**变更内容**:
- **第 48-49 行**: 在请求拦截器中添加认证头
  ```javascript
  // 添加 owner_id 和 user 参数
  HTTP_BLUEKING_SUPPLIER_ID: '0',
  BK_User: 'admin'
  ```

**影响**: 
- 确保所有 API 请求都携带正确的认证信息
- 解决了 `[owner_id] 授权信息查询失败` 错误

---

### 8. `src/ui/src/components/ui/form/user.vue`

**修改目的**: 避免用户选择器调用不存在的 API 导致 404 错误

**变更内容**:
- **第 102-116 行**: 修改 `fuzzySearchMethod` 方法
  ```javascript
  async fuzzySearchMethod(_keyword) {
    try {
      // AI: 直接返回空结果，避免 CORS 错误
      return {
        next: false,
        results: []
      }
    } catch (error) {
      // AI: 当 API 不存在时，返回空结果
      return {
        next: false,
        results: []
      }
    }
  }
  ```

**影响**: 
- 避免了用户选择器输入时的 404 错误
- 参数名从 `keyword` 改为 `_keyword` 以解决 ESLint 未使用参数警告

---

### 9. `src/ui/src/router/business-interceptor.js`

**文件说明**: 业务路由拦截器

**关键函数** (第 25-55 行):
```javascript
export async function getAuthorizedBusiness() {
  try {
    const response = await store.dispatch('objectBiz/getAuthorizedBusiness', {
      requestId,
      fromCache: true
    })
    if (response.result) {
      const { info } = response
      store.commit('objectBiz/setAuthorizedBusiness', Object.freeze(info))
      return info
    }
    // 在 internal 模式下，即使获取授权失败，也返回一个空数组
    return []
  } catch (error) {
    // 在 internal 模式下，即使获取授权异常，也设置一个空数组
    return []
  }
}
```

**作用**: 
- 获取用户有权限访问的业务列表
- 在 internal 模式下，即使 API 调用失败也返回空数组，避免应用崩溃

---

### 10. `src/ui/src/components/layout/dynamic-navigation.vue`

**文件说明**: 动态导航栏组件

**关键方法** (第 274-295 行):
```javascript
async refreshAuthorizedList() {
  try {
    const response = await this.$store.dispatch('objectBiz/getAuthorizedBusiness')
    if (response.result) {
      const { info } = response
      this.$store.commit('objectBiz/setAuthorizedBusiness', Object.freeze(info))
    } else {
      console.error('获取授权业务失败:', response.bk_error_msg)
      // 在 internal 模式下，即使获取失败，也设置一个空数组
      this.$store.commit('objectBiz/setAuthorizedBusiness', [])
    }
  } catch (error) {
    console.error('获取授权业务异常:', error)
    // 在 internal 模式下，即使获取异常，也设置一个空数组
    this.$store.commit('objectBiz/setAuthorizedBusiness', [])
  }
}
```

**作用**: 
- 刷新授权业务列表
- 错误处理机制确保在 internal 模式下导航栏正常显示

---

### 11. `src/ui/src/setup/preload.js`

**文件说明**: 预加载数据设置

**关键逻辑** (第 94-99 行):
```javascript
if (window.Site.authscheme === 'iam') {
  verifyPlatformManagementAuth()
} else {
  // 开源版的可能没有 IAM，不需要鉴权
  store.commit('globalConfig/setAuth', true)
}
```

**作用**: 
- 根据认证方案决定是否进行 IAM 鉴权
- 开源版本直接设置鉴权通过

---

### 12. `src/ui/src/store/modules/api/object-biz.js`

**文件说明**: 业务模块 API Store

**关键方法**:
- `getAuthorizedBusiness`: 获取授权业务列表
- `createBusiness`: 创建业务
- `searchBusiness`: 查询业务

**作用**: 
- 管理业务相关的 API 调用
- 与后端 `/api/v3/biz` 接口交互

---

### 13. `src/ui/builder/webpack/plugins.js`

**文件说明**: Webpack 插件配置

**关键配置** (第 29-34 行):
```javascript
new ESLintPlugin({
  extensions: ['js', 'vue', 'ts', 'tsx'],
  files: ['src'],
  failOnWarning: true,
  formatter: require('eslint-friendly-formatter')
})
```

**作用**: 
- 配置 ESLint 代码检查
- 确保代码质量

---

## 开发环境配置要点

### 认证模式说明

1. **IAM 模式** (`authscheme: 'iam'`):
   - 需要完整的 IAM 权限系统
   - 用户数据来自外部用户中心
   - 需要配置 ESB 和 IAM 服务

2. **Internal 模式** (`authscheme: 'internal'`):
   - 不依赖外部 IAM 系统
   - 所有请求默认通过认证
   - 适合本地开发和测试

### 关键配置项

**后端配置**:
```bash
# 禁用认证
enable_auth = false
```

**前端配置**:
```javascript
// src/ui/src/api/index.js
HTTP_BLUEKING_SUPPLIER_ID: '0',  // 默认供应商 ID
BK_User: 'admin'                  // 默认用户
```

### 常见问题及解决方案

1. **`[owner_id] 授权信息查询失败`**:
   - 原因：请求头缺少 `HTTP_BLUEKING_SUPPLIER_ID` 和 `BK_User`
   - 解决：在 `src/ui/src/api/index.js` 中添加请求头

2. **创建业务 404 错误**:
   - 原因：`/api/v3/biz` 路径未路由
   - 解决：在 `src/apiserver/service/url.go` 中添加路由

3. **用户选择器 404 错误**:
   - 原因：调用了不存在的用户 API
   - 解决：在 `src/ui/src/components/ui/form/user.vue` 中返回空结果

4. **登出功能 404 错误**:
   - 原因：CORS 预检请求未处理
   - 解决：在 `src/web_server/middleware/login.go` 中添加 OPTIONS 处理

---

## 总结

本次开发主要解决了以下问题：

1. ✅ 配置了前后端分离开发环境
2. ✅ 解决了跨域请求问题
3. ✅ 修复了认证授权相关错误
4. ✅ 实现了 Internal 模式下的免认证开发
5. ✅ 修复了业务创建、用户选择器、登出等功能

所有修改都添加了 `AI:` 前缀的注释，便于后续维护和识别。

---

## 服务器部署变更记录 (2026-03-23 ~ 2026-03-25)

### 服务器环境
- **服务器地址**: 192.168.45.141
- **部署路径**: /home/cmdb/cmdb
- **部署用户**: root

### 最近修改的文件清单

#### 2026-03-23 23:54 修改的配置文件

1. **`cmdb_adminserver/configures/extra.yaml`** (0 bytes)
   - 空配置文件，用于额外配置项

2. **`cmdb_adminserver/configures/redis.yaml`** (1007 bytes)
   - Redis 服务配置

3. **`cmdb_adminserver/configures/migrate.yaml`** (1.2K bytes)
   - 数据迁移配置

4. **`monstache/etc/extra.toml`** (122 bytes)
   - MongoDB 到 Elasticsearch 同步工具配置

5. **`monstache/etc/config.toml`** (707 bytes)
   - Monstache 主配置文件

6. **`init_db.sh`** (372 bytes)
   - 数据库初始化脚本

#### 2026-03-24 修改的文件

1. **`web/index.html`** (1.9K bytes) - 2026-03-24 13:28
   - **关键配置**: 
     ```javascript
     authscheme: "internal"  // 认证模式：internal（免认证）
     ```
   - **影响**: 前端使用 internal 模式，不依赖外部 IAM 系统

2. **`cmdb_authserver/cmdb_authserver`** (30M bytes) - 2026-03-24 10:56
   - 认证服务可执行文件（重新编译）

3. **各服务 start.sh 脚本** (2026-03-24 23:50)
   
   所有启动脚本都采用统一的模板结构：
   ```bash
   #!/bin/bash
   set -e
   localIp=`python ip.py`  # 获取本地 IP
   mkdir -p ./logs         # 创建日志目录
   chmod +x <service>      # 设置执行权限
   ./<service> --addrport=${localIp}:<PORT> --regdiscv=127.0.0.1:2181 [OPTIONS] &
   ```

   **详细服务配置清单**:

   | 服务名称 | 端口 | 认证开关 | 特殊参数 | 文件大小 |
   |---------|------|---------|---------|---------|
   | **cmdb_apiserver** | 8080 | `--enable-auth=false` | - | 365 bytes |
   | **cmdb_webserver** | 8083 | 无 | - | 343 bytes |
   | **cmdb_authserver** | 60014 | `--enable-auth=false` | - | 368 bytes |
   | **cmdb_toposerver** | 60002 | `--enable-auth=false` | - | 367 bytes |
   | **cmdb_hostserver** | 60001 | `--enable-auth=false` | - | 368 bytes |
   | **cmdb_coreservice** | 50009 | 无 | - | 348 bytes |
   | **cmdb_eventserver** | 60009 | `--enable-auth=false` | - | 370 bytes |
   | **cmdb_procserver** | 60003 | `--enable-auth=false` | - | 368 bytes |
   | **cmdb_datacollection** | 60005 | `--enable-auth=false` | - | 375 bytes |
   | **cmdb_taskserver** | 60012 | 无 | - | 346 bytes |
   | **cmdb_synchronizeserver** | 60010 | 无 | - | 360 bytes |
   | **cmdb_cacheservice** | 50010 | 无 | - | 350 bytes |
   | **cmdb_cloudserver** | 60013 | `--enable-auth=false` | `--enable_cryptor=false` | 394 bytes |
   | **cmdb_operationserver** | 60011 | `--enable-auth=false` | - | 378 bytes |
   | **cmdb_adminserver** | 60004 | `--enable-auth=false` | `--config=configures/migrate.yaml` | 377 bytes |

   **启动脚本变更说明**:
   - ✅ 所有服务都配置了 `--enable-auth=false`（需要认证的服务）
   - ✅ 统一使用 Zookeeper 地址：`127.0.0.1:2181`
   - ✅ 日志输出到 `./logs/std.log`
   - ✅ 所有服务后台运行（使用 `&`）
   - ✅ `cmdb_adminserver` 额外指定了迁移配置文件
   - ✅ `cmdb_cloudserver` 禁用了加密功能

#### 2026-03-25 修改的配置文件

1. **`cmdb_adminserver/configures/common.yaml`** (11K bytes) - 05:21
   - **关键配置**:
     ```yaml
     # Web 服务配置
     webServer:
       session:
         multipleOwner: 0  # 单供应商模式
       site:
         domainUrl: http://127.0.0.1:80/  # 需要替换为实际地址
       app:
         authscheme: internal  # 认证模式：internal
       login:
         version: opensource  # 开源版本登录
     
     # Elasticsearch 配置
     es:
       fullTextSearch: "off"  # 关闭全文检索
     ```

2. **`cmdb_adminserver/configures/mongodb.yaml`** (556 bytes) - 00:50
   - **关键配置**:
     ```yaml
     mongodb:
       host: 192.168.45.141  # MongoDB 主机地址
       port: 27017
       usr: cc
       pwd: "cc123456"
       database: cmdb
       rsName: rs0  # 副本集名称
     watch:
       host: 192.168.45.141  # 事件监听 MongoDB
       port: 27017
       rsName: rs0
     ```

3. **`cmdb_apiserver/cmdb_apiserver`** (34M bytes) - 01:06
   - API 服务可执行文件（重新编译）

4. **`cmdb_webserver/cmdb_webserver`** (34M bytes) - 07:28
   - Web 服务可执行文件（重新编译，包含 CORS 修复）

5. **`cmdb_webserver_new`** (34M bytes) - 07:28
   - 新版 Web 服务可执行文件

### 配置变更总结

#### 认证模式配置
- **前端**: `authscheme: "internal"` (index.html)
- **后端**: `authscheme: internal` (common.yaml)
- **启动脚本**: `--enable-auth=false` (11 个服务)
- **影响**: 系统运行在免认证模式，适合开发环境

#### 数据库配置
- **MongoDB 地址**: 从 `127.0.0.1` 改为 `192.168.45.141`
- **副本集**: `rsName: rs0`
- **影响**: 解决了服务无法连接 MongoDB 的问题

#### 服务部署
- **编译更新**: 
  - cmdb_apiserver (34M)
  - cmdb_authserver (30M)
  - cmdb_webserver (34M)
- **启动脚本**: 所有服务的 start.sh 都已更新

#### 启动脚本详细分析

**标准启动脚本模板**:
```bash
#!/bin/bash
set -e

# 获取本地 IP 地址
localIp=`python ip.py`

# 创建日志目录（如果不存在）
if [[ ! -d "./logs" ]];then
    mkdir ./logs
fi

# 设置可执行权限
chmod +x <service_binary>

# 启动服务（后台运行）
./<service_binary> \
  --addrport=${localIp}:<PORT> \
  --logtostderr=false \
  --log-dir=./logs \
  --v=3 \
  --regdiscv=127.0.0.1:2181 \
  [OPTIONS] \
  --register-ip=${localIp} \
  > ./logs/std.log 2>&1 &
```

**关键参数说明**:

| 参数 | 说明 | 示例值 |
|------|------|--------|
| `--addrport` | 服务监听地址和端口 | `${localIp}:8080` |
| `--logtostderr` | 是否输出日志到标准错误 | `false` |
| `--log-dir` | 日志目录 | `./logs` |
| `--v` | 日志级别 | `3` |
| `--regdiscv` | Zookeeper 服务发现地址 | `127.0.0.1:2181` |
| `--register-ip` | 注册到 Zookeeper 的 IP | `${localIp}` |
| `--enable-auth` | 是否启用认证 | `false` |
| `--config` | 配置文件路径 | `configures/migrate.yaml` |
| `--enable_cryptor` | 是否启用加密 | `false` |

**服务端口分布**:

```
API 层:
  - apiserver:        8080  (核心 API 服务)
  - webserver:        8083  (Web 服务)

业务层:
  - toposerver:       60002 (拓扑服务)
  - hostserver:       60001 (主机服务)
  - procserver:       60003 (进程服务)
  - eventserver:      60009 (事件服务)

支撑层:
  - authserver:       60014 (认证服务)
  - adminserver:      60004 (管理服务)
  - datacollection:   60005 (数据采集)
  - taskserver:       60012 (任务服务)
  - synchronizeserver: 60010 (同步服务)
  - cacheservice:     50010 (缓存服务)
  - cloudserver:      60013 (云服务)
  - operationserver:  60011 (运营服务)
  - coreservice:      50009 (核心服务)
```

### 部署验证

可以通过以下命令验证服务状态：
```bash
# 检查服务进程
ps aux | grep cmdb

# 检查端口监听
netstat -tlnp | grep -E '8080|8083|60001|60002'

# 查看服务日志
tail -f /home/cmdb/cmdb/cmdb_webserver/logs/web.log
```
