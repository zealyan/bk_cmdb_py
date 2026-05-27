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

部署内容，conf配置ip等支持webui、sqlcli、lib部署版本参考

```bash

[ywserver@localhost flink-1.18.1]$ ls -tlr lib
total 312276
-rwxr-xr-x 1 ywserver ywserver     24279 Sep 23  2022 log4j-slf4j-impl-2.17.1.jar
-rwxr-xr-x 1 ywserver ywserver   1790452 Sep 23  2022 log4j-core-2.17.1.jar
-rwxr-xr-x 1 ywserver ywserver    301872 Sep 23  2022 log4j-api-2.17.1.jar
-rwxr-xr-x 1 ywserver ywserver    208006 Sep 23  2022 log4j-1.2-api-2.17.1.jar
-rwxr-xr-x 1 ywserver ywserver    196578 Dec 20  2023 flink-cep-1.18.1.jar
-rwxr-xr-x 1 ywserver ywserver   3437157 Dec 20  2023 flink-table-runtime-1.18.1.jar
-rwxr-xr-x 1 ywserver ywserver    554431 Dec 20  2023 flink-connector-files-1.18.1.jar
-rwxr-xr-x 1 ywserver ywserver    202901 Dec 20  2023 flink-json-1.18.1.jar
-rwxr-xr-x 1 ywserver ywserver    102376 Dec 20  2023 flink-csv-1.18.1.jar
-rwxr-xr-x 1 ywserver ywserver  38216715 Dec 20  2023 flink-table-planner-loader-1.18.1.jar
-rwxr-xr-x 1 ywserver ywserver  21058485 Dec 20  2023 flink-scala_2.12-1.18.1.jar
-rwxr-xr-x 1 ywserver ywserver  15527125 Dec 20  2023 flink-table-api-java-uber-1.18.1.jar
-rwxr-xr-x 1 ywserver ywserver 127072434 Dec 20  2023 flink-dist-1.18.1.jar
-rwxr-xr-x 1 ywserver ywserver  43317025 Jan  9 13:29 flink-shaded-hadoop-2-uber-2.8.3-10.0.jar
-rwxr-xr-x 1 ywserver ywserver  48525885 Jan 26 11:00 paimon-flink-1.18-1.1-20250126.002637-36.jar
-rwxr-xr-x 1 ywserver ywserver     11507 Jan 26 11:05 paimon-flink-action-1.1-20250126.002637-36.jar
-rwxr-xr-x 1 ywserver ywserver  19188902 Mar 27 13:54 flink-sql-connector-mongodb-cdc-3.1.1.jar

[ywserver@localhost ~]$ cat /home/ywserver/flink-1.18.1/conf/flink-conf.yaml|grep -v "#"

jobmanager.rpc.address: 0.0.0.0
jobmanager.rpc.port: 6123
jobmanager.bind-host: 0.0.0.0
jobmanager.memory.process.size: 1000m

taskmanager.bind-host: 0.0.0.0
taskmanager.host: 0.0.0.0
taskmanager.memory.process.size: 3072m
taskmanager.numberOfTaskSlots: 8


parallelism.default: 2

execution.checkpointing.interval: 10min
execution.checkpointing.max-concurrent-checkpoints: 2
state.backend.type: rocksdb

state.checkpoints.dir: file:///home/ywserver/Documents/flinkstate/checkpoint
state.backend.incremental: true

jobmanager.execution.failover-strategy: region

rest.address: 0.0.0.0
rest.bind-address: 0.0.0.0

```

启动后，执行作业：

```bash

#单表同步

././bin/flink run /home/ywserver/flink-1.18.1/lib/paimon-flink-action-1.1-20250126.002637-36.jar  mongodb_sync_table \
--warehouse /home/ywserver/nasflie/flinkhouse \
--database cmdb \
--table cc_ObjAttDes \
--mongodb_conf hosts=197.68.2.119:27017  \
--mongodb_conf username=flinkcdc \
--mongodb_conf password=Y2gOct28 \
--mongodb_conf database=cmdb \
--mongodb_conf collection='cc_ObjAttDes' \
--table_conf bucket=1

# 单表其他案例
./bin/flink run /home/ywserver/flink-1.18.1/lib/paimon-flink-action-1.1-20250126.002637-36.jar  mongodb_sync_table --warehouse /home/ywserver/nasflie/flinkhouse --database cmdb --table cc_ObjAttDes --mongodb_conf hosts=197.68.2.119:27017,197.68.2.118:27017,197.68.2.120:27017  --mongodb_conf username=flinkcdc --mongodb_conf password=Y2gOct28 --mongodb_conf database=cmdb --mongodb_conf connection.options='replicaSet=rs0&readPreference=secondaryPreferred' --mongodb_conf collection='cc_ObjAttDes' --table_conf bucket=1 -Dexecution.checkpointing.externalized-checkpoint-retention=RETAIN_ON_CANCELLATION

#查看服务

[ywserver@localhost flink-1.18.1]$ jps
12035 StandaloneSessionClusterEntrypoint
12355 TaskManagerRunner
12395 Jps
[ywserver@localhost flink-1.18.1]$ ./bin/flink run /home/ywserver/flink-1.18.1/lib/paimon-flink-action-1.1-20250126.002637-36.jar  mongodb_sync_database --warehouse /home/ywserver/nasflie/flinkhouse --database cmdb  --mongodb_conf hosts=197.68.2.119:27017  --mongodb_conf username=flinkcdc --mongodb_conf password=Y2gOct28 --mongodb_conf database=cmdb  --table_conf bucket=1
Job has been submitted with JobID 37507d8472f2488797c7ebce63812586

GUI查看：

http://197.68.2.26:8081/#/overview

#优化后，p=4限制并行度为4；排除3个审计类大表 （实际无效果,资料说此参数只限制最小并行度）

./bin/flink run /home/ywserver/flink-1.18.1/lib/paimon-flink-action-1.1-20250126.002637-36.jar mongodb_sync_database \
--warehouse /home/ywserver/nasflie/flinkhouse \
--database cmdb \
--mongodb_conf hosts=197.68.2.119:27017 \
--mongodb_conf username=flinkcdc \
--mongodb_conf password=Y2gOct28 \
--mongodb_conf database=cmdb \
--table_conf bucket=1 \
--excluding_tables 'cc_AuditLog|cc_DelArchive|cc_idgenerator' \
-p 4

#修正为mongo集群连接串

./bin/flink run /home/ywserver/flink-1.18.1/lib/paimon-flink-action-1.1-20250126.002637-36.jar mongodb_sync_database \
--warehouse /home/ywserver/nasflie/flinkhouse \
--database cmdb \
--mongodb_conf hosts=197.68.2.119:27017,197.68.2.118:27017,197.68.2.120:27017 \
--mongodb_conf username=flinkcdc \
--mongodb_conf password=Y2gOct28 \
--mongodb_conf database=cmdb \
--mongodb_conf connection.options='replicaSet=rs0&readPreference=secondaryPreferred' \
--table_conf bucket=1 \
--excluding_tables 'cc_AuditLog|cc_DelArchive|cc_idgenerator' \
-p 4

# 实际测试发现,auditLog过大，仍然会出现一直被scan的情况，即便是被排除指定， 目前只能用单表同步：

#如以下三表,最终实践同步命令为：

  ./bin/flink run /home/ywserver/flink-1.18.1/lib/paimon-flink-action-1.1-20250126.002637-36.jar  mongodb_sync_table --warehouse /home/ywserver/nasflie/flinkhouse --database cmdb --table cc_ObjDes --mongodb_conf hosts=197.68.2.119:27017,197.68.2.118:27017,197.68.2.120:27017  --mongodb_conf username=flinkcdc --mongodb_conf password=Y2gOct28 --mongodb_conf database=cmdb --mongodb_conf connection.options='replicaSet=rs0&readPreference=secondaryPreferred' --mongodb_conf collection='cc_ObjDes' --table_conf bucket=1 -Dexecution.checkpointing.externalized-checkpoint-retention=RETAIN_ON_CANCELLATION
  ./bin/flink run /home/ywserver/flink-1.18.1/lib/paimon-flink-action-1.1-20250126.002637-36.jar  mongodb_sync_table --warehouse /home/ywserver/nasflie/flinkhouse --database cmdb --table cc_ObjAsst --mongodb_conf hosts=197.68.2.119:27017,197.68.2.118:27017,197.68.2.120:27017  --mongodb_conf username=flinkcdc --mongodb_conf password=Y2gOct28 --mongodb_conf database=cmdb --mongodb_conf connection.options='replicaSet=rs0&readPreference=secondaryPreferred' --mongodb_conf collection='cc_ObjAsst' --table_conf bucket=1 -Dexecution.checkpointing.externalized-checkpoint-retention=RETAIN_ON_CANCELLATION
  ./bin/flink run /home/ywserver/flink-1.18.1/lib/paimon-flink-action-1.1-20250126.002637-36.jar  mongodb_sync_table --warehouse /home/ywserver/nasflie/flinkhouse --database cmdb --table cc_ObjAttDes --mongodb_conf hosts=197.68.2.119:27017,197.68.2.118:27017,197.68.2.120:27017  --mongodb_conf username=flinkcdc --mongodb_conf password=Y2gOct28 --mongodb_conf database=cmdb --mongodb_conf connection.options='replicaSet=rs0&readPreference=secondaryPreferred' --mongodb_conf collection='cc_ObjAttDes' --table_conf bucket=1 -Dexecution.checkpointing.externalized-checkpoint-retention=RETAIN_ON_CANCELLATION

```

启动
./sql-gateway.sh start -Dsql-gateway.endpoint.rest.address=197.68.2.26

dbeaver安装驱动，flink1.18后支持

D:\dbeaver-22.2.3\maven-central\flink\flink-sql-jdbc-driver-bundle-1.18.1.jar
设置类名：
org.apache.flink.table.jdbc.FlinkDriver
新建连接，密码用户空
jdbc:flink://197.68.2.26:8083
使用console

```sql
create catalog my_pai1 with ('type'='paimon','warehouse'='file:/home/ywserver/nasflie/flinkhouse');
use catalog my_pai1;
show databases;
use cmdb;
show tables;
-----设置为批模式,文档曰默认读取latest snapshot文档;yzg:可用理解为读取无job流的数据
set 'execution.runtime-mode' = 'batch';
SELECT * FROM cc_ObjectBase_0_pub_redis_cluster;
SELECT * FROM cc_ObjDes;
SELECT * FROM cc_ObjAttDes;
SELECT * FROM cc_ObjAsst;
SELECT * FROM cc_ObjectBase_0_pub_vcenter;

SELECT * FROM (
(SELECT ob1.bk_classification_id,
	op.bk_obj_id,
	ob1.bk_obj_name,
	op.bk_property_id,
	op.bk_property_name,
	op.editable,
	op.isrequired,
	op.isonly,
	json_value(op.bk_property_index, '$.$numberLong') as bk_property_index,
	op.bk_property_type,
	op.option,
	op.placeholder
FROM
	cc_ObjAttDes AS op
LEFT JOIN (
	SELECT
		bk_obj_id,
		bk_obj_name,
		bk_classification_id
	FROM
		cc_ObjDes
	WHERE
		bk_ispaused = 'false') AS ob1 ON op.bk_obj_id = ob1.bk_obj_id
WHERE
	ob1.bk_obj_name IS NOT NULL )
UNION 
(
SELECT 
  ob1.bk_classification_id,
	oa.bk_obj_id,
	ob1.bk_obj_name,
	oa.bk_obj_asst_id AS bk_property_id,
	ob.bk_obj_name AS bk_property_name,
	'false' AS editable,
	'false' AS isrequired,
	'false' AS isonly,
	'909' AS bk_property_index,
	'asst' AS  bk_property_type,
	oa.mapping AS  option,
	oa.bk_obj_asst_name AS  placeholder
FROM
	cc_ObjAsst AS oa
LEFT JOIN cc_ObjDes AS ob ON
	oa.bk_asst_obj_id = ob.bk_obj_id
LEFT JOIN cc_ObjDes AS ob1 ON
	oa.bk_obj_id = ob1.bk_obj_id)
) ORDER BY bk_classification_id,bk_obj_id,isonly DESC,bk_property_index;
```

