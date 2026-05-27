# CMDB MongoDB 操作记录

## 模型创建的事务过程

```
CreateObject (topo_server/logics/model/object.go)
    │
    ├── 1. 验证模型数据
    │      └── 查询 cc_ObjClassification（验证分类是否存在）
    │
    ├── 2. CreateModel (core_service)
    │      └── 写入 cc_ObjDes
    │          ├── 检查模型ID是否已存在
    │          └── 保存模型基础信息
    │
    ├── 3. CreateAttributeGroup
    │      └── 写入 cc_PropertyGroup
    │          └── 创建默认分组 "Default"
    │
    ├── 4. createDefaultAttrs
    │      └── 写入 cc_ObjAttDes
    │          ├── bk_inst_name（实例名）- 必创建
    │          └── bk_parent_id（父级ID）- 主线模型时创建
    │
    ├── 5. CreateModelAttrUnique
    │      └── 写入 cc_ObjectUnique
    │          └── 为 bk_inst_name 和 bk_parent_id 创建唯一约束
    │
    └── 6. CreateMainlineAssociation (如果是主线模型)
           └── 写入 cc_ObjAsst
               └── 创建主线关联关系（bk_mainline）
```

涉及写入的表：

cc\_ObjDes *sys* 模型的元数据&#x20;

cc\_ObjAttDes *sys* 的属性定义（bk\_inst\_name, bk\_parent\_id）&#x20;

cc\_PropertyGroup 默认分组 "Default"&#x20;

cc\_ObjectUnique 唯一约束（实例名+父级ID）&#x20;

cc\_ObjAsst（可选） 如果是主线模型，记录与其他模型的关联

## topo模型实例查询与数据插入

### 操作时间

2026-03-31

### 1. 查看 cc\_ObjectBase\_0\_pub\_sys 集合结构

```Shell
# AI: 查询应用系统集合的单条数据样例
docker exec mongo1 mongo --host 192.168.45.141 --port 27017 -u cc -p 'cc123456' --authenticationDatabase cmdb cmdb --eval "db.cc_ObjectBase_0_pub_sys.findOne()"
```

**返回结构示例**:

```json
{
    "_id": ObjectId("69c4095a73e73ee2aaffe908"),
    "create_time": ISODate("2026-03-25T16:12:10.590Z"),
    "last_time": ISODate("2026-03-25T16:12:10.590Z"),
    "bk_biz_id": NumberLong(2),
    "bk_inst_name": "系统",
    "bk_obj_id": "sys",
    "bk_parent_id": NumberLong(2),
    "bk_supplier_account": "0",
    "bk_inst_id": NumberLong(90)
}
```

### 2. 查看 cc\_ObjectBase\_0\_pub\_subsys 集合结构

```Shell
# AI: 查询应用节点集合的单条数据样例
docker exec mongo1 mongo --host 192.168.45.141 --port 27017 -u cc -p 'cc123456' --authenticationDatabase cmdb cmdb --eval "db.cc_ObjectBase_0_pub_subsys.findOne()"
```

**返回结构示例**:

```json
{
    "_id": ObjectId("69c4096f73e73ee2aaffe91c"),
    "bk_parent_id": NumberLong(90),
    "bk_supplier_account": "0",
    "bk_inst_id": NumberLong(98),
    "create_time": ISODate("2026-03-25T16:12:31.679Z"),
    "last_time": ISODate("2026-03-25T16:12:31.679Z"),
    "bk_biz_id": NumberLong(2),
    "bk_inst_name": "应用节点",
    "bk_obj_id": "subsys"
}
```

### 3. 查询 cc\_idgenerator 获取当前序列值

```Shell
# AI: 查询 cc_idgenerator 中 cc_ObjectBase 的当前序列值（所有分片表共享此序列）
docker exec mongo1 mongo --host 192.168.45.141 --port 27017 -u cc -p 'cc123456' --authenticationDatabase cmdb cmdb --eval 'db.cc_idgenerator.findOne({_id: "cc_ObjectBase"})'
```

**说明**:

- `cc_ObjectBase` 序列被所有 `cc_ObjectBase_*_pub_*` 分片表共享
- `SequenceID` 表示当前已分配的最大 ID
- 新插入数据应使用 `SequenceID + 1` 作为 `bk_inst_id`
- 同时需要更新 `cc_idgenerator` 中的 `SequenceID` 值

### 4. 插入模拟数据

#### 4.1 插入topo“系统”数据 (sys)

```Shell
# AI: 向sys集合插入测试数据，bk_inst_id=112，bk_parent_id=3(业务ID)，bk_biz_id=3
docker exec mongo1 mongo --host 192.168.45.141 --port 27017 -u cc -p 'cc123456' --authenticationDatabase cmdb cmdb --eval 'db.cc_ObjectBase_0_pub_sys.insertOne({"bk_inst_id": NumberLong(112), "bk_obj_id": "sys", "bk_parent_id": NumberLong(3), "bk_supplier_account": "0", "bk_biz_id": NumberLong(3), "bk_inst_name": "测试应用系统", "create_time": new Date(), "last_time": new Date()})'
```

**插入结果**:

```json
{
    "acknowledged": true,
    "insertedId": ObjectId("69c46c3cf4f583d5976e2489")
}
```

#### 4.2 插入topo“应用节点(subsys)”数据

```Shell
# AI: 向subsys集合插入测试数据，bk_inst_id=113，bk_parent_id=112(关联sys的实例ID)，bk_biz_id=3
docker exec mongo1 mongo --host 192.168.45.141 --port 27017 -u cc -p 'cc123456' --authenticationDatabase cmdb cmdb --eval 'db.cc_ObjectBase_0_pub_subsys.insertOne({"bk_inst_id": NumberLong(113), "bk_obj_id": "subsys", "bk_parent_id": NumberLong(112), "bk_supplier_account": "0", "bk_biz_id": NumberLong(3), "bk_inst_name": "测试应用节点", "create_time": new Date(), "last_time": new Date()})'
```

**插入结果**:

```json
{
    "acknowledged": true,
    "insertedId": ObjectId("69c46c4d0209f20e4d98c7d0")
}
```

### 5. 验证插入的数据

```Shell
# AI: 验证sys集合中bk_inst_id=112的数据
docker exec mongo1 mongo --host 192.168.45.141 --port 27017 -u cc -p 'cc123456' --authenticationDatabase cmdb cmdb --eval 'db.cc_ObjectBase_0_pub_sys.find({bk_inst_id: NumberLong(112)})'

# AI: 验证subsys集合中bk_inst_id=113的数据
docker exec mongo1 mongo --host 192.168.45.141 --port 27017 -u cc -p 'cc123456' --authenticationDatabase cmdb cmdb --eval 'db.cc_ObjectBase_0_pub_subsys.find({bk_inst_id: NumberLong(113)})'
```

### 数据关系说明

```
业务(bk_biz_id=3)
    └── 应用系统(cc_ObjectBase_0_pub_sys)
            ├── bk_inst_id: 112
            ├── bk_inst_name: "测试应用系统"
            ├── bk_parent_id: 3 (指向业务)
            └── 应用节点(cc_ObjectBase_0_pub_subsys)
                    ├── bk_inst_id: 113
                    ├── bk_inst_name: "测试应用节点"
                    └── bk_parent_id: 112 (指向应用系统的实例ID)
```

### 字段说明

| 字段名                   | 说明      | 示例值                |
| --------------------- | ------- | ------------------ |
| `bk_inst_id`          | 实例ID，自增 | 112, 113           |
| `bk_obj_id`           | 模型ID    | "sys", "subsys"    |
| `bk_parent_id`        | 父级实例ID  | 3(业务), 112(应用系统)   |
| `bk_supplier_account` | 供应商账号   | "0"                |
| `bk_biz_id`           | 业务ID    | 3                  |
| `bk_inst_name`        | 实例名称    | "测试应用系统", "测试应用节点" |
| `create_time`         | 创建时间    | ISODate            |
| `last_time`           | 最后更新时间  | ISODate            |

***

## 自动化插入脚本（推荐）

### 使用方案四：完整的父子关系插入

**操作时间**: 2026-03-31

#### 插入应用系统及其子节点（函数封装）

```Shell
# AI: 使用函数封装方式插入1个sys和2个subsys，自动处理ID分配和父子关系
docker exec mongo1 mongo --host 192.168.45.141 --port 27017 -u cc -p 'cc123456' --authenticationDatabase cmdb cmdb --eval '
// AI: 插入应用系统及其子节点
function insertSysAndSubsys(bizId, sysName, subsysNames) {
    var now = new Date();
    var results = { sys: null, subsys: [] };
    
    // AI: 获取 sys ID
    var sysSeq = db.cc_idgenerator.findOneAndUpdate(
        { _id: "cc_ObjectBase" },
        { $inc: { SequenceID: NumberLong(1) }, $set: { last_time: now } },
        { returnNewDocument: true }
    );
    var sysId = sysSeq.SequenceID;
    
    // AI: 插入 sys
    db.cc_ObjectBase_0_pub_sys.insertOne({
        bk_inst_id: NumberLong(sysId),
        bk_obj_id: "sys",
        bk_parent_id: NumberLong(bizId),
        bk_supplier_account: "0",
        bk_biz_id: NumberLong(bizId),
        bk_inst_name: sysName,
        create_time: now,
        last_time: now
    });
    results.sys = sysId;
    print("应用系统插入成功，ID: " + sysId);
    
    // AI: 批量获取 subsys IDs
    if (subsysNames && subsysNames.length > 0) {
        var subsysSeq = db.cc_idgenerator.findOneAndUpdate(
            { _id: "cc_ObjectBase" },
            { $inc: { SequenceID: NumberLong(subsysNames.length) }, $set: { last_time: now } },
            { returnNewDocument: true }
        );
        var endId = subsysSeq.SequenceID;
        var startId = endId - subsysNames.length + 1;
        
        // AI: 插入 subsys
        for (var i = 0; i < subsysNames.length; i++) {
            var subsysId = startId + i;
            db.cc_ObjectBase_0_pub_subsys.insertOne({
                bk_inst_id: NumberLong(subsysId),
                bk_obj_id: "subsys",
                bk_parent_id: NumberLong(sysId),  // AI: 指向父级 sys
                bk_supplier_account: "0",
                bk_biz_id: NumberLong(bizId),
                bk_inst_name: subsysNames[i],
                create_time: now,
                last_time: now
            });
            results.subsys.push({ id: subsysId, name: subsysNames[i] });
            print("  应用节点插入成功，ID: " + subsysId + "，父级: " + sysId);
        }
    }
    
    return results;
}

// AI: 使用示例：插入一个系统及其两个子节点
insertSysAndSubsys(3, "订单管理系统", ["订单服务", "支付服务"]);
'
```

延伸方案：

```Shell
#  AI: 保存到 /home/cmdb/insert_utils.js
#  然后加载使用：load("/home/cmdb/insert_utils.js")
#  AI: 使用示例
docker exec mongo1 mongo --host 192.168.45.141 --port 27017 -u cc -p 'cc123456' --authenticationDatabase cmdb cmdb --eval '
load("/home/cmdb/insert_utils.js");
insertSysAndSubsys(3, "测试系统", ["节点1", "节点2"]);
'
```

#### 验证插入的数据

```Shell
# AI: 验证应用系统数据
docker exec mongo1 mongo --host 192.168.45.141 --port 27017 -u cc -p 'cc123456' --authenticationDatabase cmdb cmdb --eval 'db.cc_ObjectBase_0_pub_sys.find({bk_inst_id: NumberLong(123)})'

# AI: 验证应用节点数据（按父级ID查询）
docker exec mongo1 mongo --host 192.168.45.141 --port 27017 -u cc -p 'cc123456' --authenticationDatabase cmdb cmdb --eval 'db.cc_ObjectBase_0_pub_subsys.find({bk_parent_id: NumberLong(123)})'
```

#### 数据关系图

```
业务(bk_biz_id=3)
    └── 应用系统(cc_ObjectBase_0_pub_sys)
            ├── bk_inst_id: 123
            ├── bk_inst_name: "订单管理系统"
            ├── bk_parent_id: 3 (指向业务)
            └── 应用节点(cc_ObjectBase_0_pub_subsys)
                    ├── bk_inst_id: 124
                    ├── bk_inst_name: "订单服务"
                    ├── bk_parent_id: 123 (指向订单管理系统)
                    └── 应用节点(cc_ObjectBase_0_pub_subsys)
                            ├── bk_inst_id: 125
                            ├── bk_inst_name: "支付服务"
                            └── bk_parent_id: 123 (指向订单管理系统)
```

### 关键要点

1. **原子递增**: 使用 `findOneAndUpdate` + `$inc` 保证 ID 唯一性
2. **序列共享**: 所有 `cc_ObjectBase_*_pub_*` 表共享 `cc_ObjectBase` 序列
3. **父子关联**: `subsys` 的 `bk_parent_id` 指向 `sys` 的 `bk_inst_id`
4. **批量获取**: 子节点批量获取 ID，减少数据库操作次数

