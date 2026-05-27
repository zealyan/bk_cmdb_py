# 服务分类 (Service Category) Python 后端实现计划

## 一、原项目分析摘要

### 1.1 数据结构 (Go → MongoDB)

**集合名：** `cc_ServiceCategory`

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `id` | int64 | 主键ID，自增 |
| `bk_biz_id` | int64 | 业务ID |
| `name` | string | 分类名称 |
| `bk_root_id` | int64 | 根节点ID（一级分类指向自己） |
| `bk_parent_id` | int64 | 父节点ID（0表示一级分类） |
| `bk_supplier_account` | string | 供应商账号 |
| `is_built_in` | bool | 是否内置（不可修改） |

### 1.2 API 接口规范

| 方法 | 路径 | 说明 | 请求体/参数 |
|------|------|------|------------|
| POST | `/create/proc/service_category` | 创建分类 | `{bk_biz_id, name, bk_parent_id}` |
| GET | `/find/process/service_category/{id}` | 获取单个 | 路径参数 id |
| GET | `/find/process/default_service_category` | 获取默认分类 | - |
| POST | `/findmany/proc/service_category` | 列表查询 | `{bk_biz_id, with_statistics?}` |
| PUT | `/update/proc/service_category/{id}` | 更新分类 | `{name}` |
| DELETE | `/delete/proc/service_category/{id}` | 删除分类 | 路径参数 id |
| POST | `/findmany/proc/service_category/with_statistics` | 带统计列表 | `{bk_biz_id}` |

### 1.3 核心业务逻辑

1. **创建分类时：**
   - 自动生成自增 ID
   - `bk_root_id` = 自身ID（顶级）或父级 RootID
   - `bk_parent_id` = 0 为一级分类
   - 校验名称在同业务同层级唯一
   - 校验 `bk_biz_id` 有效

2. **更新分类时：**
   - 内置分类不可修改
   - 校验名称唯一性
   - 只允许修改 `name` 字段

3. **删除分类时：**
   - 有子分类不可删除
   - 被服务模板引用的不可删除
   - 被模块引用的不可删除

4. **列表查询时：**
   - 按业务ID过滤（包含全局0）
   - 可选带统计（服务模板+模块引用数）
   - 按名称排序

---

## 二、当前 Python 后端现状

### 2.1 已实现接口

- ✅ `/api/v3/findmany/proc/service_category` - 列表查询
- ✅ `/api/v3/findmany/proc/service_category/with_statistics` - 带统计列表
- ✅ `/api/v3/create/proc/service_category` - 创建
- ✅ `/api/v3/update/proc/service_category` - 更新
- ✅ `/api/v3/delete/proc/service_category` - 删除

### 2.2 缺失接口

- ❌ `/api/v3/find/process/service_category/{id}` - 获取单个
- ❌ `/api/v3/find/process/default_service_category` - 获取默认

### 2.3 需要完善的逻辑

1. **创建时：** 
   - 完善 `bk_root_id` 自动设置逻辑
   - 完善名称唯一性校验
   - 完善 `bk_supplier_account` 设置

2. **删除时：**
   - 检查子分类引用
   - 检查服务模板引用
   - 检查模块引用

3. **列表查询：**
   - 完善统计逻辑（计算实际引用数）

---

## 三、实现计划

### 阶段一：完善数据模型和初始化 (2h)

- [ ] 1.1 更新 `INIT_DATA` 中 `cc_ServiceCategory` 的数据结构
- [ ] 1.2 统一字段命名（`bk_parent_id` vs `parent_id`）
- [ ] 1.3 添加内置分类数据

### 阶段二：完善 CRUD 接口 (3h)

- [ ] 2.1 完善 `create_service_category` 接口
  - 自动生成 ID（使用当前最大ID+1）
  - 自动设置 `bk_root_id`
  - 添加名称唯一性校验
  - 设置 `bk_supplier_account`

- [ ] 2.2 添加 `get_service_category` 接口（获取单个）
- [ ] 2.3 添加 `get_default_service_category` 接口

- [ ] 2.4 完善 `update_service_category` 接口
  - 校验内置分类不可修改
  - 名称唯一性校验

- [ ] 2.5 完善 `delete_service_category` 接口
  - 检查子分类存在
  - 检查服务模板引用
  - 检查模块引用

### 阶段三：完善列表查询 (1h)

- [ ] 3.1 完善 `ListServiceCategories` 统计逻辑
  - 统计服务模板引用数
  - 统计模块引用数

- [ ] 3.2 完善查询条件
  - 按业务ID过滤（包含全局0）
  - 按名称排序

### 阶段四：测试验证 (2h)

- [ ] 4.1 编写测试用例
- [ ] 4.2 API 接口测试
- [ ] 4.3 前端功能验证

---

## 四、文件修改清单

### 4.1 主要修改文件

| 文件路径 | 修改内容 |
|---------|---------|
| `/workspace/app/models/db.py` | 更新 `cc_ServiceCategory` 初始化数据 |
| `/workspace/app/routes/admin_routes.py` | 完善服务分类所有接口 |
| `/workspace/app/models/__init__.py` | 如需要添加模型定义 |

### 4.2 依赖文件

| 文件路径 | 说明 |
|---------|------|
| `/workspace/app/models/db.py` | MongoDB 连接和集合操作 |
| `/workspace/app/routes/admin_routes.py` | API 路由定义 |

---

## 五、预期产出

1. **完整的服务分类 Python 后端实现**
   - 符合 Go 原项目 API 规范
   - 支持完整的 CRUD 操作
   - 包含完整的业务校验逻辑

2. **测试文档**
   - API 接口测试用例
   - 业务逻辑验证

---

## 六、风险和注意事项

1. **数据库兼容**：确保 MongoDB 和 mongomock 兼容
2. **字段一致性**：与 Go 原项目保持字段完全一致
3. **错误处理**：保持与原项目相同的错误码和消息格式
