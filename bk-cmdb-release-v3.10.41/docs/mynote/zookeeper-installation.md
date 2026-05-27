# Zookeeper 安装与配置文档

## 1. 环境准备

- **服务器**：192.168.45.141
- **用户**：root
- **Docker**：已安装
- **Zookeeper 镜像**：swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/library/zookeeper:3.4.13

## 2. 安装步骤

### 2.1 检查镜像是否存在

```bash
docker images | grep zookeeper
```

### 2.2 启动 Zookeeper 容器

#### 首次启动（创建容器）

使用 host 网络模式启动 Zookeeper 容器，默认端口 2181：

```bash
docker run -d --name zookeeper --network host swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/library/zookeeper:3.4.13
```

#### 后续启动（已存在容器）

如果容器已存在，使用以下命令启动：

```bash
docker start zookeeper
```

#### 停止容器

```bash
docker stop zookeeper
```

### 2.3 检查容器状态

```bash
docker ps | grep zookeeper
```

## 3. 测试数据读写

### 3.1 测试数据写入

```bash
docker exec zookeeper /bin/bash -c "echo 'create /test test_data' | bin/zkCli.sh -server 127.0.0.1:2181"
```

**执行结果**：

```
Connecting to 127.0.0.1:2181
2026-03-23 02:43:01,185 [myid:] - INFO  [main:Environment@100] - Client environment:zookeeper.version=3.4.13-2d71af4dbe22557fda74f9a9b4309b15a7487f03, built on 06/29/2018 04:05 GMT
...
[zk: 127.0.0.1:2181(CONNECTED) 1]
Created /test
```

### 3.2 测试数据读取

```bash
docker exec zookeeper /bin/bash -c "echo 'get /test' | bin/zkCli.sh -server 127.0.0.1:2181"
```

**执行结果**：

```
Connecting to 127.0.0.1:2181
2026-03-23 02:43:08,847 [myid:] - INFO  [main:Environment@100] - Client environment:zookeeper.version=3.4.13-2d71af4dbe22557fda74f9a9b4309b15a7487f03, built on 06/29/2018 04:05 GMT
...
[zk: 127.0.0.1:2181(CONNECTED) 0] get /test
test_data
[zk: 127.0.0.1:2181(CONNECTED) 1]
cZxid = 0x2
ctime = Mon Mar 23 02:43:01 GMT 2026
mZxid = 0x2
mtime = Mon Mar 23 02:43:01 GMT 2026
pZxid = 0x2
cversion = 0
dataVersion = 0
aclVersion = 0
ephemeralOwner = 0x0
dataLength = 9
numChildren = 0
```

## 4. 验证结果

- ✅ Zookeeper 容器已成功启动
- ✅ 数据写入功能正常
- ✅ 数据读取功能正常
- ✅ 端口 2181 可正常访问

## 5. 连接信息

- **服务地址**：192.168.45.141:2181
- **连接字符串**：127.0.0.1:2181
- **服务状态**：正常运行

## 6. 常见问题

### 6.1 容器启动失败

- 检查端口 2181 是否被占用
- 检查 Docker 服务是否运行
- 查看容器日志：`docker logs zookeeper`

### 6.2 数据读写失败

- 确保 Zookeeper 容器已正常启动
- 检查网络连接是否正常
- 验证端口 2181 是否可访问

