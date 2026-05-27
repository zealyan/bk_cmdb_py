# CMDB 初始化操作记录

## 中间件初始化

当复用原中间件时，无需操作，直接去执行init.py:

完成zookeeper和redis部署。

完成Mongodb集群搭建，初始化创建集群和库、用户

## init.py 操作记录

```Shell
# 解压cmdb.tar.gz
cd /home/cmdb;mkdir cmdb
```

```Shell
python init.py  \
  --discovery          192.168.45.141:2181 \
  --database           cmdb \
  --redis_ip           192.168.45.141 \
  --redis_port         6379 \
  --redis_pass         redis \
  --mongo_ip           192.168.45.141 \
  --mongo_port         27017 \
  --mongo_user         cc \
  --mongo_pass         cc123456 \
  --blueking_cmdb_url  http://192.168.45.141:8083 \
  --blueking_paas_url  http://paas.domain.com \
  --listen_port        8083 \
  --auth_scheme        internal \
  --auth_enabled       false \
  --auth_address       https://iam.domain.com/ \
  --auth_app_code      bk_cmdb \
  --auth_app_secret    xxxxxxx \
  --full_text_search   off \
  --log_level          3 \
  --register_ip        192.168.45.141 \
  --user_info admin:admin,tom:tom123
```

init.py 参数详解：

```Shell
python init.py
usage:
--discovery           <discovery>           the ZooKeeper server address, eg:127.0.0.1:2181
--database           <database>             the database name, default cmdb
--redis_ip           <redis_ip>             the redis ip, eg:127.0.0.1
--redis_port         <redis_port>           the redis port, default:6379
--redis_pass         <redis_pass>           the redis user password
--mongo_ip           <mongo_ip>             the mongo ip ,eg:127.0.0.1
--mongo_port         <mongo_port>           the mongo port, eg:27017
--mongo_user         <mongo_user>           the mongo user name, default:cc
--mongo_pass         <mongo_pass>           the mongo password
--blueking_cmdb_url  <blueking_cmdb_url>    the cmdb site url, eg: http://127.0.0.1:8088 or http://bk.tencent.com
--blueking_paas_url  <blueking_paas_url>    the blueking paas url, eg: http://127.0.0.1:8088 or http://bk.tencent.com
--listen_port        <listen_port>          the cmdb_webserver listen port, should be the port as same as -c <cc_url> specified, default:8083
--full_text_search   <full_text_search>     full text search function, off or on, default off
--es_url             <es_url>               the elasticsearch listen url
--user_info          <user_info>            the system user info, user and password are combined by semicolon, multiple users are separated by comma. eg: user1:password1,user2:password2
```

**注:init.py 执行成功后会自动生成cmdb各服务进程所需要的配置。**

## 启动服务后init_db.sh

```Shell

cd /home/cmdb/cmdb
./start.sh
bash ./init_db.sh
# {"result":true,"bk_error_code":0,"bk_error_msg":"success","data":"migrate success"}
```

# CMDB 开发环境前后端分离配置指南

## 一、环境概述

### 1.1 架构说明

- **前端开发环境**: Windows 11 本地运行，使用 Vue.js + Webpack Dev Server
- **后端运行环境**: SSH 服务器 (192.168.45.141) 运行所有 CMDB 微服务
- **开发模式**: 前后端分离，通过 Webpack 代理实现跨域访问

### 1.2 服务端口

- 前端开发服务器：<http://localhost:9090>
- 后端 WebServer: <http://192.168.45.141:8083>
- 后端 APIServer: <http://192.168.45.141:8080>

## 二、前端开发环境配置

### 2.1 核心配置文件

#### 2.1.1 index.dev.html (入口 HTML)

位置：`e:\workspace_webstorm\bk-cmdb-v3.10.41\bk-cmdb-release-v3.10.41\src\ui\index.dev.html`

关键配置：

```javascript
// AI: 配置 API 代理地址
window.API_HOST = "http://localhost:9090/proxy/"
window.API_PREFIX = API_HOST + 'api/' + Site.version

// AI: 站点配置
window.Site = {
    url: "http://localhost:9090/proxy/",
    version: "v3",
    authscheme: "internal"
}

// AI: 用户配置
window.User = {
    admin: 1,
    name: "admin"
}
```

#### 2.1.2 builder/config/index.js (Webpack 配置)

位置：`e:\workspace_webstorm\bk-cmdb-v3.10.41\bk-cmdb-release-v3.10.41\src\ui\builder\config\index.js`

**代理配置说明**：

```javascript
proxyTable: {
  // AI: 用户相关请求代理到 WebServer (8083)
  '/proxy/user': {
    target: 'http://192.168.45.141:8083/',
    pathRewrite: { '^/proxy/user': '/user' }
  },
  
  // AI: 登出请求代理到 WebServer (8083)
  '/proxy/logout': {
    target: 'http://192.168.45.141:8083/',
    pathRewrite: { '^/proxy/logout': '/logout' }
  },
  
  // AI: 登录请求代理到 WebServer (8083)
  '/proxy/login': {
    target: 'http://192.168.45.141:8083/',
    pathRewrite: { '^/proxy/login': '/login' }
  },
  
  // AI: 其他 API 请求代理到 APIServer (8080)
  '/proxy': {
    target: 'http://192.168.45.141:8080/',
    pathRewrite: { '^/proxy': '' }
  }
}
```

**CORS 处理函数**：

```javascript
// AI: 处理 OPTIONS 预检请求
onProxyReq(proxyReq, req, res) {
  if (req.method === 'OPTIONS') {
    res.setHeader('Access-Control-Allow-Origin', req.headers.origin || '*')
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, BK_User, HTTP_BLUEKING_SUPPLIER_ID, Cc_Request_Id')
    res.setHeader('Access-Control-Allow-Credentials', 'true')
    res.writeHead(200)
    res.end()
    proxyReq.abort() // 中止请求，不再转发到后端
  }
}

// AI: 为所有代理响应添加 CORS 头
onProxyRes(proxyRes, req, res) {
  res.setHeader('Access-Control-Allow-Origin', req.headers.origin || '*')
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, BK_User, HTTP_BLUEKING_SUPPLIER_ID, Cc_Request_Id')
  res.setHeader('Access-Control-Allow-Credentials', 'true')
}
```

### 2.2 启动前端开发服务器

```bash
cd e:\workspace_webstorm\bk-cmdb-v3.10.41\bk-cmdb-release-v3.10.41\src\ui
npm run dev
```

访问地址：<http://localhost:9090>

## 三、后端服务配置

### 3.1 编译带 CORS 修复的 WebServer

#### 3.1.1 修改 login.go 添加 CORS 支持

位置：`e:\workspace_webstorm\bk-cmdb-v3.10.41\bk-cmdb-release-v3.10.41\src\web_server\middleware\login.go`

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

#### 3.1.2 Windows 交叉编译 Linux 版本

```bash
# AI: 设置 Go 代理加速下载
go env -w GOPROXY=https://goproxy.cn,direct

# AI: 交叉编译 Linux x86_64 版本
$env:GOOS = "linux"
$env:GOARCH = "amd64"
F:\go1.17.windows-amd64\go\bin\go.exe build -o cmdb_webserver.linux
```

#### 3.1.3 上传并替换服务器二进制文件

```bash
# AI: 上传到服务器
# 使用 SFTP 上传 cmdb_webserver.linux 到 /home/cmdb/cmdb/cmdb_webserver/cmdb_webserver

# AI: 设置执行权限
chmod +x /home/cmdb/cmdb/cmdb_webserver/cmdb_webserver

# AI: 重启服务
cd /home/cmdb/cmdb
./stop.sh
./start.sh
```

### 3.2 启动所有 CMDB 服务

在 SSH 服务器上执行：

```bash
cd /home/cmdb/cmdb
./start.sh
```

验证服务状态：

```bash
ps aux | grep cmdb
```

应该看到以下服务：

- cmdb\_adminserver (60004)
- cmdb\_apiserver (8080)
- cmdb\_authserver (60014)
- cmdb\_cacheservice (50010)
- cmdb\_cloudserver (60013)
- cmdb\_coreservice (50009)
- cmdb\_datacollection (60005)
- cmdb\_eventserver (60009)
- cmdb\_hostserver (60001)
- cmdb\_operationserver (60011)
- cmdb\_procserver (60003)
- cmdb\_taskserver (60012)
- cmdb\_toposerver (60002)
- cmdb\_webserver (8083)

## 四、跨域问题解决方案

### 4.1 跨域问题原因

浏览器同源策略限制，当前端 (localhost:9090) 访问后端 (192.168.45.141:8083) 时：

1. 发送 POST 等跨域请求前，浏览器会先发送 OPTIONS 预检请求
2. 后端需要正确响应 OPTIONS 请求并返回 CORS 响应头
3. 浏览器验证通过后才发送实际请求

### 4.2 双层 CORS 处理机制

#### 4.2.1 前端代理层处理 (Webpack Dev Server)

- 在 `builder/config/index.js` 中配置 `onProxyReq` 拦截 OPTIONS 请求
- 直接返回 200 状态码和 CORS 响应头，不再转发到后端
- 优点：响应快，减少后端压力

#### 4.2.2 后端中间件层处理 (WebServer)

- 在 `web_server/middleware/login.go` 的 `ValidLogin` 中间件中处理
- 对所有 OPTIONS 请求返回 CORS 响应头
- 优点：生产环境也能正常工作

### 4.3 必需的 CORS 响应头

```
Access-Control-Allow-Origin: http://localhost:9090
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization, BK_User, HTTP_BLUEKING_SUPPLIER_ID, Cc_Request_Id
Access-Control-Allow-Credentials: true
```

## 五、开发调试流程

### 5.1 启动顺序

1. 确保 SSH 服务器上的后端服务正常运行
2. 启动本地前端开发服务器 (`npm run dev`)
3. 访问 <http://localhost:9090>

### 5.2 调试技巧

- 使用 Chrome DevTools 查看 Network 面板
- 检查 Console 中的 CORS 错误
- 使用 F12 查看请求头和响应头

### 5.3 常见问题排查

#### 问题 1: 504 Gateway Timeout

**原因**: 后端服务未启动
**解决**: 检查 SSH 服务器上的服务状态

#### 问题 2: CORS 错误

**原因**: OPTIONS 请求未正确处理
**解决**: 检查前端代理配置和后端中间件

#### 问题 3: 404 Not Found

**原因**: 代理路径配置错误
**解决**: 检查 `proxyTable` 中的 pathRewrite 配置

## 六、生产环境部署注意事项

### 6.1 前端构建

```bash
npm run build
```

### 6.2 后端配置

- 生产环境使用 Nginx 反向代理
- 前端和后端部署在同一域名下，避免跨域问题
- 或者配置 Nginx CORS 响应头

### 6.3 安全配置

- 启用 HTTPS
- 配置正确的 CORS 白名单
- 不要使用 `*` 作为 Access-Control-Allow-Origin

# 运维操作记录

```Shell
# 获取 cmdb 库全部集合
docker exec mongo1 mongo --host 192.168.45.141 --port 27017 -u cc -p 'cc123456' --authenticationDatabase cmdb cmdb --eval "db.getCollectionNames()"
```

## MongoDB CMDB 数据库集合列表

**查询时间**: 2026-03-25\
**数据库**: cmdb\
**集合总数**: 89 个

### 核心业务集合

| 集合名称                 | 说明      |
| -------------------- | ------- |
| `cc_HostBase`        | 主机基础信息  |
| `cc_ModuleBase`      | 模块基础信息  |
| `cc_SetBase`         | 集群_实例数据  |
| `cc_BizSetBase`      | 业务集基础信息 |
| `cc_ApplicationBase` | 应用基础信息  |
| `cc_PlatBase`        | 平台基础信息  |
| `cc_Process`         | 进程信息    |
| `cc_ServiceInstance` | 服务实例    |
| `cc_ServiceTemplate` | 服务模板    |

### 对象模型相关

| 集合名称                   | 说明     |
| ---------------------- | ------ |
| `cc_ObjectBase`        | 对象模型基础 |
| `cc_ObjDes`            | 对象描述   |
| `cc_ObjAsst`           | 对象关联   |
| `cc_ObjAttDes`         | 对象属性描述 |
| `cc_ObjClassification` | 对象分类   |
| `cc_ObjectUnique`      | 对象唯一约束 |
| `cc_PropertyGroup`     | 属性分组   |

### 关联关系

| 集合名称                  | 说明            |
| --------------------- | ------------- |
| `cc_InstAsst`         | 实例关联          |
| `cc_InstAsst_0_pub_*` | 公共实例关联（按模型分类） |
| `cc_ModuleHostConfig` | 模块主机配置        |

### 审计与历史

| 集合名称            | 说明   |
| --------------- | ---- |
| `cc_AuditLog`   | 审计日志 |
| `cc_History`    | 历史记录 |
| `cc_WatchToken` | 监听令牌 |

### 用户配置

| 集合名称               | 说明      |
| ------------------ | ------- |
| `cc_UserCustom`    | 用户自定义配置 |
| `cc_HostFavourite` | 主机关联收藏  |
| `cc_ChartConfig`   | 图表配置    |
| `cc_ChartData`     | 图表数据    |
| `cc_ChartPosition` | 图表位置    |

### 云管理

| 集合名称                  | 说明    |
| --------------------- | ----- |
| `cc_CloudAccount`     | 云账号   |
| `cc_CloudSyncTask`    | 云同步任务 |
| `cc_CloudSyncHistory` | 云同步历史 |

### 其他重要集合

| 集合名称                  | 说明     |
| --------------------- | ------ |
| `cc_idgenerator`      | ID 生成器 |
| `cc_DynamicGroup`     | 动态分组   |
| `cc_Subscription`     | 订阅     |
| `cc_TopologyGraphics` | 拓扑图    |
| `cc_ServiceCategory`  | 服务分类   |

### WatchChain 系列（数据变更监听）

- `cc_HostBaseWatchChain` - 主机数据变更监听
- `cc_ModuleBaseWatchChain` - 模块数据变更监听
- `cc_SetBaseWatchChain` - 集群数据变更监听
- `cc_ObjectBaseWatchChain` - 对象模型变更监听
- `cc_ProcessWatchChain` - 进程数据变更监听
- `cc_ModuleHostConfigWatchChain` - 模块主机配置变更监听
- `cc_SetServiceTemplateRelation` - 集群服务模板关系
- `cc_SetTemplate` - 集群模板
- `cc_SetTemplateAttr` - 集群模板属性
- `cc_ProcessTemplate` - 进程模板
- `cc_ProcessInstanceRelation` - 进程实例关系
- `cc_ServiceTemplateAttr` - 服务模板属性
- `cc_bizSetRelationMixedWatchChain` - 业务集关系混合监听
- `cc_MainlineInstanceWatchChain` - 主线实例监听
- `cc_InstAsstWatchChain` - 实例关联监听
- `cc_ObjectBaseWatchChain` - 对象基础监听
- `cc_HostIdentityMixedWatchChain` - 主机身份混合监听
- `cc_BizSetBaseWatchChain` - 业务集基础监听
- `cc_ApplicationBaseWatchChain` - 应用基础监听

### 其他集合

- `cc_APITask` - API 任务
- `cc_APITaskSyncHistory` - API 任务同步历史
- `cc_AsstDes` - 关联描述
- `cc_DelArchive` - 删除归档
- `cc_HostApplyRule` - 主机应用规则
- `cc_HostLock` - 主机锁
- `cc_System` - 系统
- `cc_UserAPI` - 用户 API
- `cc_NetcollectDevice` - 网络设备采集
- `cc_NetcollectProperty` - 网络采集属性
- `cc_ObjectBaseMapping` - 对象基础映射

### 关联

- `cc_InstAsst_0_pub_biz` - 公共业务实例关联
- `cc_InstAsst_0_pub_bk_biz_set_obj` - 公共业务集对象实例关联
- `cc_InstAsst_0_pub_host` - 公共主机实例关联
- `cc_InstAsst_0_pub_module` - 公共模块实例关联
- `cc_InstAsst_0_pub_plat` - 公共平台实例关联
- `cc_InstAsst_0_pub_process` - 公共进程实例关联
- `cc_InstAsst_0_pub_set` - 公共集群实例关联

### 客制模型关联

- `cc_InstAsst_0_pub_subsys` - 应用节点关联
- `cc_InstAsst_0_pub_sys` - 应用系统关联

### 客制模型对象

- `cc_ObjectBase_0_pub_subsys` - 应用节点对象
- `cc_ObjectBase_0_pub_sys` - 应用系统对象

### 客制预设对象

- `cc_ObjectBase_0_pub_bk_firewall` - 公共防火墙对象
- `cc_ObjectBase_0_pub_bk_load_balance` - 公共负载均衡对象
- `cc_ObjectBase_0_pub_bk_router` - 公共路由器对象
- `cc_ObjectBase_0_pub_bk_switch` - 公共交换机对象

<br />

### 集合名命名规则

```
客制模型格式:
cc_ObjectBase_{supplierAccount}_pub_{objectID}
cc_InstAsst_{supplierAccount}_pub_{objectID}
# {supplierAccount} 供应商账号 默认0
# {objectID} 模型英文名称
```

### 各部分含义：

这个"0"代表 供应商账号（bk\_supplier\_account） ，原因如下：

1. 多租户架构设计 : CMDB 支持多租户，不同供应商（租户）有各自独立的数据表
2. 分片策略 : 每个供应商的对象实例存储在不同的集合中，实现数据隔离
3. 默认值 : "0"是默认供应商账号，代表系统内置的租户

<br />

***

**注**: 以上集合涵盖了 CMDB 的所有核心功能模块，包括主机管理、拓扑管理、进程管理、服务管理、云管理等功能。
