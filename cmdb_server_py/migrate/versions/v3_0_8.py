"""v3.0.8 — addPresetObjects: 对象/属性/分类/关联/平台/系统 + 关联类型"""
def up(db):
    from migrate.base_migrate import run_base_migrate
    from migrate.data.groups import run_group_migrate
    from migrate.data.attributes import run_attribute_migrate
    from migrate.data.associations import run_association_migrate
    from migrate.data.association_types import run_association_type_migrate
    run_base_migrate(db)
    run_group_migrate(db)
    run_attribute_migrate(db)
    run_association_migrate(db)
    run_association_type_migrate(db)
    print("  [v3.0.8] 基础 seed + 关联类型 ✅")
