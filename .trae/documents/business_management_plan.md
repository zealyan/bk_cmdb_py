# 业务管理模块实现计划

## 概述

实现业务管理模块，包括创建、编辑、删除、搜索业务等功能，支持前端交互。

## 现状分析

### 前端实现

- 前端已完整实现业务管理功能（Vue组件）
- 主要页面：
  - `/resource/business` - 业务列表页（创建、编辑、批量编辑、归档）
  - `/resource/business/details/:bizId` - 业务详情页
  - `/resource/business/history` - 已归档业务列表

### 后端现状

- [biz_routes.py](file:///workspace/bk_cmdb_py/app/routes/biz_routes.py) 已有部分API
- 缺少完整的业务CRUD API
- 数据库使用MongoDB的`cc_ApplicationBase`集合

### API需求

根据前端调用，需要实现以下API：

| API路径 | 方法 | 功能 |
|---------|------|------|
| `/biz/search/{account}` | POST | 搜索业务 |
| `/biz/search/web` | POST | Web搜索业务 |
| `/biz/simplify` | GET | 获取简化业务列表 |
| `/biz/with_reduced` | GET | 获取带权限信息的业务列表 |
| `/biz/{account}` | POST | 创建业务 |
| `/biz/{account}/{bizId}` | PUT | 更新业务 |
| `/updatemany/biz/property` | PUT | 批量更新业务 |
| `/biz/status/disabled/{account}/{bizId}` | PUT | 归档业务 |
| `/biz/status/enable/{account}/{bizId}` | PUT | 恢复业务 |

## 实现计划

### 1. 业务模型和数据库操作

- 完善业务数据模型
- 实现业务数据的CRUD操作
- 支持MongoDB和关系型数据库（py-pglite）的双写

#### 1.1 业务数据初始化
- 添加更多示例业务数据到初始化脚本
- 业务数据包含：业务名称、维护人员、时区、创建时间等字段
- 确保业务ID生成逻辑

#### 1.2 用户与业务关系初始化
- 初始化用户业务关联数据（user_business集合）
- 支持多个用户关联同一业务
- 确保关系数据完整性

#### 1.3 数据库脚本完善
- 更新 [db.py](file:///workspace/bk_cmdb_py/app/models/db.py) 中的初始化数据
- 确保关系型数据库（py-pglite）也有对应的数据初始化

### 2. 后端API开发

在 [biz_routes.py](file:///workspace/bk_cmdb_py/app/routes/biz_routes.py) 中实现以下API：

#### 2.1 搜索API
- POST `/biz/search/{account}` - 按条件搜索业务
- POST `/biz/search/web` - Web端搜索业务

#### 2.2 查询API
- GET `/biz/simplify` - 获取简化业务列表
- GET `/biz/with_reduced` - 获取带权限信息的业务列表

#### 2.3 创建API
- POST `/biz/{account}` - 创建新业务

#### 2.4 更新API
- PUT `/biz/{account}/{bizId}` - 更新单个业务
- PUT `/updatemany/biz/property` - 批量更新业务属性

#### 2.5 状态管理API
- PUT `/biz/status/disabled/{account}/{bizId}` - 归档业务
- PUT `/biz/status/enable/{account}/{bizId}` - 恢复归档业务

### 3. 集成权限管理

- 使用已有的权限系统
- 在业务操作前后进行权限验证

### 4. 测试与验证

- 测试所有API的功能
- 验证前后端交互正常
- 测试边界条件

## 实施步骤

### 阶段1：数据模型和初始化
1. 完善业务数据模型和数据库操作
2. 添加更多初始业务数据
3. 完善用户与业务关系数据初始化
4. 确保数据库初始化脚本正确

### 阶段2：API实现
1. 逐个实现API接口
2. 添加权限检查
3. 实现用户业务关联查询

### 阶段3：测试与验证
1. 测试所有API的功能
2. 验证前后端交互正常
3. 测试边界条件
4. 文档更新
