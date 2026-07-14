"""
数据迁移CLI

用法:
    python -m migrate.cli
    python -m migrate.cli --init        # 初始化基础数据
    python -m migrate.cli --all         # 执行所有迁移
    python -m migrate.cli --check      # 检查数据库状态
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from migrate.base_migrate import run_base_migrate
from migrate.data.groups import run_group_migrate
from migrate.data.attributes import run_attribute_migrate
from migrate.data.associations import run_association_migrate
from migrate.data.association_types import run_association_type_migrate
from migrate.data.service_categories import run_service_category_migrate


MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.environ.get("MONGO_DB", "cmdb")


def get_db():
    client = MongoClient(MONGO_URI)
    return client[MONGO_DB]


def cmd_init(db):
    print("=" * 50)
    print("Initializing base data...")
    print("=" * 50)
    run_base_migrate(db)
    print("Base data initialized!")


def cmd_groups(db):
    print("=" * 50)
    print("Migrating property groups...")
    print("=" * 50)
    run_group_migrate(db)


def cmd_attributes(db):
    print("=" * 50)
    print("Migrating attributes...")
    print("=" * 50)
    run_attribute_migrate(db)


def cmd_associations(db):
    print("=" * 50)
    print("Migrating associations...")
    print("=" * 50)
    run_association_migrate(db)


def cmd_association_types(db):
    print("=" * 50)
    print("Migrating association types...")
    print("=" * 50)
    run_association_type_migrate(db)


def cmd_service_categories(db):
    print("=" * 50)
    print("Migrating service categories...")
    print("=" * 50)
    run_service_category_migrate(db)


def cmd_all(db):
    print("=" * 50)
    print("Running all migrations (module-based)...")
    print("=" * 50)
    run_base_migrate(db)
    run_group_migrate(db)
    run_attribute_migrate(db)
    run_association_migrate(db)
    run_association_type_migrate(db)
    run_service_category_migrate(db)
    print("\nAll migrations completed!")


def cmd_upgrade(db):
    """完整版本升级（对齐 Go upgrader，执行全部 63+ 个版本）。"""
    from migrate.upgrader import run_all as run_upgrader
    run_upgrader()


def cmd_check(db):
    print("=" * 50)
    print("Database Status Check")
    print("=" * 50)

    collections = [
        "cc_ObjClassification",
        "cc_ObjDes",
        "cc_PropertyGroup",
        "cc_ObjAttDes",
        "cc_ObjAsst",
        "cc_System",
        "cc_PlatBase",
    ]

    for col in collections:
        count = db[col].count_documents({}) if col in db.list_collection_names() else 0
        status = "✓" if count > 0 else "✗"
        print(f"  {status} {col}: {count} documents")


def main():
    parser = argparse.ArgumentParser(description="BK-CMDB Python Migrate CLI")
    parser.add_argument("--init", action="store_true", help="Initialize base data")
    parser.add_argument("--groups", action="store_true", help="Migrate property groups")
    parser.add_argument("--attributes", action="store_true", help="Migrate attributes")
    parser.add_argument("--associations", action="store_true", help="Migrate associations")
    parser.add_argument("--association-types", action="store_true", help="Migrate association types (cc_AsstDes)")
    parser.add_argument("--service-categories", action="store_true", help="Migrate service categories (cc_ServiceCategory)")
    parser.add_argument("--upgrade", action="store_true", help="Run full version upgrade pipeline (对齐 Go upgrader)")
    parser.add_argument("--all", action="store_true", help="Run all migrations")
    parser.add_argument("--check", action="store_true", help="Check database status")
    parser.add_argument("--uri", default=MONGO_URI, help="MongoDB URI")
    parser.add_argument("--db", default=MONGO_DB, help="Database name")

    args = parser.parse_args()

    client = MongoClient(args.uri)
    db = client[args.db]

    if args.all:
        cmd_all(db)
    elif args.upgrade:
        cmd_upgrade(db)
    elif args.init:
        cmd_init(db)
    elif args.groups:
        cmd_groups(db)
    elif args.attributes:
        cmd_attributes(db)
    elif args.associations:
        cmd_associations(db)
    elif args.association_types:
        cmd_association_types(db)
    elif args.service_categories:
        cmd_service_categories(db)
    elif args.check:
        cmd_check(db)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
