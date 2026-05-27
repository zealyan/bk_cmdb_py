# MongoDB 副本集集群安装文档

## 1. 环境准备

- **服务器**：192.168.45.141
- **用户**：root
- **Docker**：已安装
- **数据目录**：/root/mongo\_data

## 2. 规划

### 2.1 节点规划

| 节点    | 容器名称   | 端口    | 数据目录                     |
| ----- | ------ | ----- | ------------------------ |
| 主节点   | mongo1 | 27017 | /root/mongo\_data/mongo1 |
| 副本节点1 | mongo2 | 27018 | /root/mongo\_data/mongo2 |
| 副本节点2 | mongo3 | 27019 | /root/mongo\_data/mongo3 |

### 2.2 网络规划

- 使用 host 网络模式
- 副本集名称：rs0

## 3. 安装步骤

### 3.1 创建数据目录

```bash
mkdir -p /root/mongo_data/mongo1 /root/mongo_data/mongo2 /root/mongo_data/mongo3
```

### 3.2 启动 MongoDB 容器

#### 启动主节点（mongo1）

```bash
docker run -d --name mongo1 --network host -v /root/mongo_data/mongo1:/data/db -v /root/mongo_data/mongo1:/data/configdb swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/library/mongo:4.4 --replSet rs0 --port 27017
```

#### 启动副本节点1（mongo2）

```bash
docker run -d --name mongo2 --network host -v /root/mongo_data/mongo2:/data/db -v /root/mongo_data/mongo2:/data/configdb swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/library/mongo:4.4 --replSet rs0 --port 27018
```

#### 启动副本节点2（mongo3）

```bash
docker run -d --name mongo3 --network host -v /root/mongo_data/mongo3:/data/db -v /root/mongo_data/mongo3:/data/configdb swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/library/mongo:4.4 --replSet rs0 --port 27019
```

### 3.3 初始化副本集

1. 初始化副本集配置（非交互式）

```bash
docker exec mongo1 mongo --port 27017 --eval "rs.initiate({ _id: 'rs0', members: [{ _id: 0, host: '192.168.45.141:27017' }, { _id: 1, host: '192.168.45.141:27018' }, { _id: 2, host: '192.168.45.141:27019' }] })"
```

1. 查看副本集状态

```bash
docker exec mongo1 mongo --port 27017 --eval "rs.status()"
```

## 4. 验证安装

### 4.1 检查容器状态

```bash
docker ps | grep mongo
```

### 4.2 检查副本集状态

```bash
docker exec mongo1 mongo --port 27017 --eval "rs.status()"
```

### 4.3 测试写入操作

```bash
docker exec mongo1 mongo --port 27017 --eval "db.test.insert({name: 'test'})"
```

### 4.4 测试数据同步（在副本节点上验证）

```bash
docker exec mongo2 mongo --port 27018 --eval "rs.slaveOk(); db.test.find()"
```

## 5. 配置连接字符串

对于应用连接，使用以下连接字符串：

```
mongodb://192.168.45.141:27017,192.168.45.141:27018,192.168.45.141:27019/admin?replicaSet=rs0
```

## 6. 停止副本集

### 6.1 停止所有MongoDB容器

```bash
docker stop mongo1 mongo2 mongo3
```

### 6.2 查看容器状态（确认已停止）

```bash
docker ps -a | grep mongo
```

## 7. 一键启动脚本

### 7.0 手动步骤

```Shell
docker start mongo1
docker start mongo2
docker start mongo3
docker exec mongo1 mongo --port 27018 cmdb --eval "db.getUsers()"
```

### 7.1 start\_mongo.sh 脚本（保留数据状态）

该脚本用于启动MongoDB副本集集群，保留上一次停止时的数据状态，不会重新初始化集群。

```bash
#!/bin/bash

# MongoDB 副本集集群启动脚本（保留数据状态）

# 定义变量
MONGODB_IMAGE="swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/library/mongo:4.4"
REPLICA_SET_NAME="rs0"
DATA_DIR="/root/mongo_data"

# 颜色定义
GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[1;33m"
NC="\033[0m" # No Color

# 打印函数
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查Docker是否运行
if ! docker info > /dev/null 2>&1; then
    print_error "Docker服务未运行，请先启动Docker"
    exit 1
fi

# 检查数据目录是否存在
if [ ! -d "$DATA_DIR" ]; then
    print_error "数据目录 $DATA_DIR 不存在"
    exit 1
fi

# 确保子目录存在
mkdir -p "$DATA_DIR/mongo1" "$DATA_DIR/mongo2" "$DATA_DIR/mongo3"

# 检查并启动容器
for i in {1..3}; do
    CONTAINER_NAME="mongo$i"
    PORT=$((27016 + i))
    
    # 检查容器是否存在
    if docker ps -a | grep -q "$CONTAINER_NAME"; then
        # 检查容器是否在运行
        if ! docker ps | grep -q "$CONTAINER_NAME"; then
            print_info "启动容器 $CONTAINER_NAME..."
            docker start "$CONTAINER_NAME"
        else
            print_info "容器 $CONTAINER_NAME 已经在运行"
        fi
    else
        # 容器不存在，创建新容器
        print_info "创建并启动容器 $CONTAINER_NAME..."
        docker run -d --name "$CONTAINER_NAME" --network host -v "$DATA_DIR/mongo$i:/data/db" -v "$DATA_DIR/mongo$i:/data/configdb" "$MONGODB_IMAGE" --replSet "$REPLICA_SET_NAME" --port "$PORT"
    fi
done

# 等待容器启动
print_info "等待容器启动..."
sleep 5

# 检查容器状态
print_info "检查容器状态..."
docker ps | grep mongo

# 检查副本集状态
print_info "检查副本集状态..."
STATUS=$(docker exec mongo1 mongo --port 27017 --eval "rs.status()" 2>/dev/null | grep -E '\"ok\" : [01]')

if echo "$STATUS" | grep -q '"ok" : 1'; then
    print_info "副本集状态正常！"
    # 打印详细状态
    print_info "副本集详细状态："
    docker exec mongo1 mongo --port 27017 --eval "rs.status()"
else
    # 副本集可能未初始化，尝试初始化
    print_warning "副本集状态异常，尝试初始化..."
    docker exec mongo1 mongo --port 27017 --eval "rs.initiate({ _id: '$REPLICA_SET_NAME', members: [{ _id: 0, host: '192.168.45.141:27017' }, { _id: 1, host: '192.168.45.141:27018' }, { _id: 2, host: '192.168.45.141:27019' }] })"
    
    # 等待初始化
    sleep 10
    
    # 再次检查状态
    STATUS=$(docker exec mongo1 mongo --port 27017 --eval "rs.status()" 2>/dev/null | grep -E '\"ok\" : [01]')
    if echo "$STATUS" | grep -q '"ok" : 1'; then
        print_info "副本集初始化成功！"
    else
        print_error "副本集初始化失败！"
        exit 1
    fi
fi

# 测试数据是否存在
print_info "测试数据是否存在..."
DATA_EXISTS=$(docker exec mongo1 mongo --port 27017 --eval "db.test.find()" 2>/dev/null | grep -E '\"name\" : \"test\"')

if [ -n "$DATA_EXISTS" ]; then
    print_info "测试数据存在，数据未丢失！"
    print_info "数据内容："
    docker exec mongo1 mongo --port 27017 --eval "db.test.find()"
else
    print_warning "测试数据不存在，可能是首次启动或数据已丢失"
    # 写入测试数据
    print_info "写入测试数据..."
    docker exec mongo1 mongo --port 27017 --eval "db.test.insert({name: 'test', timestamp: new Date()})"
fi

print_info "MongoDB副本集集群启动完成！"
print_info "连接字符串：mongodb://192.168.45.141:27017,192.168.45.141:27018,192.168.45.141:27019/admin?replicaSet=$REPLICA_SET_NAME"
```
Spark连接串参考:(已实测可用)
```
CREATE TEMPORARY VIEW cc_SetBase
USING com.mongodb.spark.sql.DefaultSource
OPTIONS (
  uri "mongodb://cc:cc123456@192.168.45.141:27017/cmdb.cc_SetBase?authSource=cmdb"
);
```

### 7.2 使用方法

1. **添加执行权限**：
   ```bash
   chmod +x /root/mongo_data/start_mongo.sh
   ```
2. **运行脚本**：
   ```bash
   /root/mongo_data/start_mongo.sh
   ```

### 7.3 脚本特点

- 保留数据状态，不会重新初始化集群
- 自动检查容器状态，只启动未运行的容器
- 自动检查副本集状态，异常时尝试初始化
- 测试数据是否存在，验证数据是否丢失
- 包含详细的状态输出和错误处理

## 8. 创建和验证用户

### 8.1 创建用户

在主节点上执行以下命令创建用户（以mongo2为例，根据实际主节点调整）：

```bash
docker exec mongo2 mongo --port 27018 cmdb --eval "db.createUser({user: 'cc', pwd: 'cc123456', roles: [{role: 'readWrite', db: 'cmdb'}]})"
```

**执行结果**：

```
Successfully added user: {
    "user" : "cc",
    "roles" : [
        {
            "role" : "readWrite",
            "db" : "cmdb"
        }
    ]
}
```

### 8.2 验证用户存在

在主节点上执行以下命令验证用户是否存在：

```bash
docker exec mongo2 mongo --port 27018 cmdb --eval "db.getUsers()"
```

**执行结果**：

```json
[
    {
        "_id" : "cmdb.cc",
        "userId" : UUID("79b5c15d-57fa-421f-b151-59835a267f78"),
        "user" : "cc",
        "db" : "cmdb",
        "roles" : [
            {
                "role" : "readWrite",
                "db" : "cmdb"
            }
        ],
        "mechanisms" : [
            "SCRAM-SHA-1",
            "SCRAM-SHA-256"
        ]
    }
]
```

### 8.3 验证结论

- ✅ 用户 `cc` 已成功创建并存在于 cmdb 数据库中
- ✅ 用户拥有 `readWrite` 角色权限
- ✅ 认证机制已正确配置为 `SCRAM-SHA-1` 和 `SCRAM-SHA-256`（符合 MongoDB 3.6+ 的要求）

## 9. CMDB 数据库初始化

### 9.1 前提条件

在执行数据库初始化之前，请确保：

1. MongoDB 副本集集群已正常启动并运行
2. 用户 `cc` 已创建（参见第8节）
3. CMDB 服务（特别是 `cmdb_adminserver`）已启动

### 9.2 更新 MongoDB 配置

编辑 `/home/cmdb/cmdb/cmdb_adminserver/configures/mongodb.yaml` 文件，确保配置正确：

```yaml
# mongodb配置
mongodb:
  host: 192.168.45.141
  port: 27017
  usr: cc
  pwd: "cc123456"
  database: cmdb
  maxOpenConns: 3000
  maxIdleConns: 100
  mechanism: SCRAM-SHA-1
  rsName: rs0
  socketTimeoutSeconds: 10
  watch:
    host: 192.168.45.141
    port: 27017
    usr: cc
    pwd: "cc123456"
    database: cmdb
    maxOpenConns: 10
    maxIdleConns: 5
    mechanism: SCRAM-SHA-1
    rsName: rs0
    socketTimeoutSeconds: 10
```

### 9.3 刷新配置到配置中心

```bash
cd /home/cmdb/cmdb
./refresh_config.sh mongodb
```

**预期输出**：

```json
{
 "result": true,
 "bk_error_code": 0,
 "bk_error_msg": "success",
 "permission": null,
 "data": "refresh config success"
}
```

### 9.4 启动 CMDB 服务

确保所有 CMDB 服务已启动：

```bash
cd /home/cmdb/cmdb
./start.sh
```

**预期输出**：

```
starting: cmdb_adminserver
starting: cmdb_apiserver
starting: cmdb_authserver
...
process count should be: 12 , now: 14
```

### 9.5 执行数据库初始化

```bash
cd /home/cmdb/cmdb
bash ./init_db.sh
```

**预期输出**：

```json
{
 "result": true,
 "bk_error_code": 0,
 "bk_error_msg": "",
 "permission": null,
 "data": "migrate success",
 "pre_version": "y3.10.202209231617",
 "current_version": "y3.10.202209231617",
 "finished_migrations": []
}
```

**注意**：

- 此步骤必须在所有 CMDB 进程成功启动后执行
- 如果输出中包含 `"data": "migrate success"`，表示数据库初始化成功
- 初始化过程可能需要几秒钟到几分钟，请耐心等待

### 9.6 验证服务

测试 toposerver 服务是否正常运行：

```bash
curl -X GET http://192.168.45.141:60002/topo/v3/app/si
```

**预期输出**：

```
405: Method Not Allowed
```

> 注：返回 405 错误表示服务正常运行（因为该接口需要使用 POST 方法访问）

## 10. 常见问题

### 10.1 副本集初始化失败

- 检查网络连接
- 确保所有节点都已启动
- 检查防火墙设置

### 10.2 数据目录权限问题

- 确保 /root/mongo\_data 目录权限正确
- 可使用 `chmod -R 777 /root/mongo_data` 赋予权限

### 10.3 容器启动失败

- 检查端口是否被占用
- 检查数据目录是否存在
- 查看容器日志：`docker logs <容器名称>`

### 10.4 数据库初始化失败

- 确保 MongoDB 副本集已正常启动
- 确保用户 `cc` 已创建
- 确保 `cmdb_adminserver` 服务已启动
- 检查 MongoDB 配置是否正确（host 应为 `192.168.45.141`，而不是 `127.0.0.1`）
- 检查防火墙是否允许访问 27017 端口

