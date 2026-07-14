"""
服务分类数据迁移（cc_ServiceCategory）

对应 Go: src/scene_server/admin_server/upgrader/history/x19.05.16.01/
    add_default_category.go  — 默认分类（无业务标签）
    add_inner_category.go    — 内置分类层级
"""

from .. import BaseMigrate, get_timestamp, BK_DEFAULT_OWNER_ID, BK_SYSTEM_OPERATOR


class ServiceCategoryMigrate(BaseMigrate):
    """服务分类迁移"""

    def migrate(self) -> None:
        self.ensure_collection("cc_ServiceCategory")
        ts = get_timestamp()

        # 1. 创建根分类（无父级）
        root_id = self._upsert_category(1, "Default service category", 0, 1, ts)
        # 2. 创建默认子分类
        self._upsert_category(2, "Default service category", root_id, root_id, ts)

        # 3. 内置分类层级
        builtins = [
            # (name, parent_name, id_offset)
            ("数据库", None, 10),
            ("Mysql", "数据库", 11),
            ("Redis", "数据库", 12),
            ("Oracle", "数据库", 13),
            ("SQLServer", "数据库", 14),
            ("MongoDB", "数据库", 15),
            ("Etcd", "数据库", 16),
            ("Zookeeper", "数据库", 17),
            ("消息队列", None, 20),
            ("Kafka", "消息队列", 21),
            ("RabbitMQ", "消息队列", 22),
            ("HTTP 服务", None, 30),
            ("Nginx", "HTTP 服务", 31),
            ("Apache", "HTTP 服务", 32),
            ("Tomcat", "HTTP 服务", 33),
            ("存储", None, 40),
            ("Ceph", "存储", 41),
            ("NFS", "存储", 42),
        ]

        # 先创建根级分类，建立 name→id 映射
        cat_id_map = {"Default service category": root_id}
        for name, parent, _ in builtins:
            if parent is None:
                cat_id = self._find_or_create_root(name, ts)
                cat_id_map[name] = cat_id

        # 再创建子级分类
        for name, parent, cat_id in builtins:
            if parent is not None:
                parent_id = cat_id_map.get(parent)
                if parent_id:
                    self._upsert_category(cat_id, name, parent_id,
                                          cat_id_map.get(parent, root_id), ts)
                    cat_id_map[name] = cat_id

    def _find_or_create_root(self, name, ts):
        """查找或创建根级分类（parent_id=0）。"""
        existing = self.db["cc_ServiceCategory"].find_one({"name": name, "bk_parent_id": 0})
        if existing and "id" in existing:
            return existing["id"]
        # 找最大 id
        max_doc = self.db["cc_ServiceCategory"].find_one(sort=[("id", -1)])
        new_id = (max_doc["id"] + 1) if max_doc and "id" in max_doc else 1
        doc = {
            "id": new_id,
            "name": name,
            "bk_root_id": new_id,
            "bk_parent_id": 0,
            "bk_supplier_account": "0",
            "is_built_in": True,
            "metadata": {"label": {"bk_biz_id": "0"}},
            "create_time": ts,
            "last_time": ts,
        }
        self.db["cc_ServiceCategory"].insert_one(doc)
        return new_id

    def _upsert_category(self, cat_id, name, parent_id, root_id, ts):
        """Upsert 一条服务分类。"""
        doc = {
            "id": cat_id,
            "name": name,
            "bk_root_id": root_id,
            "bk_parent_id": parent_id,
            "bk_supplier_account": "0",
            "is_built_in": True,
            "metadata": {"label": {"bk_biz_id": "0"}},
            "create_time": ts,
            "last_time": ts,
        }
        existing = self.db["cc_ServiceCategory"].find_one({"id": cat_id})
        if existing:
            self.db["cc_ServiceCategory"].update_one({"id": cat_id}, {"$set": doc})
        else:
            self.db["cc_ServiceCategory"].insert_one(doc)
        return cat_id


def run_service_category_migrate(db) -> None:
    ServiceCategoryMigrate(db).migrate()
    print("Service category migrate completed!")
