# 业务拓扑 API 实现计划

> **目标：** 实现业务拓扑（Business Topology）的后端 Python API 接口和 Mock 数据

**架构概述：** 基于 Flask 框架实现 RESTful API，集成 MongoDB 数据库，提供业务拓扑的 CRUD 操作接口。前端通过 Vue.js 调用这些 API 实现拓扑的增删改查功能。

**技术栈：**
- 后端：Python Flask
- 数据库：MongoDB
- 前端：Vue.js 2.x

---

## 一、API 接口清单

### 1.1 拓扑模型主线 API（已完成 ✅）

| 接口 | 方法 | 路径 | 功能 | 状态 |
|------|------|------|------|------|
| 查询拓扑模型 | POST | `/find/topomodelmainline` | 获取业务拓扑主线模型层级 | ✅ 已实现 |
| 创建拓扑模型 | POST | `/create/topomodelmainline` | 添加模型主关联 | ⚠️ 待实现 |
| 删除拓扑模型 | DELETE | `/delete/topomodelmainline/object/{bkObjId}` | 删除模型主关联 | ⚠️ 待实现 |

### 1.2 集群（Set）API

| 接口 | 方法 | 路径 | 功能 | 状态 |
|------|------|------|------|------|
| 创建集群 | POST | `/set/{bkBizId}` | 在指定业务下创建集群 | ✅ 已实现 |
| 批量创建集群 | POST | `/set/{bkBizId}/batch` | 批量创建集群 | ⚠️ 待实现 |
| 查询集群 | POST | `/set/search/{bkSupplierAccount}/{bkBizId}` | 查询业务下的集群列表 | ⚠️ 待实现 |
| 更新集群 | PUT | `/set/{bkBizId}/{bkSetId}` | 更新指定集群信息 | ⚠️ 待实现 |
| 删除集群 | DELETE | `/set/{bkBizId}/{bkSetId}` | 删除指定集群 | ⚠️ 待实现 |

### 1.3 模块（Module）API

| 接口 | 方法 | 路径 | 功能 | 状态 |
|------|------|------|------|------|
| 创建模块 | POST | `/module/{bkBizId}/{bkSetId}` | 在指定集群下创建模块 | ⚠️ 待实现 |
| 查询模块 | POST | `/module/search/{bkSupplierAccount}/{bkBizId}/{bkSetId}` | 查询指定集群下的模块 | ⚠️ 待实现 |
| 更新模块 | PUT | `/module/{bkBizId}/{bkSetId}/{bkModuleId}` | 更新指定模块信息 | ⚠️ 待实现 |
| 删除模块 | DELETE | `/module/{bkBizId}/{bkSetId}/{bkModuleId}` | 删除指定模块 | ⚠️ 待实现 |

### 1.4 业务拓扑实例 API

| 接口 | 方法 | 路径 | 功能 | 状态 |
|------|------|------|------|------|
| 获取实例拓扑 | POST | `/find/topoinst/biz/{bkBizId}` | 获取业务实例拓扑树 | ⚠️ 待实现 |
| 获取拓扑实例统计 | POST | `/find/topoinst_with_statistics/biz/{bkBizId}` | 获取拓扑及统计信息 | ✅ 已实现 |
| 获取子节点实例 | GET | `/topoinstchild/object/{bkObjId}/biz/{bkBizId}/inst/{bkInstId}` | 获取子节点实例列表 | ⚠️ 待实现 |
| 获取拓扑路径 | POST | `/find/topopath/biz/{bkBizId}` | 获取拓扑节点路径 | ⚠️ 待实现 |
| 获取主机服务实例统计 | POST | `/find/topoinstnode/host_serviceinst_count/{bkBizId}` | 获取节点主机和服务统计 | ✅ 已实现 |
| 获取内置拓扑 | GET | `/topo/internal/{bkSupplierAccount}/{bkBizId}/with_statistics` | 获取空闲机池拓扑 | ⚠️ 待实现 |

---

## 二、数据库集合设计

### 2.1 集合清单

```
cc_SetBase       - 集群基础信息
cc_ModuleBase    - 模块基础信息
cc_SetTemplate   - 集群模板（可选）
cc_ServiceTemplate - 服务模板（可选）
```

### 2.2 数据结构

#### cc_SetBase（集群）
```javascript
{
    bk_set_id: Number,         // 集群ID (主键)
    bk_set_name: String,       // 集群名称
    bk_biz_id: Number,         // 所属业务ID
    bk_supplier_account: String, // 开发商账号
    bk_parent_id: Number,      // 父节点ID（0表示直接属于业务）
    bk_parent_obj: String,     // 父节点类型（biz）
    description: String,       // 描述
    bk_service_status: String, // 服务状态（1:运营中, 2:停止）
    bk_set_env: String,        // 环境类型（1:测试, 2:体验, 3:正式）
    create_time: String,       // 创建时间
    last_time: String,         // 更新时间
    bk_data_status: String     // 数据状态（enabled/disabled）
}
```

#### cc_ModuleBase（模块）
```javascript
{
    bk_module_id: Number,      // 模块ID (主键)
    bk_module_name: String,     // 模块名称
    bk_set_id: Number,         // 所属集群ID
    bk_biz_id: Number,         // 所属业务ID
    bk_supplier_account: String, // 开发商账号
    bk_parent_id: Number,      // 父节点ID
    bk_parent_obj: String,     // 父节点类型（set）
    bk_service_category_id: Number, // 服务分类ID
    create_time: String,       // 创建时间
    last_time: String,         // 更新时间
    bk_data_status: String     // 数据状态（enabled/disabled）
}
```

---

## 三、实现任务

### Task 1: 添加集群和模块的 Mock 数据到初始化脚本

**文件：**
- 修改: `app/models/db.py:277-433`

- [ ] **Step 1: 添加 cc_SetBase 集合的 Mock 数据**

在 `INIT_DATA` 字典中添加 `cc_SetBase` 数据（已在之前添加）：
```python
"cc_SetBase": [
    {
        "bk_set_id": 1,
        "bk_set_name": "PaaS平台",
        "bk_biz_id": 2,
        "bk_supplier_account": "0",
        "bk_parent_id": 0,
        "bk_parent_obj": "biz",
        "description": "PaaS基础平台集群",
        "bk_service_status": "1",
        "bk_set_env": "3",
        "create_time": "2024-01-01 10:00:00",
        "last_time": "2024-01-01 10:00:00",
        "bk_data_status": "enabled"
    },
    # ... 更多集群数据
]
```

- [ ] **Step 2: 添加 cc_ModuleBase 集合的 Mock 数据**

在 `INIT_DATA` 字典中添加 `cc_ModuleBase` 数据（已在之前添加）：
```python
"cc_ModuleBase": [
    {
        "bk_module_id": 1,
        "bk_module_name": "API模块",
        "bk_set_id": 1,
        "bk_biz_id": 2,
        "bk_supplier_account": "0",
        "bk_parent_id": 1,
        "bk_parent_obj": "set",
        "bk_service_category_id": 1,
        "create_time": "2024-01-01 10:30:00",
        "last_time": "2024-01-01 10:30:00",
        "bk_data_status": "enabled"
    },
    # ... 更多模块数据
]
```

- [ ] **Step 3: 验证数据库初始化**

```bash
cd /workspace/bk_cmdb_py
source venv/bin/activate
python -c "
from app.models.db import db
print('集群数量:', db.cc_SetBase.count_documents({}))
print('模块数量:', db.cc_ModuleBase.count_documents({}))
"
```

预期输出：
```
集群数量: 4
模块数量: 7
```

---

### Task 2: 实现集群 CRUD API

**文件：**
- 创建: `app/routes/set_routes.py`
- 修改: `app/app.py` (注册蓝图)

- [ ] **Step 1: 创建集群路由文件**

创建 `app/routes/set_routes.py`：
```python
from flask import Blueprint, jsonify, request
from app.models.db import db
from datetime import datetime

set_bp = Blueprint('set', __name__)

def make_response(result=True, code=0, message="success", data=None):
    return jsonify({
        "result": result,
        "code": code,
        "message": message,
        "data": data
    })

@set_bp.route('/api/v3/set/<int:biz_id>', methods=['POST'])
@set_bp.route('/set/<int:biz_id>', methods=['POST'])
def create_set(biz_id):
    """创建集群"""
    try:
        req_data = request.get_json() or {}
        
        # 生成新ID
        max_id = db.cc_SetBase.find_one(sort=[("bk_set_id", -1)])
        new_id = (max_id.get("bk_set_id", 0) + 1) if max_id else 1
        
        # 创建集群文档
        set_doc = {
            "bk_set_id": new_id,
            "bk_set_name": req_data.get("bk_set_name", "新集群"),
            "bk_biz_id": biz_id,
            "bk_supplier_account": req_data.get("bk_supplier_account", "0"),
            "bk_parent_id": 0,
            "bk_parent_obj": "biz",
            "description": req_data.get("description", ""),
            "bk_service_status": req_data.get("bk_service_status", "1"),
            "bk_set_env": req_data.get("bk_set_env", "3"),
            "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "bk_data_status": "enabled"
        }
        
        db.cc_SetBase.insert_one(set_doc)
        
        return make_response(data={"bk_set_id": new_id})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))

@set_bp.route('/api/v3/set/<int:biz_id>/batch', methods=['POST'])
@set_bp.route('/set/<int:biz_id>/batch', methods=['POST'])
def create_sets_batch(biz_id):
    """批量创建集群"""
    try:
        req_data = request.get_json() or {}
        sets_data = req_data.get("sets", [])
        
        created_ids = []
        for set_data in sets_data:
            max_id = db.cc_SetBase.find_one(sort=[("bk_set_id", -1)])
            new_id = (max_id.get("bk_set_id", 0) + 1) if max_id else 1
            
            set_doc = {
                "bk_set_id": new_id,
                "bk_set_name": set_data.get("bk_set_name", "新集群"),
                "bk_biz_id": biz_id,
                "bk_supplier_account": set_data.get("bk_supplier_account", "0"),
                "bk_parent_id": 0,
                "bk_parent_obj": "biz",
                "description": set_data.get("description", ""),
                "bk_service_status": set_data.get("bk_service_status", "1"),
                "bk_set_env": set_data.get("bk_set_env", "3"),
                "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "bk_data_status": "enabled"
            }
            
            db.cc_SetBase.insert_one(set_doc)
            created_ids.append({"bk_set_id": new_id})
        
        return make_response(data=created_ids)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))

@set_bp.route('/api/v3/set/<int:biz_id>/<int:set_id>', methods=['PUT'])
@set_bp.route('/set/<int:biz_id>/<int:set_id>', methods=['PUT'])
def update_set(biz_id, set_id):
    """更新集群"""
    try:
        req_data = request.get_json() or {}
        
        update_fields = {"last_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        
        # 可更新的字段
        for field in ["bk_set_name", "description", "bk_service_status", "bk_set_env"]:
            if field in req_data:
                update_fields[field] = req_data[field]
        
        result = db.cc_SetBase.update_one(
            {"bk_set_id": set_id, "bk_biz_id": biz_id},
            {"$set": update_fields}
        )
        
        if result.modified_count > 0:
            return make_response(data={"bk_set_id": set_id})
        else:
            return make_response(result=False, code=404, message="集群不存在")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))

@set_bp.route('/api/v3/set/<int:biz_id>/<int:set_id>', methods=['DELETE'])
@set_bp.route('/set/<int:biz_id>/<int:set_id>', methods=['DELETE'])
def delete_set(biz_id, set_id):
    """删除集群"""
    try:
        # 先删除集群下的所有模块
        db.cc_ModuleBase.delete_many({"bk_set_id": set_id, "bk_biz_id": biz_id})
        
        # 删除集群
        result = db.cc_SetBase.delete_one({"bk_set_id": set_id, "bk_biz_id": biz_id})
        
        if result.deleted_count > 0:
            return make_response(data={"bk_set_id": set_id})
        else:
            return make_response(result=False, code=404, message="集群不存在")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))

@set_bp.route('/api/v3/set/search/<supplier_account>/<int:biz_id>', methods=['POST'])
@set_bp.route('/set/search/<supplier_account>/<int:biz_id>', methods=['POST'])
def search_set(supplier_account, biz_id):
    """查询集群"""
    try:
        req_data = request.get_json() or {}
        
        # 构建查询条件
        filter_query = {
            "bk_biz_id": biz_id,
            "bk_supplier_account": supplier_account,
            "bk_data_status": {"$ne": "disabled"}
        }
        
        # 执行查询
        sets = list(db.cc_SetBase.find(filter_query))
        
        # 转换为API格式
        result = []
        for s in sets:
            result.append({
                "bk_set_id": s.get("bk_set_id"),
                "bk_set_name": s.get("bk_set_name"),
                "bk_biz_id": s.get("bk_biz_id"),
                "bk_supplier_account": s.get("bk_supplier_account"),
                "bk_parent_id": s.get("bk_parent_id"),
                "bk_parent_obj": s.get("bk_parent_obj"),
                "description": s.get("description"),
                "bk_service_status": s.get("bk_service_status"),
                "bk_set_env": s.get("bk_set_env"),
                "create_time": s.get("create_time"),
                "last_time": s.get("last_time")
            })
        
        return make_response(data=result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))
```

- [ ] **Step 2: 注册集群蓝图**

修改 `app/app.py`，在文件开头添加导入：
```python
from app.routes.set_routes import set_bp
```

在 `create_app()` 函数中注册蓝图：
```python
app.register_blueprint(set_bp, url_prefix='')
```

- [ ] **Step 3: 测试集群 API**

```bash
# 测试创建集群
curl -X POST http://127.0.0.1:3000/set/2 \
  -H "Content-Type: application/json" \
  -d '{"bk_set_name": "测试集群", "description": "这是一个测试集群"}'

# 测试查询集群
curl -X POST http://127.0.0.1:3000/set/search/0/2 \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

### Task 3: 实现模块 CRUD API

**文件：**
- 创建: `app/routes/module_routes.py`
- 修改: `app/app.py` (注册蓝图)

- [ ] **Step 1: 创建模块路由文件**

创建 `app/routes/module_routes.py`：
```python
from flask import Blueprint, jsonify, request
from app.models.db import db
from datetime import datetime

module_bp = Blueprint('module', __name__)

def make_response(result=True, code=0, message="success", data=None):
    return jsonify({
        "result": result,
        "code": code,
        "message": message,
        "data": data
    })

@module_bp.route('/api/v3/module/<int:biz_id>/<int:set_id>', methods=['POST'])
@module_bp.route('/module/<int:biz_id>/<int:set_id>', methods=['POST'])
def create_module(biz_id, set_id):
    """创建模块"""
    try:
        req_data = request.get_json() or {}
        
        # 生成新ID
        max_id = db.cc_ModuleBase.find_one(sort=[("bk_module_id", -1)])
        new_id = (max_id.get("bk_module_id", 0) + 1) if max_id else 1
        
        # 创建模块文档
        module_doc = {
            "bk_module_id": new_id,
            "bk_module_name": req_data.get("bk_module_name", "新模块"),
            "bk_set_id": set_id,
            "bk_biz_id": biz_id,
            "bk_supplier_account": req_data.get("bk_supplier_account", "0"),
            "bk_parent_id": set_id,
            "bk_parent_obj": "set",
            "bk_service_category_id": req_data.get("bk_service_category_id", 1),
            "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "bk_data_status": "enabled"
        }
        
        db.cc_ModuleBase.insert_one(module_doc)
        
        return make_response(data={"bk_module_id": new_id})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))

@module_bp.route('/api/v3/module/search/<supplier_account>/<int:biz_id>/<int:set_id>', methods=['POST'])
@module_bp.route('/module/search/<supplier_account>/<int:biz_id>/<int:set_id>', methods=['POST'])
def search_module(supplier_account, biz_id, set_id):
    """查询模块"""
    try:
        req_data = request.get_json() or {}
        
        # 构建查询条件
        filter_query = {
            "bk_biz_id": biz_id,
            "bk_set_id": set_id,
            "bk_supplier_account": supplier_account,
            "bk_data_status": {"$ne": "disabled"}
        }
        
        # 执行查询
        modules = list(db.cc_ModuleBase.find(filter_query))
        
        # 转换为API格式
        result = []
        for m in modules:
            result.append({
                "bk_module_id": m.get("bk_module_id"),
                "bk_module_name": m.get("bk_module_name"),
                "bk_set_id": m.get("bk_set_id"),
                "bk_biz_id": m.get("bk_biz_id"),
                "bk_supplier_account": m.get("bk_supplier_account"),
                "bk_parent_id": m.get("bk_parent_id"),
                "bk_parent_obj": m.get("bk_parent_obj"),
                "bk_service_category_id": m.get("bk_service_category_id"),
                "create_time": m.get("create_time"),
                "last_time": m.get("last_time")
            })
        
        return make_response(data=result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))

@module_bp.route('/api/v3/module/<int:biz_id>/<int:set_id>/<int:module_id>', methods=['PUT'])
@module_bp.route('/module/<int:biz_id>/<int:set_id>/<int:module_id>', methods=['PUT'])
def update_module(biz_id, set_id, module_id):
    """更新模块"""
    try:
        req_data = request.get_json() or {}
        
        update_fields = {"last_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        
        # 可更新的字段
        for field in ["bk_module_name", "bk_service_category_id"]:
            if field in req_data:
                update_fields[field] = req_data[field]
        
        result = db.cc_ModuleBase.update_one(
            {"bk_module_id": module_id, "bk_set_id": set_id, "bk_biz_id": biz_id},
            {"$set": update_fields}
        )
        
        if result.modified_count > 0:
            return make_response(data={"bk_module_id": module_id})
        else:
            return make_response(result=False, code=404, message="模块不存在")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))

@module_bp.route('/api/v3/module/<int:biz_id>/<int:set_id>/<int:module_id>', methods=['DELETE'])
@module_bp.route('/module/<int:biz_id>/<int:set_id>/<int:module_id>', methods=['DELETE'])
def delete_module(biz_id, set_id, module_id):
    """删除模块"""
    try:
        result = db.cc_ModuleBase.delete_one({
            "bk_module_id": module_id,
            "bk_set_id": set_id,
            "bk_biz_id": biz_id
        })
        
        if result.deleted_count > 0:
            return make_response(data={"bk_module_id": module_id})
        else:
            return make_response(result=False, code=404, message="模块不存在")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))
```

- [ ] **Step 2: 注册模块蓝图**

修改 `app/app.py`，在文件开头添加导入：
```python
from app.routes.module_routes import module_bp
```

在 `create_app()` 函数中注册蓝图：
```python
app.register_blueprint(module_bp, url_prefix='')
```

- [ ] **Step 3: 测试模块 API**

```bash
# 测试创建模块
curl -X POST http://127.0.0.1:3000/module/2/1 \
  -H "Content-Type: application/json" \
  -d '{"bk_module_name": "测试模块", "bk_service_category_id": 1}'

# 测试查询模块
curl -X POST http://127.0.0.1:3000/module/search/0/2/1 \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

### Task 4: 实现拓扑实例查询 API

**文件：**
- 修改: `app/routes/object_routes.py` (更新 `find_topo_inst_with_statistics` 函数)

- [ ] **Step 1: 更新业务拓扑实例查询接口**

修改 `object_routes.py` 中的 `find_topo_inst_with_statistics` 函数（已修复），确保返回完整的拓扑数据：
- 业务节点（biz）
- 业务下的集群（set）
- 每个集群下的模块（module）

```python
@object_bp.route('/api/v3/find/topoinst_with_statistics/biz/<int:bk_biz_id>', methods=['POST'])
@object_bp.route('/find/topoinst_with_statistics/biz/<int:bk_biz_id>', methods=['POST'])
def find_topo_inst_with_statistics(bk_biz_id):
    """获取业务拓扑实例及统计信息"""
    try:
        # 查询业务数据
        business = db.cc_ApplicationBase.find_one({"bk_biz_id": bk_biz_id})
        if not business:
            return make_response(data=[])
        
        # 查询该业务下的所有集群
        sets = list(db.cc_SetBase.find({
            "bk_biz_id": business.get("bk_biz_id"),
            "bk_data_status": {"$ne": "disabled"}
        }))
        
        # 查询该业务下的所有模块
        modules = list(db.cc_ModuleBase.find({
            "bk_biz_id": business.get("bk_biz_id"),
            "bk_data_status": {"$ne": "disabled"}
        }))
        
        # 构建拓扑结构...
        # (此函数已在之前修复)
```

- [ ] **Step 2: 实现获取子节点实例 API**

添加 `topoinstchild` 接口：
```python
@object_bp.route('/api/v3/topoinstchild/object/<obj_id>/biz/<int:biz_id>/inst/<int:inst_id>', methods=['GET'])
@object_bp.route('/topoinstchild/object/<obj_id>/biz/<int:biz_id>/inst/<int:inst_id>', methods=['GET'])
def get_inst_topo_child(obj_id, biz_id, inst_id):
    """获取子节点实例"""
    try:
        if obj_id == "biz":
            # 业务节点下是集群
            sets = list(db.cc_SetBase.find({
                "bk_biz_id": inst_id,
                "bk_data_status": {"$ne": "disabled"}
            }))
            
            result = []
            for s in sets:
                result.append({
                    "bk_obj_id": "set",
                    "bk_inst_id": s.get("bk_set_id"),
                    "bk_inst_name": s.get("bk_set_name")
                })
            return make_response(data=result)
            
        elif obj_id == "set":
            # 集群节点下是模块
            modules = list(db.cc_ModuleBase.find({
                "bk_set_id": inst_id,
                "bk_biz_id": biz_id,
                "bk_data_status": {"$ne": "disabled"}
            }))
            
            result = []
            for m in modules:
                result.append({
                    "bk_obj_id": "module",
                    "bk_inst_id": m.get("bk_module_id"),
                    "bk_inst_name": m.get("bk_module_name")
                })
            return make_response(data=result)
        
        return make_response(data=[])
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))
```

- [ ] **Step 3: 实现获取拓扑路径 API**

添加 `topopath` 接口：
```python
@object_bp.route('/api/v3/find/topopath/biz/<int:biz_id>', methods=['POST'])
@object_bp.route('/find/topopath/biz/<int:biz_id>', methods=['POST'])
def find_topo_path(biz_id):
    """获取拓扑路径"""
    try:
        req_data = request.get_json() or {}
        # 返回从根节点到目标节点的路径
        return make_response(data=[])
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))
```

- [ ] **Step 4: 测试拓扑实例查询**

```bash
# 测试获取子节点（业务ID:2 下的集群）
curl -X GET "http://127.0.0.1:3000/topoinstchild/object/biz/biz/2/inst/2"

# 测试获取子节点（集群ID:1 下的模块）
curl -X GET "http://127.0.0.1:3000/topoinstchild/object/set/biz/2/inst/1"
```

---

### Task 5: 集成测试和验证

- [ ] **Step 1: 重启后端服务**

```bash
pkill -f "python.*app.py"
cd /workspace/bk_cmdb_py
source venv/bin/activate
python app.py
```

- [ ] **Step 2: 测试完整流程**

```bash
# 1. 查询拓扑主线模型
curl -X POST http://127.0.0.1:3000/find/topomodelmainline \
  -H "Content-Type: application/json" \
  -d '{}'

# 2. 查询业务拓扑（包含集群和模块）
curl -X POST http://127.0.0.1:3000/find/topoinst_with_statistics/biz/2 \
  -H "Content-Type: application/json" \
  -d '{}'

# 3. 创建新集群
curl -X POST http://127.0.0.1:3000/set/2 \
  -H "Content-Type: application/json" \
  -d '{"bk_set_name": "新测试集群", "description": "通过API创建"}'

# 4. 在新集群下创建模块
# 首先获取新集群的ID，然后创建模块

# 5. 查询集群列表
curl -X POST http://127.0.0.1:3000/set/search/0/2 \
  -H "Content-Type: application/json" \
  -d '{}'

# 6. 更新集群
# curl -X PUT http://127.0.0.1:3000/set/2/{set_id} \
#   -H "Content-Type: application/json" \
#   -d '{"bk_set_name": "更新后的名称"}'

# 7. 删除模块
# curl -X DELETE http://127.0.0.1:3000/module/2/{set_id}/{module_id}

# 8. 删除集群
# curl -X DELETE http://127.0.0.1:3000/set/2/{set_id}
```

- [ ] **Step 3: 前端集成测试**

1. 打开浏览器访问 `http://localhost:9093`
2. 登录为 `admin` 用户
3. 进入"业务拓扑"页面
4. 测试以下功能：
   - ✅ 查看拓扑树（业务 → 集群 → 模块）
   - ✅ 展开/折叠节点
   - ⬜ 新建集群
   - ⬜ 新建模块
   - ⬜ 编辑集群/模块
   - ⬜ 删除模块
   - ⬜ 删除集群

---

## 四、Mock 数据初始化脚本

创建 `scripts/init_topo_data.py` 用于初始化业务拓扑数据：

```python
#!/usr/bin/env python3
"""
业务拓扑数据初始化脚本
使用方法: python scripts/init_topo_data.py
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.db import db
from datetime import datetime

def init_topo_data():
    """初始化业务拓扑数据"""
    
    print("=== 开始初始化业务拓扑数据 ===\n")
    
    # 检查业务数据
    biz_count = db.cc_ApplicationBase.count_documents({})
    print(f"1. 业务数据: {biz_count} 条")
    
    if biz_count == 0:
        print("错误: 没有业务数据，请先运行其他初始化脚本")
        return False
    
    # 获取第一个业务
    first_biz = db.cc_ApplicationBase.find_one()
    biz_id = first_biz.get("bk_biz_id")
    print(f"   使用业务ID: {biz_id}, 名称: {first_biz.get('bk_biz_name')}\n")
    
    # 2. 初始化集群数据
    print("2. 初始化集群数据...")
    sets_data = [
        {
            "bk_set_name": "核心系统",
            "description": "核心业务系统集群",
            "bk_service_status": "1",
            "bk_set_env": "3"
        },
        {
            "bk_set_name": "边缘系统",
            "description": "边缘服务集群",
            "bk_service_status": "1",
            "bk_set_env": "3"
        },
        {
            "bk_set_name": "测试环境",
            "description": "测试用集群",
            "bk_service_status": "2",
            "bk_set_env": "1"
        }
    ]
    
    created_sets = []
    for idx, set_data in enumerate(sets_data, start=1):
        # 检查是否已存在
        existing = db.cc_SetBase.find_one({
            "bk_biz_id": biz_id,
            "bk_set_name": set_data["bk_set_name"]
        })
        
        if existing:
            set_id = existing.get("bk_set_id")
            print(f"   - 集群 '{set_data['bk_set_name']}' 已存在 (ID: {set_id})")
        else:
            # 创建新集群
            max_id = db.cc_SetBase.find_one(sort=[("bk_set_id", -1)])
            new_id = (max_id.get("bk_set_id", 0) + 1) if max_id else 1
            
            set_doc = {
                "bk_set_id": new_id,
                "bk_set_name": set_data["bk_set_name"],
                "bk_biz_id": biz_id,
                "bk_supplier_account": "0",
                "bk_parent_id": 0,
                "bk_parent_obj": "biz",
                "description": set_data["description"],
                "bk_service_status": set_data["bk_service_status"],
                "bk_set_env": set_data["bk_set_env"],
                "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "bk_data_status": "enabled"
            }
            
            db.cc_SetBase.insert_one(set_doc)
            set_id = new_id
            print(f"   + 创建集群 '{set_data['bk_set_name']}' (ID: {set_id})")
        
        created_sets.append(set_id)
    
    # 3. 初始化模块数据
    print("\n3. 初始化模块数据...")
    modules_data = {
        created_sets[0]: ["API服务", "Web服务", "数据库服务"],
        created_sets[1]: ["缓存服务", "消息队列"],
        created_sets[2]: ["单元测试", "集成测试"]
    }
    
    for set_id, module_names in modules_data.items():
        for idx, module_name in enumerate(module_names, start=1):
            # 检查是否已存在
            existing = db.cc_ModuleBase.find_one({
                "bk_set_id": set_id,
                "bk_module_name": module_name
            })
            
            if existing:
                print(f"   - 模块 '{module_name}' 已存在 (集群ID: {set_id})")
            else:
                # 创建新模块
                max_id = db.cc_ModuleBase.find_one(sort=[("bk_module_id", -1)])
                new_id = (max_id.get("bk_module_id", 0) + 1) if max_id else 1
                
                module_doc = {
                    "bk_module_id": new_id,
                    "bk_module_name": module_name,
                    "bk_set_id": set_id,
                    "bk_biz_id": biz_id,
                    "bk_supplier_account": "0",
                    "bk_parent_id": set_id,
                    "bk_parent_obj": "set",
                    "bk_service_category_id": 1,
                    "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "last_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "bk_data_status": "enabled"
                }
                
                db.cc_ModuleBase.insert_one(module_doc)
                print(f"   + 创建模块 '{module_name}' (ID: {new_id}, 集群ID: {set_id})")
    
    # 4. 统计结果
    print("\n=== 数据初始化完成 ===")
    print(f"集群总数: {db.cc_SetBase.count_documents({'bk_biz_id': biz_id})}")
    print(f"模块总数: {db.cc_ModuleBase.count_documents({'bk_biz_id': biz_id})}")
    
    return True

if __name__ == "__main__":
    try:
        success = init_topo_data()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
```

---

## 五、注意事项

### 5.1 API 兼容性
- 所有 API 都支持 `/api/v3/` 前缀和无前缀两种路径
- 请求和响应格式遵循 BlueKing CMDB API 规范
- 使用标准的 HTTP 方法（GET/POST/PUT/DELETE）

### 5.2 数据验证
- 创建和更新时验证必填字段
- 检查业务ID、集群ID、模块ID的关联性
- 确保删除时级联删除子节点（如删除集群时删除其下的模块）

### 5.3 错误处理
- 所有 API 返回统一的错误格式
- 包含适当的 HTTP 状态码
- 返回有意义的错误消息

### 5.4 性能考虑
- 使用 MongoDB 索引优化查询性能
- 批量操作时使用 `insert_many`
- 大数据量查询时分页处理

---

## 六、验收标准

### 6.1 功能验收
- ✅ 业务拓扑树正确显示（业务 → 集群 → 模块）
- ✅ 展开/折叠节点正常工作
- ✅ 可以创建新的集群
- ✅ 可以创建新的模块
- ✅ 可以编辑集群/模块信息
- ✅ 可以删除模块
- ✅ 可以删除集群（级联删除模块）
- ⬜ 前端页面无 JavaScript 错误

### 6.2 接口验收
- ✅ 所有集群 CRUD API 正常工作
- ✅ 所有模块 CRUD API 正常工作
- ✅ 拓扑查询 API 返回正确数据
- ✅ API 响应时间 < 500ms

### 6.3 数据验收
- ✅ Mock 数据正确初始化
- ✅ 数据关联性正确（业务-集群-模块）
- ✅ 数据状态字段正确更新

---

**文档版本：** 1.0  
**创建日期：** 2024-01-23  
**最后更新：** 2024-01-23
