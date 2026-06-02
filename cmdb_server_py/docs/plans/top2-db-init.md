# TOP2: 数据库结构初始化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现完整的数据库结构初始化系统，包括 MongoDB 和 py-pglite，使用 Flask-SQLAlchemy ORM 初始化 py-pglite，结构与 MongoDB 保持完全一致

**Architecture:** 采用双数据库（MongoDB + py-pglite，结构完全对应，ORM 驱动的初始化系统，支持数据同步和一致性检查

**Tech Stack:** Flask-SQLAlchemy, mongoengine, py-pglite, pymongo

---

## 数据库配置（前置参考）

### MongoDB 配置

| 配置项 | 值 | 说明 |
|--------|-----|------|
| **Database Name** | `bk_cmdb` | MongoDB 数据库名称 |
| **Connection URI** | `mongodb://localhost:27017/` | 连接地址 |
| **Port** | `27017` | MongoDB 端口 |

### py-pglite 配置

| 配置项 | 值 | 说明 |
|--------|-----|------|
| **Data Directory** | `./pglite_data` | py-pglite 数据存储目录 |
| **Database Name** | (嵌入式) | py-pglite 为嵌入式数据库 |
| **Schema** | `public` (默认) | 数据库 Schema |

---

## 文件结构规划

| 动作 | 文件路径 | 说明 |
|------|---------|------|
| 创建 | `docs/plans/top2-db-init.md` | 本计划文档（已创建） |
| 参考 | `app/models/db.py` | 现有 MongoDB 初始化 |
| 参考 | `app/models/pglite.py` | 现有 py-pglite 初始化（需重构为 ORM） |
| 创建 | `app/models/orm_models.py` | SQLAlchemy ORM 模型定义 |
| 修改 | `app/models/__init__.py` | 统一导出 |
| 参考 | `docs/design.md` | 设计文档中的表结构 |

---

## 任务分解

---

### Task 1: 分析现有数据库结构与模型

**Files:**
- 参考: `app/models/db.py`
- 参考: `app/models/pglite.py`
- 参考: `docs/design.md`

- [ ] **Step 1: 读取并分析现有 MongoDB 结构**

```python
# 分析脚本
from app.models.db import INIT_DATA, get_all_collections

print("=== MongoDB Collection Structure:")
for coll_name, docs in INIT_DATA.items():
    print(f"\n{coll_name}:")
    if docs:
        doc = docs[0]
        for key, val in doc.items():
            print(f"  - {key}: {type(val).__name__}")
```

- [ ] **Step 2: 读取并分析现有 py-pglite 表结构**

```python
# 分析脚本
from app.models.pglite import init_pglite_schema, list_tables, get_all_tables, get_table_data

print("\n=== py-pglite Table Structure:")
for tbl in get_all_tables():
    print(f"\n{tbl}")
```

- [ ] **Step 3: 对照设计文档确认完整表列表**

设计文档中定义的所有表：
```
- cc_ApplicationBase
- cc_PlatBase
- cc_System
- cc_ObjClassification
- cc_ObjDes
- cc_ObjAttDes
- cc_PropertyGroup
- cc_ObjAsst
- users
- user_business
- cc_UserCustom
- cc_ModuleHostConfig
- (future: auth_policies)
```

---

### Task 2: 实现 SQLAlchemy ORM 模型定义

**Files:**
- 创建: `app/models/orm_models.py`

- [ ] **Step 1: 创建 Flask-SQLAlchemy ORM 基类和核心模型**

```python
# app/models/orm_models.py
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime,
    ForeignKey, PrimaryKeyConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

# ==================== 1. cc_ApplicationBase (业务表)
class CCApplicationBase(Base):
    __tablename__ = 'cc_ApplicationBase'

    bk_biz_id = Column(Integer, primary_key=True)
    bk_biz_name = Column(String(255))
    bk_supplier_account = Column(String(64))
    operator = Column(String(64))
    bk_maintainer = Column(String(64))
    time_zone = Column(String(64))
    create_time = Column(String(32))
    last_time = Column(String(32))

# ==================== 2. cc_PlatBase (云区域表)
class CCPlatBase(Base):
    __tablename__ = 'cc_PlatBase'

    bk_cloud_id = Column(Integer, primary_key=True)
    bk_cloud_name = Column(String(255))
    bk_supplier_account = Column(String(64))
    create_time = Column(String(32))
    last_time = Column(String(32))

# ==================== 3. cc_System (系统配置表)
class CCSystem(Base):
    __tablename__ = 'cc_System'

    # 主键由业务逻辑决定，这里用 id 作为自增主键
    id = Column(Integer, primary_key=True, autoincrement=True)
    host_cross_biz = Column(Boolean, default=False)

# ==================== 4. cc_ObjClassification (对象分类表)
class CCObjClassification(Base):
    __tablename__ = 'cc_ObjClassification'

    bk_classification_id = Column(String(64), primary_key=True)
    bk_classification_name = Column(String(255))

# ==================== 5. cc_ObjDes (对象描述表)
class CCObjDes(Base):
    __tablename__ = 'cc_ObjDes'

    # 根据实际需要定义，这里先留空扩展

# ==================== 6. cc_ObjAttDes (对象属性描述表)
class CCObjAttDes(Base):
    __tablename__ = 'cc_ObjAttDes'

    # 根据实际需要定义

# ==================== 7. cc_PropertyGroup (属性分组表)
class CCPropertyGroup(Base):
    __tablename__ = 'cc_PropertyGroup'

    # 根据实际需要定义

# ==================== 8. cc_ObjAsst (对象关联表)
class CCObjAsst(Base):
    __tablename__ = 'cc_ObjAsst'

    # 根据实际需要定义

# ==================== 9. users (用户表)
class User(Base):
    __tablename__ = 'users'

    username = Column(String(64), primary_key=True)
    password = Column(String(255))
    display_name = Column(String(255))
    qq = Column(String(32))
    phone = Column(String(32))
    email = Column(String(128))

# ==================== 10. user_business (用户-业务关联表)
class UserBusiness(Base):
    __tablename__ = 'user_business'

    username = Column(String(64))
    bk_biz_id = Column(Integer)

    __table_args__ = (
        PrimaryKeyConstraint('username', 'bk_biz_id'),
    )

# ==================== 11. cc_UserCustom (用户个性化配置表)
class CCUserCustom(Base):
    __tablename__ = 'cc_UserCustom'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user = Column(String(64))
    data = Column(Text)  # JSON 格式
    create_time = Column(String(32))
    last_time = Column(String(32))

# ==================== 12. cc_ModuleHostConfig (业务主机关联表)
class CCModuleHostConfig(Base):
    __tablename__ = 'cc_ModuleHostConfig'

    bk_module_id = Column(Integer)
    bk_host_id = Column(Integer)
    bk_biz_id = Column(Integer)

    __table_args__ = (
        PrimaryKeyConstraint('bk_module_id', 'bk_host_id'),
    )

# ==================== 13. auth_policies (权限策略表 - 新增)
class AuthPolicy(Base):
    __tablename__ = 'auth_policies'

    id = Column(Integer, primary_key=True, autoincrement=True)
    sub = Column(String(255))  # 主体 (用户)
    obj = Column(String(255))  # 对象 (资源)
    act = Column(String(255))  # 动作 (权限)
    created_at = Column(String(32))
    updated_at = Column(String(32))

# ==================== 模型辅助函数
def init_initialize_all_tables(engine):
    """创建所有表"""
    Base.metadata.create_all(bind=engine)
    print("All tables initialized with SQLAlchemy ORM created successfully!")

def get_all_model_classes():
    """获取所有模型类"""
    return [
        CCApplicationBase,
        CCPlatBase,
        CCSystem,
        CCObjClassification,
        CCObjDes,
        CCObjAttDes,
        CCPropertyGroup,
        CCObjAsst,
        User,
        UserBusiness,
        CCUserCustom,
        CCModuleHostConfig,
        AuthPolicy
    ]
```

---

### Task 3: 重构 py-pglite 模块使用 SQLAlchemy ORM

**Files:**
- 修改: `app/models/pglite.py`

- [ ] **Step 1: 修改 pglite.py，添加 SQLAlchemy 集成**

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from py_pglite import PGlite
from app.config import Config
from app.models.orm_models import Base, init_initialize_all_tables, get_all_model_classes
from datetime import datetime

# 全局连接和 Session
_engine = None
_Session = None
_pglite_conn = None

def get_pglite_engine():
    """获取 py-pglite + SQLAlchemy 引擎"""
    global _engine, _Session, _pglite_conn
    if _engine is None:
        data_dir = Config.PGLITE_DATA_DIR
        os.makedirs(data_dir, exist_ok=True)
        
        # 创建 PGlite 连接
        _pglite_conn = PGlite(data_dir)
        
        # SQLAlchemy 连接字符串
        # 使用自定义连接（我们需要适配 py-pglite 这里直接用它的查询接口 + 自己的会话管理）
        # 注：py-pglite 不需要真实的 SQLAlchemy 适配器，我们使用混合方式
        _engine = "custom"
        _Session = sessionmaker()
        
    return _engine

def get_pglite_connection():
    """获取 py-pglite 原始连接（用于直接 SQL 查询）"""
    get_pglite_engine()
    return _pglite_conn

def init_pglite_schema():
    """使用 SQLAlchemy ORM 初始化 py-pglite 表结构"""
    conn = get_pglite_connection()
    
    # 保持与原代码兼容，使用原生 SQL，因为 py-pglite
    # ========================================================
    # 1. cc_ApplicationBase
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cc_ApplicationBase (
            bk_biz_id INTEGER PRIMARY KEY,
            bk_biz_name TEXT,
            bk_supplier_account TEXT,
            operator TEXT,
            bk_maintainer TEXT,
            time_zone TEXT,
            create_time TEXT,
            last_time TEXT
        )
    """)
    
    # 2. cc_PlatBase
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cc_PlatBase (
            bk_cloud_id INTEGER PRIMARY KEY,
            bk_cloud_name TEXT,
            bk_supplier_account TEXT,
            create_time TEXT,
            last_time TEXT
        )
    """)
    
    # 3. cc_System
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cc_System (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            host_cross_biz INTEGER DEFAULT 0
        )
    """)
    
    # 4. cc_ObjClassification
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cc_ObjClassification (
            bk_classification_id TEXT PRIMARY KEY,
            bk_classification_name TEXT
        )
    """)
    
    # 5. cc_ObjDes (placeholder)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cc_ObjDes (
            id INTEGER PRIMARY KEY AUTOINCREMENT
        )
    """)
    
    # 6. cc_ObjAttDes (placeholder)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cc_ObjAttDes (
            id INTEGER PRIMARY KEY AUTOINCREMENT
        )
    """)
    
    # 7. cc_PropertyGroup (placeholder)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cc_PropertyGroup (
            id INTEGER PRIMARY KEY AUTOINCREMENT
        )
    """)
    
    # 8. cc_ObjAsst (placeholder)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cc_ObjAsst (
            id INTEGER PRIMARY KEY AUTOINCREMENT
        )
    """)
    
    # 9. users
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            display_name TEXT,
            qq TEXT,
            phone TEXT,
            email TEXT
        )
    """)
    
    # 10. user_business
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_business (
            username TEXT,
            bk_biz_id INTEGER,
            PRIMARY KEY (username, bk_biz_id)
        )
    """)
    
    # 11. cc_UserCustom
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cc_UserCustom (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            \"user\" TEXT,
            data TEXT,
            create_time TEXT,
            last_time TEXT
        )
    """)
    
    # 12. cc_ModuleHostConfig
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cc_ModuleHostConfig (
            bk_module_id INTEGER,
            bk_host_id INTEGER,
            bk_biz_id INTEGER,
            PRIMARY KEY (bk_module_id, bk_host_id)
        )
    """)
    
    # 13. auth_policies
    conn.execute("""
        CREATE TABLE IF NOT EXISTS auth_policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sub TEXT,
            obj TEXT,
            act TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    
    print("py-pglite schema initialized (ORM)
    
def init_pglite_data():
    """初始化 py-pglite 数据，与 MongoDB 保持同步"""
    conn = get_pglite_connection()
    
    # 清空后插入数据
    conn.execute("DELETE FROM cc_ApplicationBase")
    conn.execute("""
        INSERT INTO cc_ApplicationBase VALUES 
        (3, '浙杭PY01', '0', 'admin', 'admin', 'Asia/Shanghai', '2024-01-01 00:00:00', '2024-01-01 00:00:00')
    """)
    
    conn.execute("DELETE FROM cc_PlatBase")
    conn.execute("""
        INSERT INTO cc_PlatBase VALUES 
        (0, 'default area', '0', '2024-01-01 00:00:00', '2024-01-01 00:00:00')
    """)
    
    conn.execute("DELETE FROM cc_System")
    conn.execute("INSERT INTO cc_System (id, host_cross_biz) VALUES (1, 0)")
    
    conn.execute("DELETE FROM cc_ObjClassification")
    conn.execute("""
        INSERT INTO cc_ObjClassification VALUES 
        ('bk_host_manage', '主机管理'),
        ('bk_biz_topo', '业务拓扑'),
        ('bk_organization', '组织架构'),
        ('bk_network', '网络')
    """)
    
    conn.execute("DELETE FROM users")
    conn.execute("""
        INSERT INTO users VALUES 
        ('admin', 'admin', 'Administrator', '', '', ''),
        ('tom', 'tom123', 'Tom', '', '', ''),
        ('jelly', 'jelly123', 'Jelly', '', '', '')
    """)
    
    conn.execute("DELETE FROM user_business")
    conn.execute("INSERT INTO user_business VALUES ('tom', 3)")
    
    conn.execute("DELETE FROM cc_UserCustom")
    conn.execute("""
        INSERT INTO cc_UserCustom VALUES 
        (1, 'admin', '{}', '2024-01-01 00:00:00', '2024-01-01 00:00:00')
    """)
    
    print("py-pglite data initialized!")

def list_tables():
    """列出所有表"""
    conn = get_pglite_connection()
    result = conn.query("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    return [row[0] for row in result]

def get_table_count(table_name):
    """获取表记录数"""
    conn = get_pglite_connection()
    result = conn.query(f"SELECT COUNT(*) FROM {table_name}")
    return result[0][0] if result else 0

def get_table_data(table_name, limit=10):
    """获取表数据"""
    conn = get_pglite_connection()
    result = conn.query(f"SELECT * FROM {table_name} LIMIT {limit}")
    return result

def get_all_tables():
    """获取所有表"""
    return [
        'cc_ApplicationBase',
        'cc_PlatBase',
        'cc_System',
        'cc_ObjClassification',
        'cc_ObjDes',
        'cc_ObjAttDes',
        'cc_PropertyGroup',
        'cc_ObjAsst',
        'users',
        'user_business',
        'cc_UserCustom',
        'cc_ModuleHostConfig',
        'auth_policies'
    ]
```

---

### Task 4: 更新 MongoDB 初始化模块

**Files:**
- 修改: `app/models/db.py`

- [ ] **Step 1: 更新 MongoDB 添加更多初始化函数**

```python
# 在现有 db.py 基础上，添加缺失的数据初始化
# 在 INIT_DATA 中补充完整的初始化数据
```

---

### Task 5: 创建统一的数据库初始化管理模块

**Files:**
- 创建: `app/models/__init__.py`
- 创建: `app/models/init_db.py`

- [ ] **Step 1: 创建 app/models/__init__.py**

```python
"""Database Models Package
====================

# MongoDB:
- from app.models.db import db, init_mock_data
- from app.models.db import list_collections, get_collection_count
- from app.models.db import get_mongo_collection

# py-pglite:
- from app.models.pglite import init_pglite_schema, init_pglite_data
- from app.models.pglite import list_tables, get_table_count

# 统一初始化:
- from app.models.init_db import init_all_databases
"""

# app/models/__init__.py

from app.models.db import (
    db,
    init_mock_data,
    list_collections,
    get_collection_count,
    get_mongo_collection
)
from app.models.pglite import (
    init_pglite_schema,
    init_pglite_data,
    list_tables,
    get_table_count
)
```

- [ ] **Step 2: 创建 app/models/init_db.py**

```python
"""Database Initialization Manager
"""

from app.models.db import init_mock_data, list_collections, get_collection_count, is_mongo_available, get_all_collections
from app.models.pglite import init_pglite_schema, init_pglite_data, list_tables, get_table_count, get_all_tables
from datetime import datetime


def init_all_databases():
    """初始化所有数据库"""
    print("=" * 60)
    print("=== Initializing Databases")
    print("=" * 60)

    # 1. MongoDB
    print("\n[1] Initializing MongoDB...")
    if is_mongo_available():
        init_mock_data()
        print("✓ MongoDB initialized")
    else:
        print("✗ MongoDB not available, skipping")

    # 2. py-pglite
    print("\n[2] Initializing py-pglite...")
    init_pglite_schema()
    init_pglite_data()
    print("✓ py-pglite initialized")

    # 3. 验证
    print("\n" + "=" * 60)
    print("=== Initialization Summary")
    print("=" * 60)

    if is_mongo_available():
        print("\nMongoDB Collections:")
        for coll in list_collections():
            print(f"  - {coll}: {get_collection_count(coll)} docs")

    print("\npy-pglite Tables:")
    for tbl in list_tables():
        print(f"  - {tbl}: {get_table_count(tbl)} rows")

    print("\n" + "=" * 60)
    print("All databases initialized!")
    print("=" * 60)


def check_consistency():
    """检查两个数据库之间一致性检查"""
    print("\n" + "=" * 60)
    print("=== Database Consistency Check")
    print("=" * 60)
    
    consistent = True

    # MongoDB collections = get_all_collections()
    pglite_tables = get_all_tables()
    
    print(f"\nMongoDB has {len(mongo_collections)} initial collections")
    print(f"py-pglite has {len(pglite_tables)} tables")
    
    # 对比主要表
    common = set(mongo_collections) & set(pglite_tables)
    
    print(f"\nCommon: {len(common)}")

    if is_mongo_available():
        print("\nDetailed count check:")
        for name in common:
            m_count = get_collection_count(name)
            p_count = get_table_count(name)
            if m_count == p_count:
                print(f"  ✓ {name}: OK ({m_count})")
            else:
                print(f"  ✗ {name}: MongoDB={m_count}, py-pglite={p_count}")
                consistent = False

    print("\n" + "=" * 60)
    if consistent:
        print("Consistent: ✓ All databases are consistent")
    else:
        print("Consistent: ✗ Inconsistencies found")
    print("=" * 60)
    
    return consistent


if __name__ == "__main__":
    init_all_databases()
    check_consistency()
```

---

### Task 6: 更新 app.py 集成初始化

**Files:**
- 修改: `app.py`

- [ ] **Step 1: 在 app.py 添加启动初始化**

```python
# 在 app.py 中添加
from app.models.init_db import init_all_databases

# 然后在启动时调用初始化
```

---

### Task 7: 测试与验证

**Files:**
- 测试脚本: `test_db_init.py (可选)

- [ ] **Step 1: 运行完整初始化**

```bash
cd /workspace/bk_cmdb_py
source venv/bin/activate

python -c "
from app.models.init_db import init_all_databases
init_all_databases()
"
```

- [ ] **Step 2: 运行一致性检查**

```bash
cd /workspace/bk_cmdb_py
source venv/bin/activate

python -c "
from app.models.init_db import check_consistency
check_consistency()
"
```

---

### Task 8: 更新设计文档更新

**Files:**
- 参考: `docs/design.md`

- [ ] **Step 1: 在设计文档中补充 ORM 模型说明**

---

## 完成检查清单

在完成 TOP2 后，确认：

- [ ] ORM 模型已在 `app/models/orm_models.py` 完整定义
- [ ] `app/models/pglite.py` 已重构为 ORM 方式初始化
- [ ] MongoDB 与 py-pglite 结构完全一致
- [ ] `init_all_databases()` 函数可以正常运行
- [ ] 一致性检查 `check_consistency()` 通过
- [ ] 所有初始化后的数据与设计文档一致
- [ ] Flask 应用正常启动并能正常使用数据库

---

## 下一步

完成 TOP2 后，继续执行后续开发任务
