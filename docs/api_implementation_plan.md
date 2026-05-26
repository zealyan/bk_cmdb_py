# API 实现计划

## 一、已实现的 API 清单

### 1.1 业务相关 API
| API 路径 | 方法 | 功能 | 状态 |
|---------|------|------|------|
| `/api/v3/biz/search` | POST | 搜索业务 | ✅ 已实现 |
| `/api/v3/biz/simplify` | GET | 获取业务简单列表 | ✅ 已实现 |
| `/api/v3/biz/with_reduced` | GET | 获取有权限的业务列表 | ✅ 已实现 |
| `/biz/search` | POST | 搜索业务（无前缀） | ✅ 已实现（通过双注册） |
| `/biz/simplify` | GET | 获取业务简单列表（无前缀） | ✅ 已实现（通过双注册） |
| `/biz/with_reduced` | GET | 获取有权限的业务列表（无前缀） | ✅ 已实现（通过双注册） |

### 1.2 用户认证 API
| API 路径 | 方法 | 功能 | 状态 |
|---------|------|------|------|
| `/api/v3/user/auth` | POST | 用户登录 | ✅ 已实现 |
| `/api/v3/user/logout` | GET | 用户登出 | ✅ 已实现 |
| `/user/auth` | POST | 用户登录（无前缀） | ✅ 已实现（通过双注册） |
| `/user/logout` | GET | 用户登出（无前缀） | ✅ 已实现（通过双注册） |

### 1.3 对象模型 API
| API 路径 | 方法 | 功能 | 状态 |
|---------|------|------|------|
| `/api/v3/find/objectattr` | POST | 获取对象属性 | ✅ 已实现 |
| `/api/v3/find/objectattgroup/object/<obj_id>` | POST | 获取对象属性分组 | ✅ 已实现 |
| `/api/v3/find/topomodelmainline` | POST | 获取拓扑主线模型 | ✅ 已实现 |
| `/api/v3/find/classificationobject` | POST | 获取模型分类 | ✅ 已实现 |
| `/api/v3/find/objectassociation` | POST | 获取对象关联 | ✅ 已实现 |
| `/api/v3/find/instassociation` | POST | 获取实例关联 | ✅ 已实现 |
| `/api/v3/find/associationtype` | POST | 获取关联类型 | ✅ 已实现 |
| `/api/v3/find/topoassociationtype` | POST | 获取拓扑关联类型 | ✅ 已实现（新增） |
| `/api/v3/find/objecttopo/scope_type/global/scope_id/0` | POST | 获取模型拓扑 | ✅ 已实现（新增） |
| `/api/v3/update/objecttopo/scope_type/global/scope_id/0` | POST | 更新模型拓扑 | ✅ 已实现（新增） |
| `/find/objectattr` | POST | 获取对象属性（无前缀） | ✅ 已实现（通过双注册） |

### 1.4 用户自定义 API
| API 路径 | 方法 | 功能 | 状态 |
|---------|------|------|------|
| `/api/v3/usercustom/user/search` | POST | 获取用户自定义配置 | ✅ 已实现 |
| `/api/v3/usercustom/default/model` | POST | 获取默认模型配置 | ✅ 已实现 |
| `/api/v3/find/usercustom` | POST | 获取用户自定义 | ✅ 已实现 |
| `/api/v3/search/usercustom` | POST | 搜索用户自定义 | ✅ 已实现 |
| `/api/v3/usercustom` | POST | 保存用户自定义配置 | ✅ 已实现（新增） |
| `/api/v3/usercustom/default/search` | POST | 获取默认用户配置 | ✅ 已实现（新增） |

### 1.5 审计 API
| API 路径 | 方法 | 功能 | 状态 |
|---------|------|------|------|
| `/api/v3/find/audit_dict` | GET | 获取审计字典 | ✅ 已实现（新增） |
| `/api/v3/findmany/audit_list` | POST | 查询审计列表 | ✅ 已实现（新增） |
| `/api/v3/find/audit` | POST | 获取审计详情 | ✅ 已实现（新增） |
| `/api/v3/find/inst_audit` | POST | 查询实例审计 | ✅ 已实现（新增） |

## 二、待实现的 API 清单（按优先级）

### 2.1 高优先级 - 资源菜单、首页基础功能

#### 2.1.1 全局配置 API
| API 路径 | 方法 | 功能 | 优先级 |
|---------|------|------|--------|
| `/find/platformadmin/config` | POST | 获取全局配置 | 🔴 高 |
| `/api/v3/find/platformadmin/config` | POST | 获取全局配置 | 🔴 高 |

#### 2.1.2 用户自定义 API
| API 路径 | 方法 | 功能 | 优先级 |
|---------|------|------|--------|
| `/find/usercustom` | POST | 获取用户自定义配置 | 🔴 高 |
| `/search/usercustom` | POST | 搜索用户自定义 | 🔴 高 |
| `/api/v3/find/usercustom` | POST | 获取用户自定义配置 | 🔴 高 |

#### 2.1.3 对象模型分类 API
| API 路径 | 方法 | 功能 | 优先级 |
|---------|------|------|--------|
| `/find/objectclassification` | POST | 获取对象分类 | 🔴 高 |
| `/api/v3/find/objectclassification` | POST | 获取对象分类 | 🔴 高 |

#### 2.1.4 拓扑主线 API
| API 路径 | 方法 | 功能 | 优先级 |
|---------|------|------|--------|
| `/find/mainlineobject` | POST | 获取主线对象 | 🔴 高 |
| `/api/v3/find/mainlineobject` | POST | 获取主线对象 | 🔴 高 |

#### 2.1.5 对象模型完整 API
| API 路径 | 方法 | 功能 | 优先级 |
|---------|------|------|--------|
| `/find/object` | POST | 搜索对象 | 🔴 高 |
| `/api/v3/find/object` | POST | 搜索对象 | 🔴 高 |

#### 2.1.6 资源菜单 - 主机相关 API
| API 路径 | 方法 | 功能 | 优先级 |
|---------|------|------|--------|
| `/hosts/search` | POST | 搜索主机 | 🔴 高 |
| `/api/v3/hosts/search` | POST | 搜索主机 | 🔴 高 |
| `/hosts/search/web` | POST | 搜索主机（Web） | 🔴 高 |
| `/api/v3/hosts/search/web` | POST | 搜索主机（Web） | 🔴 高 |

### 2.2 中优先级 - 资源菜单高级功能

#### 2.2.1 模块 API
| API 路径 | 方法 | 功能 | 优先级 |
|---------|------|------|--------|
| `/search/module` | POST | 搜索模块 | 🟡 中 |
| `/findmany/module` | POST | 查询多个模块 | 🟡 中 |

#### 2.2.2 集群 API
| API 路径 | 方法 | 功能 | 优先级 |
|---------|------|------|--------|
| `/search/set` | POST | 搜索集群 | 🟡 中 |
| `/findmany/set` | POST | 查询多个集群 | 🟡 中 |

#### 2.2.3 对象实例 API
| API 路径 | 方法 | 功能 | 优先级 |
|---------|------|------|--------|
| `/search/inst` | POST | 搜索实例 | 🟡 中 |
| `/findmany/inst` | POST | 查询多个实例 | 🟡 中 |
| `/create/inst` | POST | 创建实例 | 🟡 中 |
| `/update/inst` | PUT | 更新实例 | 🟡 中 |
| `/delete/inst` | DELETE | 删除实例 | 🟡 中 |

## 三、实现计划

### 阶段 1：基础功能完整性（立即执行）
1. **全局配置 API** - 让页面能正常加载
2. **用户自定义 API** - 提供基础的用户配置
3. **对象模型完整 API** - 完善模型分类、对象查询等
4. **主机基础 API** - 主机搜索等基础功能

### 阶段 2：资源菜单完善
1. **模块 API** - 支持模块操作
2. **集群 API** - 支持集群操作
3. **对象实例 API** - 支持实例增删改查

### 阶段 3：高级功能
1. **权限 API** - 更完整的权限管理
2. **业务集 API** - 业务集功能
3. **其他高级 API** - 按需实现

## 四、实现规范
1. **双注册路由**：所有 API 都同时注册带 `/api/v3` 前缀和不带前缀的版本
2. **统一响应格式**：使用 `make_response(result, code, message, data)` 统一响应格式
3. **数据库模拟**：对于没有数据库支持的 API，返回合理的模拟数据
4. **错误处理**：捕获异常，返回合适的错误信息
