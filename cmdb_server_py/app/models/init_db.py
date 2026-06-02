"""Database Initialization Manager

统一的数据库初始化管理模块。
提供 MongoDB 和关系型数据库（py-pglite/PostgreSQL）的统一初始化接口。

Design Principles:
    1. MongoDB 作为主数据存储
    2. 关系型数据库通过数据库抽象层自动选择
    3. 同一套 API 兼容 py-pglite 和 PostgreSQL

Usage:
    # 初始化所有数据库
    from app.models.init_db import init_all_databases
    
    init_all_databases()
    
    # 检查一致性
    from app.models.init_db import check_consistency
    
    check_consistency()
"""

from app.models.db import (
    init_mock_data, 
    list_collections, 
    get_collection_count, 
    is_mongo_available, 
    get_all_collections
)
from app.models.relational_db import (
    init_relational_schema, 
    init_relational_data, 
    list_tables, 
    get_table_count, 
    get_all_tables,
    table_exists
)
from app.models.database import (
    get_environment,
    DBEnvironment,
    DatabaseFactory
)


def init_all_databases():
    """初始化所有数据库
    
    依次初始化 MongoDB 和关系型数据库，并打印初始化结果。
    """
    print("=" * 60)
    print("=== Initializing Databases")
    print("=" * 60)
    
    env = get_environment()
    print(f"\n[DB Environment] {env.value}")

    print("\n[1] Initializing MongoDB...")
    if is_mongo_available():
        init_mock_data()
        print("✓ MongoDB initialized")
    else:
        print("✗ MongoDB not available, skipping")

    print("\n[2] Initializing Relational Database...")
    init_relational_schema()
    init_relational_data()
    print("✓ Relational Database initialized")

    print("\n" + "=" * 60)
    print("=== Initialization Summary")
    print("=" * 60)

    if is_mongo_available():
        print("\nMongoDB Collections:")
        mongo_collections = list_collections()
        for coll in mongo_collections:
            print(f"  - {coll}: {get_collection_count(coll)} docs")

    print(f"\nRelational DB Tables ({env.value}):")
    for tbl in list_tables():
        print(f"  - {tbl}: {get_table_count(tbl)} rows")

    print("\n" + "=" * 60)
    print("All databases initialized!")
    print("=" * 60)


def check_consistency():
    """检查 MongoDB 和关系型数据库之间的一致性
    
    Returns:
        bool: 一致返回 True，否则返回 False
    """
    print("\n" + "=" * 60)
    print("=== Database Consistency Check")
    print("=" * 60)
    
    env = get_environment()
    print(f"\n[DB Environment] {env.value}")
    
    consistent = True

    mongo_collections = get_all_collections()
    relational_tables = get_all_tables()
    
    print(f"\nMongoDB has {len(mongo_collections)} initial collections")
    print(f"Relational DB has {len(relational_tables)} tables")
    
    common = set(mongo_collections) & set(relational_tables)
    
    print(f"\nCommon: {len(common)}")

    if is_mongo_available():
        print("\nDetailed count check:")
        for name in sorted(common):
            m_count = get_collection_count(name)
            p_count = get_table_count(name)
            if m_count == p_count:
                print(f"  ✓ {name}: OK ({m_count})")
            else:
                print(f"  ✗ {name}: MongoDB={m_count}, RelationalDB={p_count}")
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
