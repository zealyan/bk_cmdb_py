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


def cmd_all(db):
    print("=" * 50)
    print("Running all migrations...")
    print("=" * 50)
    run_base_migrate(db)
    run_group_migrate(db)
    run_attribute_migrate(db)
    run_association_migrate(db)
    print("\nAll migrations completed!")


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
    parser.add_argument("--all", action="store_true", help="Run all migrations")
    parser.add_argument("--check", action="store_true", help="Check database status")
    parser.add_argument("--uri", default=MONGO_URI, help="MongoDB URI")
    parser.add_argument("--db", default=MONGO_DB, help="Database name")

    args = parser.parse_args()

    client = MongoClient(args.uri)
    db = client[args.db]

    if args.all:
        cmd_all(db)
    elif args.init:
        cmd_init(db)
    elif args.groups:
        cmd_groups(db)
    elif args.attributes:
        cmd_attributes(db)
    elif args.associations:
        cmd_associations(db)
    elif args.check:
        cmd_check(db)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
