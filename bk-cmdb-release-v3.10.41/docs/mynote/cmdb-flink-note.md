2026 年环境操作记录

服务器环境：ssh://192.168.45.141

部署路径：/home/ywserver/flink-1.18.1

数据路径：/home/ywserver/nasflie/flinkhouse

状态数据：/home/ywserver/nasflie/flinkstate

java 路径 (ywserver 用户自带): /home/ywserver/jdk1.8.0\_191/bin/java

用户初始化Demo：

```bash

mongo -u $BK_MONGODB_ADMIN_USER -p $BK_MONGODB_ADMIN_PASSWORD mongodb://197.68.2.119:27017 --authenticationDatabase admin
MongoDB shell version v4.4.15
connecting to: mongodb://197.68.2.119:27017/?authSource=admin&compressors=disabled&gssapiServiceName=mongodb
Implicit session: session { "id" : UUID("ea9277f9-8e05-410b-a935-f03877702519") }
MongoDB server version: 4.4.15


rs0:PRIMARY> use admin;
switched to db admin
#如果为从库，需切为主库操作admin
rs.secondaryOk()
rs0:PRIMARY> show dbs;
admin         0.000GB
cmdb         61.974GB
cmdb_events   1.257GB
config        0.013GB
gse           0.005GB
joblog        0.610GB
local         1.924GB
rs0:PRIMARY> show roles;
{
        "role" : "__queryableBackup",
        "db" : "admin",
        "isBuiltin" : true,
        "roles" : [ ],
        "inheritedRoles" : [ ]
}
{
        "role" : "__system",
        "db" : "admin",
        "isBuiltin" : true,
        "roles" : [ ],
        "inheritedRoles" : [ ]
}
{
        "role" : "backup",
        "db" : "admin",
        "isBuiltin" : true,
        "roles" : [ ],
        "inheritedRoles" : [ ]
}
{
        "role" : "clusterAdmin",
        "db" : "admin",
        "isBuiltin" : true,
        "roles" : [ ],
        "inheritedRoles" : [ ]
}
{
        "role" : "clusterManager",
        "db" : "admin",
        "isBuiltin" : true,
        "roles" : [ ],
        "inheritedRoles" : [ ]
}
{
        "role" : "clusterMonitor",
        "db" : "admin",
        "isBuiltin" : true,
        "roles" : [ ],
        "inheritedRoles" : [ ]
}
{
        "role" : "dbAdmin",
        "db" : "admin",
        "isBuiltin" : true,
        "roles" : [ ],
        "inheritedRoles" : [ ]
}
{
        "role" : "dbAdminAnyDatabase",
        "db" : "admin",
        "isBuiltin" : true,
        "roles" : [ ],
        "inheritedRoles" : [ ]
}
{
        "role" : "dbOwner",
        "db" : "admin",
        "isBuiltin" : true,
        "roles" : [ ],
        "inheritedRoles" : [ ]
}
{
        "role" : "enableSharding",
        "db" : "admin",
        "isBuiltin" : true,
        "roles" : [ ],
        "inheritedRoles" : [ ]
}
{
        "role" : "hostManager",
        "db" : "admin",
        "isBuiltin" : true,
        "roles" : [ ],
        "inheritedRoles" : [ ]
}
{
        "role" : "read",
        "db" : "admin",
        "isBuiltin" : true,
        "roles" : [ ],
        "inheritedRoles" : [ ]
}
{
        "role" : "readAnyDatabase",
        "db" : "admin",
        "isBuiltin" : true,
        "roles" : [ ],
        "inheritedRoles" : [ ]
}
{
        "role" : "readWrite",
        "db" : "admin",
        "isBuiltin" : true,
        "roles" : [ ],
        "inheritedRoles" : [ ]
}
{
        "role" : "readWriteAnyDatabase",
        "db" : "admin",
        "isBuiltin" : true,
        "roles" : [ ],
        "inheritedRoles" : [ ]
}
{
        "role" : "restore",
        "db" : "admin",
        "isBuiltin" : true,
        "roles" : [ ],
        "inheritedRoles" : [ ]
}
{
        "role" : "root",
        "db" : "admin",
        "isBuiltin" : true,
        "roles" : [ ],
        "inheritedRoles" : [ ]
}
{
        "role" : "userAdmin",
        "db" : "admin",
        "isBuiltin" : true,
        "roles" : [ ],
        "inheritedRoles" : [ ]
}
{
        "role" : "userAdminAnyDatabase",
        "db" : "admin",
        "isBuiltin" : true,
        "roles" : [ ],
        "inheritedRoles" : [ ]
}

use admin;

db.createRole({
  role: "flinkrole",  // 角色名称
  privileges: [
    {
      resource: {  // 定义资源
        db: "",  // 数据库名称
        collection: ""           // 如果为所有集合，则留空
      },
      actions: [                // 定义该角色可以执行的操作
        "find",                // 读取数据
        "splitVector",
		"listDatabases",
		"listCollections",
		"collStats",
		"changeStream"
      ]
	  
	  
    }

  ],
  roles: [                     // 如果需要继承其他角色，可以在这里定义
    {
      role: "read",
      db: "config"
    }
  ]
});
db.getRole("flinkrole")
{
        "role" : "flinkrole",
        "db" : "admin",
        "isBuiltin" : false,
        "roles" : [
                {
                        "role" : "read",
                        "db" : "config"
                }
        ],
        "inheritedRoles" : [
                {
                        "role" : "read",
                        "db" : "config"
                }
        ]
}
rs0:PRIMARY> db.getRole("flinkrole").privileges
rs0:PRIMARY> db.createUser({user:'flinkcdc',pwd:'Y2gOct28',roles:[{role:'flinkrole',db:'admin'}]});
Successfully added user: {
        "user" : "flinkcdc",
        "roles" : [
                {
                        "role" : "flinkrole",
                        "db" : "admin"
                }
        ]
}
rs0:PRIMARY> db.getUser('flinkcdc')
{
        "_id" : "admin.flinkcdc",
        "userId" : UUID("33eaa838-90a6-47b1-b01e-a9761c8b5156"),
        "user" : "flinkcdc",
        "db" : "admin",
        "roles" : [
                {
                        "role" : "flinkrole",
                        "db" : "admin"
                }
        ],
        "mechanisms" : [
                "SCRAM-SHA-1",
                "SCRAM-SHA-256"
        ]
}

#重建role,修改权限
#这里db：admin可能是指role、user的配置保存在admin库
rs0:PRIMARY> use admin ;
switched to db admin
rs0:PRIMARY> db.dropRole("flinkrole")
true
rs0:PRIMARY> db.getUser("flinkcdc")
{
        "_id" : "admin.flinkcdc",
        "userId" : UUID("33eaa838-90a6-47b1-b01e-a9761c8b5156"),
        "user" : "flinkcdc",
        "db" : "admin",
        "roles" : [ ],
        "mechanisms" : [
                "SCRAM-SHA-1",
                "SCRAM-SHA-256"
        ]
}
db.createRole({
    role: "flinkrole",  // 角色名称
    privileges: [
      {
        resource: {  // 定义资源
          db: "cmdb",  // 数据库名称
          collection: "*"           // 如果为所有集合，则留空
        },
        actions: [                // 定义该角色可以执行的操作
          "find",                // 读取数据
          "splitVector",
          "listDatabases",
          "listCollections",
          "collStats",
          "changeStream"
        ]
      }

    ],
    roles: [                     // 如果需要继承其他角色，可以在这里定义
      {
        role: "read",
        db: "config"
      }
    ]
  }）
db.grantRolesToUser("flinkcdc",["flinkrole"])
```

## 集群模式

```Shell
# 集群下先全量后增量的不结束 job
cd /home/ywserver/flink-1.18.1
./bin/start-cluster.sh 
export JAVA_HOME=/home/ywserver/jdk1.8.0_191 && /home/ywserver/flink-1.18.1/bin/flink run /home/ywserver/flink-1.18.1/lib/paimon-flink-action-1.1-20250126.002637-36.jar mongodb_sync_table --warehouse /home/ywserver/nasflie/flinkhouse --database cmdb --table cc_SetBase --mongodb_conf hosts=192.168.45.141:27017,192.168.45.141:27018,192.168.45.141:27019 --mongodb_conf username=flinkcdc --mongodb_conf password=Y2gOct28 --mongodb_conf database=cmdb --mongodb_conf connection.options='replicaSet=rs0&readPreference=secondaryPreferred' --mongodb_conf collection='cc_SetBase' --table_conf bucket=1 -Dexecution.checkpointing.externalized-checkpoint-retention=RETAIN_ON_CANCELLATION
```

### 带状态的启动命令（集群模式）

```Shell
# 带状态参数的集群模式启动
export JAVA_HOME=/home/ywserver/jdk1.8.0_191 && /home/ywserver/flink-1.18.1/bin/flink run \
  -Dstate.checkpoints.dir=file:///home/ywserver/nasflie/flinkstate \
  -Dexecution.checkpointing.externalized-checkpoint-retention=RETAIN_ON_CANCELLATION \
  -Dexecution.checkpointing.interval=10s \
  -Dexecution.checkpointing.timeout=600s \
  -Dexecution.checkpointing.max-concurrent-checkpoints=1 \
  -Dexecution.checkpointing.min-pause=5s \
  /home/ywserver/flink-1.18.1/myaction/paimon1.3.1/paimon-flink-action-1.3.1.jar mongodb_sync_table \
  --warehouse /home/ywserver/nasflie/flinkhouse \
  --database cmdb \
  --table cc_SetBase \
  --mongodb_conf hosts=192.168.45.141:27017,192.168.45.141:27018,192.168.45.141:27019 \
  --mongodb_conf username=flinkcdc \
  --mongodb_conf password=Y2gOct28 \
  --mongodb_conf database=cmdb \
  --mongodb_conf collection='cc_SetBase' \
  --table_conf bucket=1
```

### 状态保存与恢复（集群模式）

**状态保存**：

- 作业运行时会自动在 `file:///home/ywserver/nasflie/flinkstate` 目录生成 checkpoint
- 检查 checkpoint 生成：
  ```Shell
  ls -laR /home/ywserver/nasflie/flinkstate/
  ```

**状态恢复**：

- **解决 Commons CLI 依赖冲突**：使用 `-Dexecution.savepoint.path` 替代 `-s` 参数
- **恢复命令**：

```Shell
  # 从 checkpoint 恢复作业（避开 -s 参数的依赖冲突）
export JAVA_HOME=/home/ywserver/jdk1.8.0_191 && /home/ywserver/flink-1.18.1/bin/flink run \
  -Dstate.checkpoints.dir=file:///home/ywserver/nasflie/flinkstate \
  -Dexecution.checkpointing.externalized-checkpoint-retention=RETAIN_ON_CANCELLATION \
  -Dexecution.checkpointing.interval=10s \
  -Dexecution.checkpointing.timeout=600s \
  -Dexecution.checkpointing.max-concurrent-checkpoints=1 \
  -Dexecution.checkpointing.min-pause=5s \
  -Dexecution.savepoint.path=file:///home/ywserver/nasflie/flinkstate/<job-id>/chk-<n> \
  /home/ywserver/flink-1.18.1/myaction/paimon1.3.1/paimon-flink-action-1.3.1.jar mongodb_sync_table \
  --warehouse /home/ywserver/nasflie/flinkhouse \
  --database cmdb \
  --table cc_SetBase \
  --mongodb_conf hosts=192.168.45.141:27017 \
  --mongodb_conf username=flinkcdc \
  --mongodb_conf password=Y2gOct28 \
  --mongodb_conf database=cmdb \
  --mongodb_conf collection='cc_SetBase' \
  --table_conf bucket=1
```

**注意事项**：

- 替换 `<job-id>` 为实际的作业 ID 目录
- 替换 `<chk-n>` 为实际的 checkpoint 目录（如 chk-242）
- 确保 checkpoint 目录存在且包含 `_metadata` 文件

非集群模式

```Shell
# 不启动集群的客户端 job 模式
export JAVA_HOME=/home/ywserver/jdk1.8.0_191 && /home/ywserver/flink-1.18.1/bin/flink run -Dexecution.target=local -Dstate.checkpoints.dir=file:///home/ywserver/nasflie/flinkstate -Dexecution.checkpointing.externalized-checkpoint-retention=RETAIN_ON_CANCELLATION /home/ywserver/flink-1.18.1/myaction/paimon1.3.1/paimon-flink-action-1.3.1.jar mongodb_sync_table --warehouse /home/ywserver/nasflie/flinkhouse --database cmdb --table cc_SetBase --mongodb_conf hosts=192.168.45.141:27017 --mongodb_conf username=flinkcdc --mongodb_conf password=Y2gOct28 --mongodb_conf database=cmdb --mongodb_conf collection='cc_SetBase' --table_conf bucket=1 --snapshot-only
```

<br />

## 非集群模式

### 1. 状态参数设置（重要）

**验证结论**：在 `flink run` 命令中可以通过 `-D` 参数设置 state 存档路径。

**关键配置参数**：

```Shell
# 正确的 state 路径配置参数（指定 checkpoint 存储目录）
-Dstate.checkpoints.dir=file:///home/ywserver/nasflie/flinkstate

# 其他 checkpoint 相关参数
-Dexecution.checkpointing.externalized-checkpoint-retention=RETAIN_ON_CANCELLATION  # 取消后保留 checkpoint
-Dexecution.checkpointing.interval=10s                                   # checkpoint 间隔
-Dexecution.checkpointing.timeout=600s                                  # checkpoint 超时时间
-Dexecution.checkpointing.max-concurrent-checkpoints=1                   # 最大并发 checkpoint 数
-Dexecution.checkpointing.min-pause=5s                                  # checkpoint 最小间隔
```

### 带状态的启动命令（非集群模式）

```Shell
# 带状态参数的非集群模式启动
export JAVA_HOME=/home/ywserver/jdk1.8.0_191 && /home/ywserver/flink-1.18.1/bin/flink run \
  -Dexecution.target=local \
  -Dstate.checkpoints.dir=file:///home/ywserver/nasflie/flinkstate \
  -Dexecution.checkpointing.externalized-checkpoint-retention=RETAIN_ON_CANCELLATION \
  -Dexecution.checkpointing.interval=10s \
  -Dexecution.checkpointing.timeout=600s \
  -Dexecution.checkpointing.max-concurrent-checkpoints=1 \
  -Dexecution.checkpointing.min-pause=5s \
  /home/ywserver/flink-1.18.1/myaction/paimon1.3.1/paimon-flink-action-1.3.1.jar mongodb_sync_table \
  --warehouse /home/ywserver/nasflie/flinkhouse \
  --database cmdb \
  --table cc_SetBase \
  --mongodb_conf hosts=192.168.45.141:27017 \
  --mongodb_conf username=flinkcdc \
  --mongodb_conf password=Y2gOct28 \
  --mongodb_conf database=cmdb \
  --mongodb_conf collection='cc_SetBase' \
  --table_conf bucket=1
```

### 状态保存与恢复（非集群模式）

### 3. 验证 State 文件生成

```Shell
# 检查 state 目录结构
ls -laR /home/ywserver/nasflie/flinkstate/

# 预期输出示例
/home/ywserver/nasflie/flinkstate/
└── <job-id>/
    ├── chk-<n>/
    │   └── _metadata
    ├── shared/
    └── taskowned/
```

**状态保存**：

- 作业运行时会自动在 `file:///home/ywserver/nasflie/flinkstate` 目录生成 checkpoint
- 检查 checkpoint 生成：
  ```Shell
  ls -laR /home/ywserver/nasflie/flinkstate/
  ```

**状态恢复**：

- **解决 Commons CLI 依赖冲突**：使用 `-Dexecution.savepoint.path` 替代 `-s` 参数
- **恢复命令**：（实验未通过）

```Shell
  # 从 checkpoint 恢复作业（避开 -s 参数的依赖冲突）
export JAVA_HOME=/home/ywserver/jdk1.8.0_191 && /home/ywserver/flink-1.18.1/bin/flink run \
  -Dexecution.target=local \
  -Dstate.checkpoints.dir=file:///home/ywserver/nasflie/flinkstate \
  -Dexecution.checkpointing.externalized-checkpoint-retention=RETAIN_ON_CANCELLATION \
  -Dexecution.checkpointing.interval=10s \
  -Dexecution.checkpointing.timeout=600s \
  -Dexecution.checkpointing.max-concurrent-checkpoints=1 \
  -Dexecution.checkpointing.min-pause=5s \
  -Dexecution.savepoint.path=file:///home/ywserver/nasflie/flinkstate/<job-id>/chk-<n> \
  /home/ywserver/flink-1.18.1/myaction/paimon1.3.1/paimon-flink-action-1.3.1.jar mongodb_sync_table \
  --warehouse /home/ywserver/nasflie/flinkhouse \
  --database cmdb \
  --table cc_SetBase \
  --mongodb_conf hosts=192.168.45.141:27017 \
  --mongodb_conf username=flinkcdc \
  --mongodb_conf password=Y2gOct28 \
  --mongodb_conf database=cmdb \
  --mongodb_conf collection='cc_SetBase' \
  --table_conf bucket=1
```

**注意事项**：

- 替换 `<job-id>` 为实际的作业 ID 目录
- 替换 `<chk-n>` 为实际的 checkpoint 目录（如 chk-242）
- 确保 checkpoint 目录存在且包含 `_metadata` 文件

<br />

<br />

## Flink SQL 测试操作步骤

### 0. Embedded 模式说明（不启动集群，但实测连Mongodb有问题）

**验证结论**：Flink SQL Client 使用Mongodb，必须 start-Cluster

**优势**：

- 节约内存：不需要启动 JobManager 和 TaskManager 进程
- 快速测试：直接执行 SQL 文件，适合开发和测试环境
- 资源友好：JVM 参数可优化，内存占用可控制在 512MB 以内

**执行方式**：

```Shell
# 使用 embedded 模式执行 SQL 文件（不启动集群）
export JAVA_HOME=/home/ywserver/jdk1.8.0_191
export FLINK_ENV_JAVA_OPTS="-Xms256m -Xmx512m -XX:MetaspaceSize=128m -XX:MaxMetaspaceSize=256m -XX:+UseG1GC -XX:MaxGCPauseMillis=200"
/home/ywserver/flink-1.18.1/bin/sql-client.sh embedded -f /path/to/your/sql/file.sql
```

**JVM 参数优化说明**：

```Shell
# 推荐的小型测试配置（最大内存约 512MB）
-Xms256m                     # 初始堆大小
-Xmx512m                     # 最大堆大小
-XX:MetaspaceSize=128m       # 初始元空间大小
-XX:MaxMetaspaceSize=256m    # 最大元空间大小
-XX:+UseG1GC                 # 使用 G1 垃圾收集器
-XX:MaxGCPauseMillis=200     # 目标最大 GC 暂停时间 200ms

# 如果需要处理更多数据，可适当增加：
# -Xms512m -Xmx1024m（最大内存约 1GB）
```

**注意事项**：

- MongoDB CDC 源表是流式表，INSERT 语句会持续运行
- 测试时可使用 timeout 命令控制执行时间，或使用 Ctrl+C 手动停止
- 全量同步完成后，作业会进入增量同步模式（持续运行）

### 0.1 State 存档路径配置（重要）

**验证结论**：在 SQL 文件中可以通过 `SET` 命令配置 checkpoint 和 state 存储路径。

**关键配置参数**：

```SQL
-- 启用 checkpoint
SET 'execution.checkpointing.interval' = '10s';

-- 设置 checkpoint 存储目录（state 存档路径）
SET 'state.checkpoints.dir' = 'file:///home/ywserver/nasflie/flinkstate/checkpoints';

-- 设置 savepoint 存储目录
SET 'state.savepoints.dir' = 'file:///home/ywserver/nasflie/flinkstate/savepoints';

-- 设置 checkpoint 外部化保留策略（取消后保留 checkpoint）
SET 'execution.checkpointing.externalized-checkpoint-retention' = 'RETAIN_ON_CANCELLATION';

-- 设置 checkpoint 超时时间
SET 'execution.checkpointing.timeout' = '600s';

-- 设置最大并发 checkpoint 数
SET 'execution.checkpointing.max-concurrent-checkpoints' = '1';

-- 设置 checkpoint 最小间隔
SET 'execution.checkpointing.min-pause' = '5s';

-- 设置状态后端（使用 filesystem）
SET 'state.backend' = 'filesystem';

-- 设置状态后端存储路径
SET 'state.backend.fs.checkpointdir' = 'file:///home/ywserver/nasflie/flinkstate/backend';
```

**目录结构说明**：

```
/home/ywserver/nasflie/flinkstate/
├── checkpoints/          # checkpoint 文件目录
├── savepoints/           # savepoint 文件目录
└── backend/              # state backend 存储目录
```

**实验验证步骤**：

1. 清理环境和状态目录
2. 创建带有 state 路径配置的 SQL 文件
3. 执行 SQL 文件作业
4. 检查 `/home/ywserver/nasflie/flinkstate/` 目录结构

### 1. 准备合并后的 SQL 文件

```Shell
-- 创建带 State 存档配置的 SQL 文件（主用文件）
echo "-- 创建 Paimon Catalog
CREATE CATALOG paimon_catalog WITH (
    'type'='paimon',
    'warehouse'='file:/home/ywserver/nasflie/flinkhouse'
);

-- 使用 Paimon Catalog
USE CATALOG paimon_catalog;

-- 创建数据库
CREATE DATABASE IF NOT EXISTS cmdb;

-- 创建 Paimon 目标表
CREATE TABLE cmdb.cc_SetBase (
  _id STRING PRIMARY KEY NOT ENFORCED,
  bk_set_id STRING,
  bk_set_name STRING
) WITH (
  'file.format' = 'parquet',
  'sink.upsert-mode' = 'true',
  'bucket' = '1'
);

-- 查看表结构
DESCRIBE cmdb.cc_SetBase;

-- 创建 MongoDB CDC 源表（使用 TEMPORARY）
CREATE TEMPORARY TABLE mongo_setbase (
  _id STRING PRIMARY KEY NOT ENFORCED,
  bk_set_id STRING,
  bk_set_name STRING
) WITH (
  'connector' = 'mongodb-cdc',
  'hosts' = '192.168.45.141:27017,192.168.45.141:27018,192.168.45.141:27019',
  'username' = 'flinkcdc',
  'password' = 'Y2gOct28',
  'database' = 'cmdb',
  'collection' = 'cc_SetBase',
  'scan.startup.mode' = 'initial',
  'connection.options' = 'replicaSet=rs0&readPreference=secondaryPreferred'
);

-- ============================================
-- Checkpoint 和 State 配置（关键配置）
-- ============================================

-- 启用 checkpoint
SET 'execution.checkpointing.interval' = '10s';

-- 设置 checkpoint 存储目录（state 存档路径）
SET 'state.checkpoints.dir' = 'file:///home/ywserver/nasflie/flinkstate/checkpoints';

-- 设置 savepoint 存储目录
SET 'state.savepoints.dir' = 'file:///home/ywserver/nasflie/flinkstate/savepoints';

-- 设置 checkpoint 外部化保留策略
SET 'execution.checkpointing.externalized-checkpoint-retention' = 'RETAIN_ON_CANCELLATION';

-- 设置 checkpoint 超时时间
SET 'execution.checkpointing.timeout' = '600s';

-- 设置最大并发 checkpoint 数
SET 'execution.checkpointing.max-concurrent-checkpoints' = '1';

-- 设置 checkpoint 最小间隔
SET 'execution.checkpointing.min-pause' = '5s';

-- 设置状态后端（使用 filesystem）
SET 'state.backend' = 'filesystem';

-- 设置状态后端存储路径
SET 'state.backend.fs.checkpointdir' = 'file:///home/ywserver/nasflie/flinkstate/backend';

-- 执行数据同步（流式处理，会持续运行）
INSERT INTO cmdb.cc_SetBase SELECT * FROM mongo_setbase;" > /home/ywserver/nasflie/mongo_to_paimon_with_state.sql

-- 创建查询验证的 SQL 文件
echo "-- 创建 Paimon Catalog
CREATE CATALOG paimon_catalog WITH (
    'type'='paimon',
    'warehouse'='file:/home/ywserver/nasflie/flinkhouse'
);

-- 使用 Paimon Catalog
USE CATALOG paimon_catalog;

-- 设置结果模式
SET 'sql-client.execution.result-mode' = 'tableau';

-- 切换到批处理模式
SET 'execution.runtime-mode' = 'batch';

-- 查询同步结果
SELECT * FROM cmdb.cc_SetBase LIMIT 10;" > /home/ywserver/nasflie/query_paimon.sql
```

### 2. 执行操作

#### 2.1 创建表并执行同步（主用方式：带 State 存档配置）

```Shell
export JAVA_HOME=/home/ywserver/jdk1.8.0_191
export FLINK_ENV_JAVA_OPTS="-Xms256m -Xmx512m -XX:MetaspaceSize=128m -XX:MaxMetaspaceSize=256m -XX:+UseG1GC -XX:MaxGCPauseMillis=200"
nohup /home/ywserver/flink-1.18.1/bin/sql-client.sh embedded -f /home/ywserver/nasflie/mongo_to_paimon_with_state.sql > /tmp/flink_sql_state_test.log 2>&1 &

# 查看执行日志
tail -f /tmp/flink_sql_state_test.log

# 检查 state 文件生成
ls -laR /home/ywserver/nasflie/flinkstate/
```

#### 2.2 验证同步结果

```Shell
export JAVA_HOME=/home/ywserver/jdk1.8.0_191
export FLINK_ENV_JAVA_OPTS="-Xms256m -Xmx512m -XX:MetaspaceSize=128m -XX:MaxMetaspaceSize=256m -XX:+UseG1GC -XX:MaxGCPauseMillis=200"
/home/ywserver/flink-1.18.1/bin/sql-client.sh embedded -f /home/ywserver/nasflie/query_paimon.sql
```

### 3. 验证结果

#### 3.1 检查 Paimon 表目录结构

```Shell
ls -la /home/ywserver/nasflie/flinkhouse/cmdb.db/cc_SetBase/
```

#### 3.2 检查快照文件

```Shell
ls -la /home/ywserver/nasflie/flinkhouse/cmdb.db/cc_SetBase/snapshot/
```

#### 3.3 检查数据文件

```Shell
ls -la /home/ywserver/nasflie/flinkhouse/cmdb.db/cc_SetBase/bucket-0/
```

#### 3.4 State文件

```Shell
ls -la /home/ywserver/nasflie/flinkstate/
```

### 4. 同步结果示例

| \_id                     | bk\_set\_id | bk\_set\_name        |
| ------------------------ | ----------- | -------------------- |
| 69c16198bc6a9298e23a1463 | 1           | 空闲机池                 |
| 69c16198bc6a9298e23a1468 | 2           | 空闲机池                 |
| 69c2c7c9bb6ff54b8ff61a98 | 3           | 空闲机池                 |
| 69c3282673e73ee2aaffe856 | 5           | 久张系统                 |
| 69c3292073e73ee2aaffe863 | 6           | 空闲机池                 |
| 69c33e5d73e73ee2aaffe873 | 7           | SET 好性能              |
| 69c34b2e73e73ee2aaffe88b | 8           | 幸福 xx 子系统            |
| 69c40a1473e73ee2aaffe92a | 9           | lp-zwapp-k8sa        |
| 69c4926773e73ee2aaffe951 | 10          | lp-fzwapp-vma        |
| 69c4928873e73ee2aaffe953 | 11          | lp-fzwapp-dill-redis |

