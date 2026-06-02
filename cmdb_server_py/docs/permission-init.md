# 权限初始化

## 初始化命令

```bash
python scripts/init_admin_policy.py
```

## 功能说明

- 初始化 `admin` 用户的超级权限（所有资源 + 所有动作）
- 初始化默认用户权限（tom、jelly）
- 将策略存储到 MongoDB 的 `auth_policies` 集合

## 默认权限

| 用户 | 资源 | 动作 |
|------|------|------|
| admin | 所有 | 所有 |
| tom | biz | view |
| tom | host | view, edit |
| jelly | biz | view, list |

## 权限类型

**资源类型**: biz, host, module, set, process, cloud_area, model, custom_query

**动作类型**: create, view, edit, delete, list
