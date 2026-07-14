"""
业务拓扑 - 集群（Set）路由模块
提供集群的 CRUD 操作接口
"""

from flask import Blueprint, jsonify, request
from app.models.db import db, get_db_connection, next_sequence
from datetime import datetime

set_bp = Blueprint('set', __name__)


def make_response(result=True, code=0, message="success", data=None, **kwargs):
    """统一响应格式（兼容 bk-cmdb 前端 bk_error_code 判定）"""
    if result and code == 0:
        bk_error_code, bk_error_msg = 0, ""
    else:
        bk_error_code = code if code != 0 else 500
        bk_error_msg = message
    response = {
        "bk_error_code": bk_error_code,
        "bk_error_msg": bk_error_msg,
        "result": result,
        "code": code,
        "message": message,
    }
    if data is not None:
        response["data"] = data
    response.update(kwargs)
    return jsonify(response)


def _build_set_doc(conn, biz_id, set_data):
    """
    构造并落库一个集群（Set）文档，返回剔除 MongoDB _id 后的可序列化 dict。

    关键点：
    前端业务拓扑“新建集群”走 handleCreateSetNode -> createSet 单例 action，
    会把多行集群名组装成 **数组** POST 到 /set/{bizId}，并期望响应 data 为
    [{data:{bk_set_id,bk_set_name,...}}, ...]（每个元素带 .data 包装）。

    同时拓扑树节点以 bk_inst_id / bk_inst_name 标识实例（handleCreateNode
    会把响应直接合并进节点对象），因此这里补齐这两个字段，与
    bk_set_id / bk_set_name 对齐，确保本地插入的新节点能正确渲染。
    """
    bk_set_name = set_data.get('bk_set_name')
    bk_supplier_account = set_data.get('bk_supplier_account', '0')

    # 全局原子自增 ID（对齐 Go NextSequence("cc_SetBase")）
    new_id = next_sequence(conn, "cc_SetBase")

    set_doc = {
        "bk_set_id": new_id,
        "bk_set_name": bk_set_name,
        "bk_biz_id": biz_id,
        "bk_supplier_account": bk_supplier_account,
        "bk_parent_id": set_data.get('bk_parent_id', 0),
        "bk_parent_obj": "biz",
        "description": set_data.get('description', ''),
        "bk_service_status": set_data.get('bk_service_status', '1'),
        "bk_set_env": set_data.get('bk_set_env', '3'),
        "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "bk_data_status": "enabled",
    }
    # 拓扑树实例标识字段（与 bk_set_id/bk_set_name 对齐）
    set_doc["bk_inst_id"] = new_id
    set_doc["bk_inst_name"] = bk_set_name

    conn.cc_SetBase.insert_one(set_doc)
    # 剔除 MongoDB 注入的 _id（ObjectId 不可 JSON 序列化，否则 500）
    set_doc.pop("_id", None)
    return set_doc


@set_bp.route('/api/v3/set/<int:biz_id>', methods=['POST'])
@set_bp.route('/set/<int:biz_id>', methods=['POST'])
def create_set(biz_id):
    """
    创建集群
    POST /set/{bkBizId}

    前端业务拓扑“新建集群”（create-set 组件 -> handleCreateSetNode）会把多行
    集群名组装成 **数组** POST 到本接口，因此本接口同时兼容：
      - 数组：逐条创建，返回 [{data:{...}}, ...]（对齐 handleCreateSetNode 的 n.data 读取）
      - 单对象：创建一条，返回完整节点文档（含 bk_inst_id/bk_inst_name）

    单对象请求体:
    {
        "bk_set_name": "集群名称",
        "bk_supplier_account": "0",
        "description": "描述",
        "bk_service_status": "1",
        "bk_set_env": "3"
    }

    响应（数组）:
    {
        "result": true, "code": 0, "message": "success",
        "data": [{"data": {"bk_set_id": 123, "bk_set_name": "集群1", ...}}]
    }
    """
    try:
        req_data = request.get_json(silent=True)
        if req_data is None:
            req_data = {}

        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        # 数组形态：前端拓扑“新建集群”批量创建（多行集群名）
        if isinstance(req_data, list):
            results = []
            for item in req_data:
                if not isinstance(item, dict):
                    results.append({"error_message": "无效的集群数据"})
                    continue
                bk_set_name = item.get('bk_set_name')
                if not bk_set_name:
                    results.append({"error_message": "集群名称不能为空"})
                    continue
                try:
                    doc = _build_set_doc(conn, biz_id, item)
                    results.append({"data": doc})
                except Exception as ex:
                    results.append({"error_message": str(ex)})
            return make_response(data=results)

        # 单对象形态：兼容直接调用 / 集成态
        bk_set_name = req_data.get('bk_set_name')
        if not bk_set_name:
            return make_response(result=False, code=400, message="集群名称不能为空")

        doc = _build_set_doc(conn, biz_id, req_data)
        return make_response(data=doc)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@set_bp.route('/api/v3/set/<int:biz_id>/batch', methods=['POST'])
@set_bp.route('/set/<int:biz_id>/batch', methods=['POST'])
def create_sets_batch(biz_id):
    """
    批量创建集群
    POST /set/{bkBizId}/batch

    业务拓扑“新建集群”的 createSet 组件方法会 dispatch objectSet/createset
    走到本接口，且 handleCreateSetNode 期望响应 data 为
    [{data:{bk_set_id,bk_set_name,...}}, ...]（每个元素带 .data 包装），
    与单例端点 /set/{bizId} 的数组形态保持一致。

    请求体:
    {
        "sets": [
            {"bk_set_name": "集群1", "description": "..."},
            {"bk_set_name": "集群2", "description": "..."}
        ]
    }

    响应:
    {
        "result": true, "code": 0, "message": "success",
        "data": [
            {"data": {"bk_set_id": 123, "bk_set_name": "集群1", ...}},
            {"data": {"bk_set_id": 124, "bk_set_name": "集群2", ...}}
        ]
    }
    """
    try:
        req_data = request.get_json(silent=True) or {}
        sets_data = req_data.get('sets', [])

        if not sets_data:
            return make_response(result=False, code=400, message="sets 列表不能为空")

        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        created_sets = []

        for set_data in sets_data:
            if not isinstance(set_data, dict):
                continue
            bk_set_name = set_data.get('bk_set_name')
            if not bk_set_name:
                continue
            # 复用 _build_set_doc：落库并返回含 bk_inst_id/bk_inst_name 的完整文档。
            # 按前端 handleCreateSetNode 的契约，每个元素需包一层 .data。
            created_sets.append({"data": _build_set_doc(conn, biz_id, set_data)})

        return make_response(data=created_sets)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@set_bp.route('/api/v3/set/search/<supplier_account>/<int:biz_id>', methods=['POST'])
@set_bp.route('/set/search/<supplier_account>/<int:biz_id>', methods=['POST'])
def search_set(supplier_account, biz_id):
    """
    查询集群列表
    POST /set/search/{bkSupplierAccount}/{bkBizId}

    请求体:
    {
        "condition": {"bk_set_id": 3},          # 业务拓扑节点详情会带单条精确条件
        "fields": [],
        "page": {"start": 0, "limit": 20}
    }

    响应（bk-cmdb 标准 {count, info} 信封）:
    {
        "result": true, "code": 0, "message": "success",
        "data": {
            "count": 1,
            "info": [{"bk_set_id": 3, "bk_set_name": "...", "bk_inst_id": 3, "bk_inst_name": "...", ...}]
        }
    }

    说明:
    前端业务拓扑节点详情 getSetInstance 会 dispatch objectSet/searchSet 并读取
    response.data.info[0]（见 1077.*.js 中 getSetInstance 的 n.info[0]），因此必须返回
    {count, info} 信封而非裸数组；同时需合并请求体 condition 做精确过滤，否则点击任意
    集群节点都会取回 biz 下第一条集群、导致详情面板张冠李戴。
    """
    try:
        req_data = request.get_json() or {}

        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        # 基础过滤（对齐 bk-cmdb set search）
        filter_query = {
            "bk_biz_id": biz_id,
            "bk_supplier_account": supplier_account,
            "bk_data_status": {"$ne": "disabled"},
        }

        # 合并请求体 condition（支持裸值 / {$eq: x} / 其它 Mongo 操作符）
        for k, v in (req_data.get("condition") or {}).items():
            if isinstance(v, dict) and "$eq" in v:
                filter_query[k] = v["$eq"]
            else:
                filter_query[k] = v

        page = req_data.get("page") or {}
        start = int(page.get("start", 0) or 0)
        limit = int(page.get("limit", 20) or 20)

        total = conn.cc_SetBase.count_documents(filter_query)
        sets = list(conn.cc_SetBase.find(filter_query).skip(start).limit(limit))

        info = []
        for s in sets:
            info.append({
                "bk_set_id": s.get("bk_set_id"),
                "bk_set_name": s.get("bk_set_name"),
                "bk_biz_id": s.get("bk_biz_id"),
                "bk_supplier_account": s.get("bk_supplier_account"),
                "bk_parent_id": s.get("bk_parent_id"),
                "bk_parent_obj": s.get("bk_parent_obj"),
                "description": s.get("description"),
                "bk_service_status": s.get("bk_service_status"),
                "bk_set_env": s.get("bk_set_env"),
                # 拓扑树实例标识字段：与 bk_set_id/bk_set_name 对齐，确保详情面板正确渲染
                "bk_inst_id": s.get("bk_inst_id", s.get("bk_set_id")),
                "bk_inst_name": s.get("bk_inst_name", s.get("bk_set_name")),
                "create_time": s.get("create_time"),
                "last_time": s.get("last_time"),
            })

        # 前端按 data.info[0] 读取，故返回 {count, info} 信封
        return make_response(data={"count": total, "info": info})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


@set_bp.route('/api/v3/set/<int:biz_id>/<int:set_id>', methods=['PUT'])
@set_bp.route('/set/<int:biz_id>/<int:set_id>', methods=['PUT'])
def update_set(biz_id, set_id):
    """
    更新集群信息
    PUT /set/{bkBizId}/{bkSetId}
    
    请求体:
    {
        "bk_set_name": "新名称",
        "description": "新描述",
        "bk_service_status": "1",
        "bk_set_env": "3"
    }
    
    响应:
    {
        "result": true,
        "code": 0,
        "message": "success",
        "data": {"bk_set_id": 123}
    }
    """
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        req_data = request.get_json() or {}
        
        update_fields = {
            "last_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        for field in ["bk_set_name", "description", "bk_service_status", "bk_set_env"]:
            if field in req_data and req_data[field] is not None:
                update_fields[field] = req_data[field]
        
        result = conn.cc_SetBase.update_one(
            {"bk_set_id": set_id, "bk_biz_id": biz_id},
            {"$set": update_fields}
        )
        
        if result.modified_count > 0 or result.matched_count > 0:
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
    """
    删除集群（级联删除集群下的所有模块）
    DELETE /set/{bkBizId}/{bkSetId}
    
    响应:
    {
        "result": true,
        "code": 0,
        "message": "success",
        "data": {"bk_set_id": 123}
    }
    """
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")

        conn.cc_ModuleBase.delete_many({"bk_set_id": set_id, "bk_biz_id": biz_id})
        
        result = conn.cc_SetBase.delete_one({
            "bk_set_id": set_id,
            "bk_biz_id": biz_id
        })
        
        if result.deleted_count > 0:
            return make_response(data={"bk_set_id": set_id})
        else:
            return make_response(result=False, code=404, message="集群不存在")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))
