# bk-cmdb 开发环境搭建 SOP（v3.10.41 / v3.10.50）

> 本文档原以 **v3.10.41** 编写；当前 `bk_cmdb_py` 仓库内实际内置的是 **v3.10.50** 源码（`bk-cmdb-release-v3.10.50/`）。二者构建流程一致，差异仅集中在「源码来源」与「UI 依赖补丁」两处，详见末尾 **§11 v3.10.50 版本差异补充**。

## 0\. 版本与源码说明

| 版本 | 源码来源 | 源码目录 |
|------|----------|----------|
| v3.10.41 | GitHub 下载 release 压缩包（见 §1） | `/workspace/bk-cmdb-release-v3.10.41/` |
| **v3.10.50**（本仓库） | 仓库内已内置，无需下载 | `/workspace/bk_cmdb_py/bk-cmdb-release-v3.10.50/` |

> 若使用本仓库内置的 v3.10.50，请跳过 §1 的下载步骤，直接以 `bk-cmdb-release-v3.10.50` 作为源码根目录，并将后续所有命令中的路径替换为该目录。构建产物已归集至 `prod_bin/`（见 `prod_bin/build_manifest.txt`）。

## 1\. 下载解压源码（仅 v3.10.41 需要）

```bash
cd /workspace
wget -O bk-cmdb-release-v3.10.41.zip https://github.com/TencentBlueKing/bk-cmdb/archive/refs/tags/release-v3.10.41.zip
unzip -q bk-cmdb-release-v3.10.41.zip
rm bk-cmdb-release-v3.10.41.zip
```

源码目录：`/workspace/bk-cmdb-release-v3.10.41/`

\---

## 2\. 安装 MongoDB 4.4

```bash
# 导入 GPG key
curl -fsSL https://pgp.mongodb.com/server-4.4.asc | gpg --dearmor -o /usr/share/keyrings/mongodb-4.4.gpg

# 配置腾讯云镜像源（使用 focal 仓库兼容 Ubuntu 24.04）或其他中国镜像源
echo "deb \[arch=amd64 signed-by=/usr/share/keyrings/mongodb-4.4.gpg] https://mirrors.cloud.tencent.com/mongodb/apt/ubuntu focal/mongodb-org/4.4 multiverse" > /etc/apt/sources.list.d/mongodb-4.4.list

# Ubuntu 24.04 需额外安装 libssl1.1
wget -q http://archive.ubuntu.com/ubuntu/pool/main/o/openssl/libssl1.1\_1.1.1f-1ubuntu2.24\_amd64.deb -O /tmp/libssl1.1.deb
dpkg -i /tmp/libssl1.1.deb \&\& rm /tmp/libssl1.1.deb

# 安装
apt-get update \&\& apt-get install -y mongodb-org=4.4.29 mongodb-org-server=4.4.29 mongodb-org-shell=4.4.29 mongodb-org-mongos=4.4.29 mongodb-org-tools=4.4.29

# 以副本集模式启动（bk-cmdb 事务功能依赖副本集）
mkdir -p /data/db
mongod --dbpath /data/db --replSet rs0 --fork --logpath /var/log/mongodb/mongod.log

# 初始化副本集
mongo --quiet --eval 'rs.initiate({\_id: "rs0", members: \[{\_id: 0, host: "127.0.0.1:27017"}]})'

# 创建数据库用户
mongo --quiet --eval '
db = db.getSiblingDB("cmdb");
db.createUser({user: "cc", pwd: "cc", roles: \[{role: "readWrite", db: "cmdb"}]});
'
```

\---

## 3\. 安装 ZooKeeper 3.8

```bash
# 从清华镜像下载或其他中国镜像源
curl -fsSL -o /tmp/zookeeper.tar.gz "https://mirrors.tuna.tsinghua.edu.cn/apache/zookeeper/zookeeper-3.8.6/apache-zookeeper-3.8.6-bin.tar.gz"
tar -xzf /tmp/zookeeper.tar.gz -C /usr/local/
ln -s /usr/local/apache-zookeeper-3.8.6-bin /usr/local/zookeeper
rm /tmp/zookeeper.tar.gz

# 配置
cp /usr/local/zookeeper/conf/zoo\_sample.cfg /usr/local/zookeeper/conf/zoo.cfg
# 修改 dataDir=/data/zookeeper
sed -i 's|dataDir=/tmp/zookeeper|dataDir=/data/zookeeper|' /usr/local/zookeeper/conf/zoo.cfg
mkdir -p /data/zookeeper

# 启动
/usr/local/zookeeper/bin/zkServer.sh start
```

\---

## 4\. 安装 Redis

```bash
# 优先考虑使用redis 5.x
# Ubuntu 24.04 仓库自带 7.0.15，满足文档要求 >= 3.2.11
apt-get install -y redis-server

# 启动并设置密码（文档要求必须启用 auth）
redis-server --daemonize yes --bind 0.0.0.0 --port 6379
redis-cli CONFIG SET requirepass "cmdb\_redis"
```

\---

## 5\. 构建 UI

```bash
cd /workspace/bk-cmdb-release-v3.10.41/src/ui

# 配置腾讯云 npm 镜像或其他中国镜像源
npm config set registry https://mirrors.cloud.tencent.com/npm/

# 安装依赖（--ignore-scripts 跳过 fibers 编译问题，--legacy-peer-deps 兼容旧依赖）
npm install --ignore-scripts --legacy-peer-deps

# 补充安装 @babel/runtime（源码缺此依赖）
npm install @babel/runtime@^7.0.0

# 生产构建
npm run build
```

构建产物：`src/bin/enterprise/cmdb/web/`

> **v3.10.50 注意（webpack 5）**：v3.10.50 的 UI 基于 **webpack 5**，而 `package.json` 漏列了两个被 webpack 5 拆分为独立包的依赖，且 `@babel/runtime` 安装需规避 peer 冲突。请改用以下命令（否则 `npm run build` 会报 `Cannot find module 'terser-webpack-plugin'`）：
> ```bash
> # 安装依赖（--ignore-scripts 跳过 fibers 编译问题，--legacy-peer-deps 兼容旧依赖）
> npm install --ignore-scripts --legacy-peer-deps
> # 补充 @babel/runtime（源码缺此依赖，必须加 --legacy-peer-deps 否则与 eslint-config-tencent peer 冲突）
> npm install @babel/runtime@^7.0.0 --legacy-peer-deps
> # 补充 webpack 5 拆分出的依赖（package.json 漏列）
> npm install terser-webpack-plugin@^5 webpack-cli@^4 --legacy-peer-deps
> # 生产构建（BUILD_OUTPUT 仅从 process.argv 读取、不读环境变量，未传参时落到默认路径）
> npm run build
> ```
> 构建产物路径与 v3.10.41 一致：`src/bin/enterprise/cmdb/web/`。

\---

## 6\. 编译 Go 后端服务（最小化服务集）

```bash
# 最小化 6 个服务：adminserver、coreservice、toposerver、hostserver、apiserver、webserver
cd /workspace/bk-cmdb-release-v3.10.41/src

make -C scene\_server/admin\_server    # cmdb\_adminserver
make -C source\_controller/coreservice # cmdb\_coreservice
make -C scene\_server/topo\_server      # cmdb\_toposerver
make -C scene\_server/host\_server      # cmdb\_hostserver
make -C apiserver                     # cmdb\_apiserver
make -C web\_server                    # cmdb\_webserver
```

编译产物：`src/bin/build/cmdb\_\*/cmdb\_\*`

> **v3.10.50 注意（VERSION 与产物路径）**：v3.10.50 目录是 `bk_cmdb_py` 这个 git 仓库的**子目录**（非独立仓库），`git symbolic-ref` 返回的是外层仓库分支 `main`，因此 `VERSION` 默认解析为 `main`，编译产物会落在 `src/bin/build/main/`。
> - 若想让产物路径带上版本号（如 `src/bin/build/v3.10.50/`），在构建前 `export VERSION=v3.10.50` 即可（`scripts/Makefile` 中 `VERSION?=...` 为「未设才赋值」，环境变量优先级更高）。
> - 首次编译需下载 Go 模块，建议配置国内代理加速：`export GOPROXY=https://goproxy.cn,direct GOSUMDB=off`。
> - Go 1.21.x 可正常编译 v3.10.50；仅编译上述 6 个最小服务约 40~60 秒（模块已缓存时更快）。
> - 仅构建这 6 个服务即可满足 CMDB 基础运行；`make server` 会全量构建 11+ 服务且任一失败即中止，按需使用。

\---

## 7\. 准备部署目录和配置

### 7.1 目录结构

```bash
mkdir -p /data/cmdb/cmdb\_adminserver/{configures,conf/errors,conf/language,logs}
mkdir -p /data/cmdb/cmdb\_coreservice/logs
mkdir -p /data/cmdb/cmdb\_toposerver/logs
mkdir -p /data/cmdb/cmdb\_hostserver/logs
mkdir -p /data/cmdb/cmdb\_apiserver/logs
mkdir -p /data/cmdb/cmdb\_webserver/logs
mkdir -p /data/cmdb/web

# 复制二进制
cp src/bin/build/cmdb\_adminserver/cmdb\_adminserver /data/cmdb/cmdb\_adminserver/
cp src/bin/build/cmdb\_coreservice/cmdb\_coreservice /data/cmdb/cmdb\_coreservice/
cp src/bin/build/cmdb\_toposerver/cmdb\_toposerver /data/cmdb/cmdb\_toposerver/
cp src/bin/build/cmdb\_hostserver/cmdb\_hostserver /data/cmdb/cmdb\_hostserver/
cp src/bin/build/cmdb\_apiserver/cmdb\_apiserver /data/cmdb/cmdb\_apiserver/
cp src/bin/build/cmdb\_webserver/cmdb\_webserver /data/cmdb/cmdb\_webserver/

# 复制资源文件
cp -r resources/errors/\* /data/cmdb/cmdb\_adminserver/conf/errors/
cp -r resources/language/\* /data/cmdb/cmdb\_adminserver/conf/language/

# 复制前端构建产物
cp -r src/bin/enterprise/cmdb/web/\* /data/cmdb/web/
```

### 7.2 配置文件

所有配置文件位于 `/data/cmdb/cmdb\_adminserver/configures/`

**migrate.yaml**（adminserver 启动入口）

```yaml
configServer:
  addrs: 127.0.0.1:2181
  usr:
  pwd:
registerServer:
  addrs: 127.0.0.1:2181
  usr:
  pwd:
confs:
  dir: /data/cmdb/cmdb\_adminserver/configures
errors:
  res: /data/cmdb/cmdb\_adminserver/conf/errors
language:
  res: /data/cmdb/cmdb\_adminserver/conf/language
```

**mongodb.yaml**

```yaml
mongodb:
  host: 127.0.0.1
  port: 27017
  usr: cc
  pwd: cc
  database: cmdb
  maxOpenConns: 3000
  maxIdleConns: 100
  mechanism: SCRAM-SHA-1
  rsName: rs0
  socketTimeoutSeconds: 10
watch:
  host: 127.0.0.1
  port: 27017
  usr: cc
  pwd: cc
  database: cmdb
  maxOpenConns: 10
  maxIdleConns: 5
  mechanism: SCRAM-SHA-1
  rsName: rs0
  socketTimeoutSeconds: 10
```

**redis.yaml**

```yaml
redis:
  host: 127.0.0.1:6379
  pwd: "cmdb\_redis"
  sentinelPwd: ""
  database: "0"
  maxOpenConns: 3000
  maxIDleConns: 1000
  snap:
    host: 127.0.0.1:6379
    pwd: "cmdb\_redis"
    sentinelPwd: ""
    database: "0"
    enable: "false"
  discover:
    host: 127.0.0.1:6379
    pwd: "cmdb\_redis"
    sentinelPwd: ""
    database: "0"
    enable: "false"
  netcollect:
    host: 127.0.0.1:6379
    pwd: "cmdb\_redis"
    sentinelPwd: ""
    database: "0"
    enable: "false"
```

**common.yaml**（关键配置项）

```yaml
es:
  fullTextSearch: "off"
  url: http://127.0.0.1:9200
  usr:
  pwd:

webServer:
  api:
    version: v3
  session:
    name: cc3
    defaultlanguage: zh-cn
    multipleOwner: "0"
    userInfo: admin:admin          # Web 登录账号密码
  site:
    domainUrl: /                   # 相对路径，预览环境兼容
    bkLoginUrl: http://127.0.0.1:8083/login/?app\_id=%s\&c\_url=%s
    appCode: cc
    checkUrl: http://127.0.0.1:8083/login/accounts/get\_user/?bk\_token=
    htmlRoot: /data/cmdb/web       # 前端文件路径
    authscheme: internal           # 内置权限模式，不使用 IAM
  login:
    version: opensource            # 开源登录方式，skip-login方式待评估是否有效

authServer:
  address: ""
  appCode: bk\_cmdb
  appSecret: ""

datacollection:
  hostsnap:
    reportMode: redis
    changeRangePercent: 10
    rateLimiter:
      qps: 40
      burst: 100

eventServer:
  hostIdentifier:
    startUp: false

cloudServer:
  cryptor:
    enableCryptor: false

monitor:
  pluginName: noop
  enableMonitor: false

openTelemetry:
  enable: false

gse:
  apiServer:
    endpoints:
  taskServer:
    endpoints:

kafka:
  snap:
    brokers:
    groupID: bk\_cmdb\_snapshot\_group

tls:
  insecureSkipVerify:
  certFile:
  keyFile:
  caFile:
```

**extra.yaml**

```yaml
# 空文件，用于扩展配置
```

\---

## 8\. 启动 Go 服务（按顺序）

> \*\*启动顺序\*\*：adminserver → coreservice → toposerver → hostserver → apiserver → webserver

```bash
# 1. adminserver（使用 --config 而非 --regdiscv）
cd /data/cmdb/cmdb\_adminserver
nohup ./cmdb\_adminserver \\
  --addrport=127.0.0.1:60004 \\
  --logtostderr=false --log-dir=./logs --v=3 \\
  --config=configures/migrate.yaml \\
  --enable-auth=false \\
  > ./logs/std.log 2>\&1 \&

# 2. coreservice
cd /data/cmdb/cmdb\_coreservice
nohup ./cmdb\_coreservice \\
  --addrport=127.0.0.1:50009 \\
  --logtostderr=false --log-dir=./logs --v=3 \\
  --regdiscv=127.0.0.1:2181 \\
  > ./logs/std.log 2>\&1 \&

# 3. toposerver
cd /data/cmdb/cmdb\_toposerver
nohup ./cmdb\_toposerver \\
  --addrport=127.0.0.1:60002 \\
  --logtostderr=false --log-dir=./logs --v=3 \\
  --regdiscv=127.0.0.1:2181 \\
  --enable-auth=false \\
  > ./logs/std.log 2>\&1 \&

# 4. hostserver
cd /data/cmdb/cmdb\_hostserver
nohup ./cmdb\_hostserver \\
  --addrport=127.0.0.1:60001 \\
  --logtostderr=false --log-dir=./logs --v=3 \\
  --regdiscv=127.0.0.1:2181 \\
  --enable-auth=false \\
  > ./logs/std.log 2>\&1 \&

# 5. apiserver
cd /data/cmdb/cmdb\_apiserver
nohup ./cmdb\_apiserver \\
  --addrport=127.0.0.1:8081 \\
  --logtostderr=false --log-dir=./logs --v=3 \\
  --regdiscv=127.0.0.1:2181 \\
  --enable-auth=false \\
  > ./logs/std.log 2>\&1 \&

# 6. webserver（绑定 0.0.0.0 支持外部访问，--register-ip 避免 0.0.0.0 注册报错）
cd /data/cmdb/cmdb\_webserver
nohup ./cmdb\_webserver \\
  --addrport=0.0.0.0:8083 \\
  --logtostderr=false --log-dir=./logs --v=3 \\
  --regdiscv=127.0.0.1:2181 \\
  --register-ip=127.0.0.1 \\
  > ./logs/std.log 2>\&1 \&
```

\---

## 9\. 初始化数据库

```bash
# 等待所有服务就绪后执行
curl -s -X POST \\
  -H 'Content-Type:application/json' \\
  -H 'BK\_USER:migrate' \\
  -H 'HTTP\_BLUEKING\_SUPPLIER\_ID:0' \\
  http://127.0.0.1:60004/migrate/v3/migrate/community/0

# 成功返回：{"result":true,"bk\_error\_code":0,"bk\_error\_msg":"","data":"migrate success",...}
```

\---

## 10\. 验证与预览

### 健康检查

```bash
# coreservice
curl -s http://127.0.0.1:50009/healthz | python3 -m json.tool

# API 测试（查询业务列表）
curl -s "http://127.0.0.1:8081/api/v3/biz/search/0" \\
  -X POST -H 'Content-Type:application/json' \\
  -H 'BK\_USER:admin' -H 'HTTP\_BLUEKING\_SUPPLIER\_ID:0' \\
  -d '{"condition":{}}'
```

### Web 预览

```bash
# 使用codebuddy preview skill 获取外部预览 URL，或其他agent 的web Preview
/root/.codebuddy/skills/preview/notify 8083
```

登录账号：`admin` / `admin`

\---

## 端口总览

|服务|端口|绑定地址|
|-|-|-|
|MongoDB|27017|127.0.0.1|
|ZooKeeper|2181|127.0.0.1|
|Redis|6379|0.0.0.0|
|cmdb\_adminserver|60004|127.0.0.1|
|cmdb\_coreservice|50009|127.0.0.1|
|cmdb\_toposerver|60002|127.0.0.1|
|cmdb\_hostserver|60001|127.0.0.1|
|cmdb\_apiserver|8081|127.0.0.1|
|cmdb\_webserver|8083|0.0.0.0|

\---

## 踩坑记录

|问题|原因|解决方案|
|-|-|-|
|MongoDB 4.4 在 Ubuntu 24.04 安装失败|缺少 `libssl1.1`|从 Ubuntu 20.04 仓库安装 `libssl1.1` deb 包|
|MongoDB 副本集报错 `ReplicaSetNoPrimary`|未以副本集模式启动|启动时加 `--replSet rs0`，并执行 `rs.initiate()`|
|UI 构建 `fibers` 编译失败|Node 22 与 fibers 5 不兼容|使用 `--ignore-scripts` 跳过，fibers 非必须|
|UI 构建 `@babel/runtime` 缺失|源码未声明此依赖|手动 `npm install @babel/runtime`|
|apiserver 端口 8080 被占用|系统代理占用|改用 8081 端口|
|webserver `register ip can not be 0.0.0.0`|绑定 0.0.0.0 时注册 IP 校验不通过|加 `--register-ip=127.0.0.1`|
|登录后跳转到不可达的 `127.0.0.1:8083`|`domainUrl` 配置了绝对 URL|改为相对路径 `/`|
|修改配置后服务未生效|配置存储在 ZK 中|调用 `POST /migrate/v3/migrate/config/refresh` 刷新 ZK 配置，再重启服务|
|v3.10.50 UI 构建报 `Cannot find module 'terser-webpack-plugin'`|webpack 5 已将该包拆分为独立依赖，但 `package.json` 漏列|`npm install terser-webpack-plugin@^5 webpack-cli@^4 --legacy-peer-deps`|
|v3.10.50 安装 `@babel/runtime` 报 peer 冲突（eslint-config-tencent）|npm 11 严格校验 peer 依赖|安装时加 `--legacy-peer-deps`|
|v3.10.50 编译产物落在 `src/bin/build/main/` 而非版本目录|v3.10.50 是 `bk_cmdb_py` 仓库子目录，`git symbolic-ref` 返回外层分支 `main`|构建前 `export VERSION=v3.10.50`|

\---

## 11\. v3.10.50 版本差异补充

本仓库实际内置源码为 **bk-cmdb v3.10.50**（`bk-cmdb-release-v3.10.50/`），与本文档基线 v3.10.41 的整体流程一致，差别集中在「源码来源」与「UI 依赖补丁」。以下为 v3.10.50 实测补充。

### 11.1 源码来源

- v3.10.41：按 §1 从 GitHub 下载 `release-v3.10.41.zip`。
- **v3.10.50（本仓库）**：已内置，路径 `/workspace/bk_cmdb_py/bk-cmdb-release-v3.10.50/`，**跳过 §1 下载步骤**，后续命令中的 `bk-cmdb-release-v3.10.41` 全部替换为 `bk-cmdb-release-v3.10.50`。

### 11.2 UI 构建差异（webpack 5）

v3.10.50 的 UI 使用 **webpack 5**，而 `package.json` 漏列了 webpack 5 拆分出的 `terser-webpack-plugin` / `webpack-cli`；同时 `@babel/runtime` 安装会触发 `eslint-config-tencent` 的 peer 冲突。完整命令：

```bash
cd /workspace/bk_cmdb_py/bk-cmdb-release-v3.10.50/src/ui
npm config set registry https://mirrors.cloud.tencent.com/npm/

npm install --ignore-scripts --legacy-peer-deps
npm install @babel/runtime@^7.0.0 --legacy-peer-deps
npm install terser-webpack-plugin@^5 webpack-cli@^4 --legacy-peer-deps

# BUILD_OUTPUT 仅从 process.argv 读取、不读环境变量；未传参时落到默认路径
npm run build
```

- 构建产物：`src/bin/enterprise/cmdb/web/`（与 v3.10.41 一致）。
- 若想自定义输出目录，需通过 `npm run build BUILD_OUTPUT=/abs/path` 传参（而非环境变量）。

### 11.3 Go 后端编译差异

```bash
cd /workspace/bk_cmdb_py/bk-cmdb-release-v3.10.50/src
export GOPROXY=https://goproxy.cn,direct GOSUMDB=off
export VERSION=v3.10.50   # 可选：让产物落在 src/bin/build/v3.10.50/ 而非默认的 main

for svc in scene_server/admin_server source_controller/coreservice \
           scene_server/topo_server scene_server/host_server \
           apiserver web_server; do
  make -C $svc
done
```

- 版本与产物路径：`bk-cmdb-release-v3.10.50` 是 `bk_cmdb_py` 仓库的子目录，`git symbolic-ref` 返回外层分支 `main`，故 `VERSION` 默认解析为 `main`，产物在 `src/bin/build/main/`；`export VERSION=v3.10.50` 可得到干净的版本目录。
- 工具链：Go 1.21.x 可正常编译；6 个最小服务约 40~60 秒（模块已缓存更快）。
- 范围：`make server` 会全量构建 11+ 服务且任一失败即中止；仅运行基础 CMDB 时构建上述 6 个服务即可。

### 11.4 产物归集（已执行）

按本任务要求，已将构建产物归集至仓库内 `prod_bin/`：

| 类别 | 位置 | 内容 |
|------|------|------|
| 后端 | `prod_bin/server/` | 6 个 Go 服务二进制（226M） |
| 前端 | `prod_bin/ui/` | Vue 生产构建静态资源（14M，388 文件） |

详细清单见 `prod_bin/build_manifest.txt`。后续启动仍按 §7~§9 配置 `/data/cmdb` 并启动服务。



