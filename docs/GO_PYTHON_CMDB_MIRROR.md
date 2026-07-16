# Go 工程目录结构 vs Python 复刻对照

> 目标：在 `bk-cmdb-release-v3.10.50/src` 与 `cmdb_server_py/` 之间，逐包核对
> **公共工具 / 类库 / 函数库** 是否已在 Python 侧实现，并标注 Go 的 MongoDB
> **连接 / 操作 / 资源使用** 中哪些性能提升逻辑已被复刻。
>
> 结论速览：
> - **目录镜像**：Go `common/` 的 11 个核心子包 + `storage/dal/mongo` + `storage/driver/mongodb`
>   已在 `cmdb_server_py/app/common/` 下 1:1 落位（见 §1）。
> - **MongoDB 性能逻辑**：连接池、超时、操作指标、读偏好、原子序列、重复键分类
>   全部复刻（见 §2）。
> - **本次新增（纯 Python 包）**：`version` / `mapstruct` / `selector` 已完整复刻并测试（见 §1.1）。
> - **按决策不复刻**：`zkclient`、`storage/driver/redis`、`common/lock`、`watch`/`stream`/`reflector`
>   依赖 ZooKeeper / Redis / 事件流，超出最小依赖部署范围（见 §1.1 标注 ⏸ 与文末说明）。

---

## §1 目录结构对照（公共工具 / 类库 / 函数库）

### 1.1 Go `common/*` → Python `app/common/*`

| Go 包（`src/common/...`） | Python 模块 | 状态 | 说明 |
|---|---|---|---|
| `common/blog` | `app/common/blog` | ✅ 已实现 | `Infof/Errorf/Warnf/V(level).Infof` 封装标准库 logging |
| `common/condition` | `app/common/condition` | ✅ 已实现 | `Condition` 构建器：`Eq/Ne/In/Nin/Gt/Gte/Lt/Lte/Regex` → `to_filter()` |
| `common/errors` | `app/common/errors` | ✅ 已实现 | `is_duplicated_error` / `get_duplicate_key` / `is_not_found_error`（移植自 `mongod.go`） |
| `common/json` | （Python 内置 `json`） | ➖ 等价 | 语言级能力，无需独立包 |
| `common/lock` | — | ⏸ 未复刻 | 分布式锁，依赖 Redis（本次决策：不复制 Redis 层，故 lock 一并跳过） |
| `common/mapstr` | `app/common/mapstr` | ✅ 已实现 | `MapStr(dict)` 的 `String/Bool/Int64/MapStr` 访问器 |
| `common/mapstruct` | `app/common/mapstruct` | ✅ 已实现 | `struct_to_map` / `map_to_struct` / `map_to_struct_with_hook`（含 duration 钩子） |
| `common/metadata` | `app/common/types` | 🟡 部分 | 以 `types` 常量 + 哨兵错误 + 读偏好枚举承载（非全量） |
| `common/metric`, `common/metrics` | `app/common/metric` | ✅ 已实现 | `MongoMetrics`：按 `(集合,操作)` 累计次数/耗时/错误，线程安全 |
| `common/paraparse` | `app/common/querybuilder` | 🟡 部分 | 查询解析能力收敛进 `build_filter/build_sort/build_projection` |
| `common/querybuilder` | `app/common/querybuilder` | ✅ 已实现 | `build_filter` / `build_sort` / `build_projection` |
| `common/selector` | `app/common/selector` | ✅ 已实现 | `Selector`/`Selectors`/`Labels` 校验 + `to_mgo_filter`（labels 选择器→Mongo） |
| `common/types` | `app/common/types` | ✅ 已实现 | 哨兵错误、读偏好枚举、集合名常量 |
| `common/util` | `app/common/util` | ✅ 已实现 | `conver_to_interface_slice` / `get_int32_by_interface` 移植 |
| `common/version` | `app/common/version` | ✅ 已实现 | 版本常量 + `get_version` / `show_version` |
| `common/watch` | — | ⏸ 未复刻 | 事件 watch 流（依赖 `storage/stream`，超出最小部署范围） |
| `common/webservice` | （Flask Blueprint） | ➖ 等价 | 由 `app/routes/*` 的 Blueprint 承载 |
| `common/zkclient` | — | ⏸ 未复刻 | ZooKeeper 客户端（本次决策：zk/redis 均不复制） |
| `common/identification`, `common/auth`, `common/cryptor` | `app/auth/*` | 🟡 对应 | 鉴权在 `app/auth`（internal 模式），非 `common` 直译 |

### 1.2 Go `storage/*` → Python `app/common/mongo/*`

| Go 路径 | Python 模块 | 状态 | 说明 |
|---|---|---|---|
| `storage/dal/mongo/local/mongo.go` | `app/common/mongo/client.py` | ✅ 已实现 | `NewMgo` → `new_mgo`：连接池/超时/副本集/AppName/RetryWrites |
| `storage/dal/mongo/local/mongo.go`（`Collection`/`getCollectionOption`） | `app/common/mongo/collection.py` | ✅ 已实现 | `Collection` 封装 + 懒加载读偏好 |
| `storage/dal/mongo/config.go` | `app/common/mongo/conf.py` | ✅ 已实现 | `MongoConf` dataclass + 池常量别名 |
| `storage/dal/mongo/local/metric.go`（`mtc`） | `app/common/mongo/monitor.py` + `app/common/metric` | ✅ 已实现 | driver 层 `CommandListener` 自动采集所有命令 |
| `storage/dal/mongo/local/mongo.go`（`NextSequence/NextSequences`） | `app/common/mongo/sequence.py` | ✅ 已实现 | `find_one_and_update` `$inc` + `redirectTable` 分表重定向 |
| `storage/driver/mongodb` | `app/common/mongo/__init__.py` | ✅ 已实现 | 公共 API 再导出 |
| `storage/dal/types` | `app/common/dal/__init__.py` | 🟡 部分 | `new_rdb` → `new_mgo` 桥接 |
| `storage/dal/redis`, `storage/driver/redis` | — | ⏸ 未复刻 | Redis 驱动（本次决策：不复制 Redis 层；后续若启用 Redis 再补 `app/common/redis`） |
| `storage/reflector`, `storage/stream` | — | ⏸ 未复刻 | watch/事件流（超出最小部署范围） |

### 1.3 顶层模块对照

| Go 顶层 | Python 对应 | 状态 |
|---|---|---|
| `scene_server/admin_server` 等 | `app/routes/*` | 🟡 按服务拆分路由 |
| `apimachinery` | — | ⏸ 外部服务调用层（最小依赖下 BFF 已移除） |
| `framework` | `app/core/*` | 🟡 核心逻辑 |
| `web_server` | `ui_server.py` | 🟡 UI 入口/代理 |

**图例**：✅ 已实现　🟡 部分/对应　➖ 语言级等价　⏸ 未复刻（当前部署不需要）

> **本次复刻范围（用户决策）**：仅完整复刻**纯 Python 包** `version` / `mapstruct` / `selector`
> （无外部基础设施依赖，已通过功能测试）。`zkclient`（ZooKeeper）、`storage/driver/redis`、
> `common/lock`（依赖 Redis）、`watch` / `storage/stream` / `storage/reflector`（事件流）均**按决策跳过**，
> 因其依赖 ZooKeeper / Redis / 事件流，超出最小依赖部署目标。后续若启用 Redis 或事件同步，再补对应层。

---

## §2 Go MongoDB 性能逻辑复刻清单

| Go 性能逻辑（位置） | 复刻到 Python | 验证结果 |
|---|---|---|
| **连接池**：`MaxPoolSize=MaxOpenConns(默认1000,上限3000)` / `MinPoolSize=MaxIdleConns(默认50)` | `new_mgo` → `maxPoolSize=1000, minPoolSize=50` | ✅ `pool_options.max_pool_size=1000, min_pool_size=50` |
| **超时**：`ConnectTimeout=60s` / `SocketTimeout=10s(区间5~30)` / `MaxConnIdleTime=25min` | `connectTimeoutMS=60000, socketTimeoutMS=10000, maxIdleTimeMS=1500000` | ✅ `connect_timeout=60.0, socket_timeout=10.0` |
| **副本集**：`ReplicaSet` 必填 + `AppName` 标识 + `RetryWrites=false` | `replicaSet=rs0, appName=cmdb_server_py, retryWrites=False` | ✅ `replica_set_name=rs0, retry_writes=False` |
| **服务端选择超时**：`serverSelectionTimeoutMS=30s` | `serverSelectionTimeoutMS=30000` | ✅ |
| **每操作指标**：`mtc.collectOperCount/Duration/ErrorCount` 按 `(集合,操作)` | `MongoCommandListener` 在 driver 层自动记录 `record(coll,op,dur,err)` | ✅ 实时流量已采集：`cc_ApplicationBase/find`×6、`cc_HostBase/aggregate`×2 等 |
| **读偏好**：`getCollectionOption` 按 ctx 设 primary/preferred + `maxStaleness=90s` | `read_preference_ctx`(contextvars) + `read_preference_for_ctx()` | ✅ `SECONDARY_PREFERRED → SecondaryPreferred(max_staleness=90)` |
| **原子序列**：`NextSequence` 经 `findOneAndUpdate $inc` + `redirectTable` 分表 | `sequence.next_sequence` / `next_sequences` | ✅ 返回 1,2,3；批量 [1,2,3]；`cc_idgenerator` 文档 `_id=test_seq_letter, SequenceID=3` |
| **重复键分类**：`IsDuplicatedError` / `GetDuplicateKey` 解析 E11000 | `errors.is_duplicated_error` / `get_duplicate_key` | ✅ `DuplicateKeyError → True`，正确提取 `E11000 ... _id: 100` |
| **连接自检**：`client.Connect` 后 `ping` | `new_mgo` 内 `client.admin.command("ping")` | ✅ 启动时打印 “MongoDB 连接成功” |

---

## §3 复刻后 Python 调用路径

```
业务路由 (app/routes/*.py)
   │  db.cc_X  (app/models/db._LazyDatabase 代理)
   ▼
app/models/db.get_db_connection()           ← 兼容层，公共 API 不变
   ▼
app/common/mongo.client.new_mgo(conf)       ← 对齐 Go NewMgo（连接池/超时/副本集）
   │  MongoClient(event_listeners=[MongoCommandListener()])
   ▼
pymongo 驱动层  ──CommandListener──▶  app/common/metric.MongoMetrics.record()  (对齐 Go mtc)
   ▼
app/common/mongo.sequence.next_sequence()   ← 对齐 Go NextSequence（原子 $inc）
```

> **关键设计**：PyMongo 的 `Database.__getattr__` 会把任意属性访问当作集合名，
> 因此 `next_sequence` 必须用 `isinstance(conn, Mongo)` 精确区分包装类与
> `pymongo.Database`，而非 `hasattr(conn,"dbc")`（该判定对 Database 恒为真）。
> `db` 代理对象在每次访问时即时解析实时连接，故 `from app.models.db import db`
> 在导入期无需完成 MongoDB 连接即可被路由直接使用。

---

## §4 运维端点

| 端点 | 方法 | 作用 |
|---|---|---|
| `/api/v3/metrics/mongo` | GET | 导出 MongoDB 操作指标快照（对齐 Go mtc） |
| `/api/v3/metrics/mongo/reset` | POST | 清零指标 |

> 指标为进程级单例（`app/common/metric.get_metrics()`），随实时流量自动累积，
> 无需改动任何业务路由即可全量覆盖。
