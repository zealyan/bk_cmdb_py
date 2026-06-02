"""Relational Database Module

关系型数据库模块（PostgreSQL/py-pglite），使用 SQLAlchemy 统一接口。
同时兼容 py-pglite（开发环境）和 PostgreSQL（生产环境）。

Design Principles:
    1. 使用 SQLAlchemy ORM 作为主要接口
    2. 保持与 MongoDB 集合名一致的表名
    3. 所有 SQL 使用标准 PostgreSQL 语法

Usage:
    # 获取连接
    from app.models.relational_db import get_session, execute
    
    session = get_session()
    result = session.query(User).all()
    
    # 或使用原生 SQL
    result = execute("SELECT * FROM users WHERE username = :username", {"username": "admin"})

Tables (与 MongoDB 集合名保持一致):
    - cc_ApplicationBase: 业务表
    - cc_PlatBase: 云区域表
    - cc_System: 系统配置表
    - cc_ObjClassification: 对象分类表
    - users: 用户表
    - user_business: 用户-业务关联表
    - cc_UserCustom: 用户个性化配置表
    - auth_policies: 权限策略表
"""

from typing import List, Dict, Any, Optional
from sqlalchemy import text, inspect
from app.models.database import (
    get_engine,
    get_session,
    get_connection,
    execute as db_execute,
    DatabaseFactory
)
from app.auth import hash_password


def get_table_count(table_name: str) -> int:
    """获取表记录数
    
    Args:
        table_name (str): 表名
        
    Returns:
        int: 记录数
    """
    result = db_execute(f"SELECT COUNT(*) FROM {table_name}")
    return result[0][0] if result else 0


def get_table_data(table_name: str, limit: int = 10) -> List:
    """获取表数据
    
    Args:
        table_name (str): 表名
        limit (int): 返回记录数限制
        
    Returns:
        List: 表数据列表
    """
    return db_execute(f"SELECT * FROM {table_name} LIMIT {limit}")


def list_tables() -> List[str]:
    """列出所有表
    
    Returns:
        List[str]: 表名列表
    """
    return DatabaseFactory.list_tables()


def table_exists(table_name: str) -> bool:
    """检查表是否存在
    
    Args:
        table_name (str): 表名
        
    Returns:
        bool: 表是否存在
    """
    return DatabaseFactory.table_exists(table_name)


def init_relational_schema():
    """初始化关系型数据库表结构
    
    使用原生 SQL 创建表，与 MongoDB 集合名保持一致。
    """
    conn = get_connection()
    
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS cc_ApplicationBase (
            bk_biz_id INTEGER PRIMARY KEY,
            bk_biz_name TEXT,
            bk_supplier_account TEXT,
            operator TEXT,
            bk_maintainer TEXT,
            time_zone TEXT,
            create_time TEXT,
            last_time TEXT,
            bk_data_status TEXT DEFAULT 'enabled'
        )
    """))
    
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS cc_PlatBase (
            bk_cloud_id INTEGER PRIMARY KEY,
            bk_cloud_name TEXT,
            bk_supplier_account TEXT,
            create_time TEXT,
            last_time TEXT
        )
    """))
    
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS cc_System (
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            host_cross_biz INTEGER DEFAULT 0
        )
    """))
    
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS cc_ObjClassification (
            bk_classification_id TEXT PRIMARY KEY,
            bk_classification_name TEXT
        )
    """))
    
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS cc_ObjDes (
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY
        )
    """))
    
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS cc_ObjAttDes (
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY
        )
    """))
    
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS cc_PropertyGroup (
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY
        )
    """))
    
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS cc_ObjAsst (
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY
        )
    """))
    
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            display_name TEXT,
            qq TEXT,
            phone TEXT,
            email TEXT
        )
    """))
    
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS user_business (
            username TEXT,
            bk_biz_id INTEGER,
            PRIMARY KEY (username, bk_biz_id)
        )
    """))
    
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS cc_UserCustom (
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            "user" TEXT,
            data TEXT,
            create_time TEXT,
            last_time TEXT
        )
    """))
    
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS cc_ModuleHostConfig (
            bk_module_id INTEGER,
            bk_host_id INTEGER,
            bk_biz_id INTEGER,
            PRIMARY KEY (bk_module_id, bk_host_id)
        )
    """))
    
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS auth_policies (
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            sub TEXT,
            obj TEXT,
            act TEXT,
            sub_type TEXT DEFAULT 'user',
            obj_id TEXT,
            effect TEXT DEFAULT 'allow',
            created_at TEXT,
            updated_at TEXT
        )
    """))
    
    conn.commit()
    print("关系型数据库表结构初始化完成")


def init_relational_data():
    """初始化关系型数据库数据
    
    插入初始数据，与 MongoDB 保持同步。
    """
    execute = db_execute
    
    execute("DELETE FROM cc_ApplicationBase")
    execute("""
        INSERT INTO cc_ApplicationBase VALUES 
        (2, '蓝鲸', '0', 'admin', 'admin', 'Asia/Shanghai', '2024-01-01 00:00:00', '2024-01-01 00:00:00', 'enabled'),
        (3, '浙杭PY01', '0', 'admin', 'admin', 'Asia/Shanghai', '2024-01-01 00:00:00', '2024-01-01 00:00:00', 'enabled'),
        (4, '测试业务1', '0', 'tom', 'tom', 'Asia/Shanghai', '2024-01-02 00:00:00', '2024-01-02 00:00:00', 'enabled'),
        (5, '测试业务2', '0', 'jelly', 'jelly', 'Asia/Shanghai', '2024-01-03 00:00:00', '2024-01-03 00:00:00', 'enabled')
    """)
    
    execute("DELETE FROM cc_PlatBase")
    execute("""
        INSERT INTO cc_PlatBase VALUES 
        (0, 'default area', '0', '2024-01-01 00:00:00', '2024-01-01 00:00:00')
    """)
    
    execute("DELETE FROM cc_System")
    execute("INSERT INTO cc_System (host_cross_biz) VALUES (0)")
    
    execute("DELETE FROM cc_ObjClassification")
    execute("""
        INSERT INTO cc_ObjClassification VALUES 
        ('bk_host_manage', '主机管理'),
        ('bk_biz_topo', '业务拓扑'),
        ('bk_organization', '组织架构'),
        ('bk_network', '网络')
    """)
    
    execute("DELETE FROM users")
    execute("""
        INSERT INTO users VALUES 
        ('admin', :admin_pwd, 'Administrator', '', '', ''),
        ('tom', :tom_pwd, 'Tom', '', '', ''),
        ('jelly', :jelly_pwd, 'Jelly', '', '', '')
    """, {
        'admin_pwd': hash_password("admin"),
        'tom_pwd': hash_password("tom123"),
        'jelly_pwd': hash_password("jelly123")
    })
    
    execute("DELETE FROM user_business")
    execute("""
        INSERT INTO user_business VALUES 
        ('tom', 2),
        ('tom', 3),
        ('tom', 4),
        ('jelly', 2),
        ('jelly', 5)
    """)
    
    execute("DELETE FROM cc_UserCustom")
    execute("""
        INSERT INTO cc_UserCustom ("user", data, create_time, last_time) VALUES 
        ('admin', '{}', '2024-01-01 00:00:00', '2024-01-01 00:00:00')
    """)
    
    print("关系型数据库数据初始化完成")


def get_all_tables() -> List[str]:
    """获取所有需要初始化的表名
    
    Returns:
        List[str]: 表名列表
    """
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


def reset_database():
    """重置数据库连接
    
    用于切换环境或重新初始化。
    """
    DatabaseFactory.reset()
