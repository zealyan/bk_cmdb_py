from flask import Blueprint, request, jsonify, g
from app.models.db import db, init_mock_data, get_db_connection
from datetime import datetime
import time

biz_bp = Blueprint('biz', __name__)


def make_response(result=True, code=0, message="success", data=None):
    return jsonify({
        "result": result,
        "code": code,
        "message": message,
        "data": data
    })


def get_current_time():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def get_next_biz_id():
    """获取下一个业务ID"""
    conn = get_db_connection()
    if conn is None:
        return int(time.time() * 1000)
    max_biz = conn.cc_ApplicationBase.find_one(
        sort=[('bk_biz_id', -1)]
    )
    if max_biz and max_biz.get('bk_biz_id'):
        return max_biz['bk_biz_id'] + 1
    return 6


def build_query_conditions(condition):
    """构建MongoDB查询条件"""
    query = {}
    if not condition:
        return query
    
    for key, value in condition.items():
        if isinstance(value, dict):
            # 处理操作符，如 $eq, $ne, $in
            if '$eq' in value:
                query[key] = value['$eq']
            elif '$ne' in value:
                query[key] = {'$ne': value['$ne']}
            elif '$in' in value:
                query[key] = {'$in': value['$in']}
            elif '$gte' in value or '$lte' in value:
                query[key] = {}
                if '$gte' in value:
                    query[key]['$gte'] = value['$gte']
                if '$lte' in value:
                    query[key]['$lte'] = value['$lte']
        else:
            query[key] = value
    
    return query


@biz_bp.route('/biz/search/<account>', methods=['POST'])
def biz_search(account):
    """按条件搜索业务"""
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")
        
        # 兼容多种请求数据格式
        req_data = {}
        if request.is_json:
            req_data = request.get_json() or {}
        elif request.form:
            req_data = request.form.to_dict()
        elif request.data:
            try:
                import json
                req_data = json.loads(request.data)
            except:
                req_data = {}
        condition = req_data.get('condition', {})
        fields = req_data.get('fields', [])
        page = req_data.get('page', {})
        start = page.get('start', 0)
        limit = page.get('limit', 20)
        sort = page.get('sort', 'bk_biz_id')
        
        # 构建查询条件
        query = build_query_conditions(condition)
        
        # 添加默认条件：只查询启用的业务
        if 'bk_data_status' not in query:
            query['bk_data_status'] = {'$ne': 'disabled'}
        
        # 查询数据
        cursor = conn.cc_ApplicationBase.find(query)
        
        # 排序
        if sort:
            sort_direction = 1
            if sort.startswith('-'):
                sort_direction = -1
                sort = sort[1:]
            cursor = cursor.sort(sort, sort_direction)
        
        # 分页
        total_count = conn.cc_ApplicationBase.count_documents(query)
        businesses = list(cursor.skip(start).limit(limit))
        
        # 移除_id字段
        for biz in businesses:
            biz.pop('_id', None)
        
        return make_response(data={"count": total_count, "info": businesses})
    except Exception as e:
        print(f"搜索业务失败: {e}")
        return make_response(result=False, code=500, message=str(e))


@biz_bp.route('/biz/search/web', methods=['POST'])
def biz_search_web():
    """Web端搜索业务（与search接口相同，为了兼容性）"""
    return biz_search('0')


@biz_bp.route('/biz/simplify', methods=['GET'])
def biz_simplify():
    """获取简化的业务列表"""
    try:
        conn = get_db_connection()
        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")
        
        businesses = list(conn.cc_ApplicationBase.find(
            {'bk_data_status': {'$ne': 'disabled'}},
            {'bk_biz_id': 1, 'bk_biz_name': 1, '_id': 0}
        ).sort('bk_biz_id', 1))
        return make_response(data=businesses)
    except Exception as e:
        print(f"获取简化业务列表失败: {e}")
        return make_response(result=False, code=500, message=str(e))


@biz_bp.route('/biz/with_reduced', methods=['GET'])
def biz_with_reduced():
    """获取带权限信息的业务列表"""
    try:
        conn = get_db_connection()

        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")
        
        # 获取当前用户
        current_username = getattr(g, 'current_user', None)
        
        # 如果有当前用户，只返回用户有权限的业务
        if current_username:
            user_biz_list = list(conn.user_business.find(
                {'username': current_username},
                {'bk_biz_id': 1, '_id': 0}
            ))
            user_biz_ids = [ub['bk_biz_id'] for ub in user_biz_list]
            
            # 查询这些业务
            businesses = list(conn.cc_ApplicationBase.find(
                {'bk_biz_id': {'$in': user_biz_ids}, 'bk_data_status': {'$ne': 'disabled'}},
                {'_id': 0}
            ).sort('bk_biz_id', 1))
        else:
            # 没有用户信息，返回所有业务
            businesses = list(conn.cc_ApplicationBase.find(
                {'bk_data_status': {'$ne': 'disabled'}},
                {'_id': 0}
            ).sort('bk_biz_id', 1))
        
        return make_response(data={"info": businesses})
    except Exception as e:
        print(f"获取带权限信息的业务列表失败: {e}")
        return make_response(result=False, code=500, message=str(e))


@biz_bp.route('/biz/<account>', methods=['POST'])
def create_business(account):
    """创建新业务"""
    try:
        # 兼容多种请求数据格式
        req_data = {}
        if request.is_json:
            req_data = request.get_json() or {}
        elif request.form:
            req_data = request.form.to_dict()
        elif request.data:
            try:
                import json
                req_data = json.loads(request.data)
            except:
                req_data = {}
        
        conn = get_db_connection()

        
        if conn is None:
            return make_response(result=False, code=500, message="数据库不可用")
        
        # 获取下一个业务ID
        new_biz_id = get_next_biz_id()
        
        # 构建业务数据
        current_time = get_current_time()
        business_data = {
            'bk_biz_id': new_biz_id,
            'bk_biz_name': req_data.get('bk_biz_name', ''),
            'bk_supplier_account': account,
            'operator': req_data.get('operator', getattr(g, 'current_user', 'admin')),
            'bk_maintainer': req_data.get('bk_maintainer', getattr(g, 'current_user', 'admin')),
            'time_zone': req_data.get('time_zone', 'Asia/Shanghai'),
            'create_time': current_time,
            'last_time': current_time,
            'bk_data_status': 'enabled'
        }
        
        # 添加其他字段
        for key, value in req_data.items():
            if key not in business_data:
                business_data[key] = value
        
        # 插入数据库
        conn.cc_ApplicationBase.insert_one(business_data)
        
        # 移除_id字段
        business_data.pop('_id', None)
        
        return make_response(data=business_data)
    except Exception as e:
        print(f"创建业务失败: {e}")
        return make_response(result=False, code=500, message=str(e))


@biz_bp.route('/biz/<account>/<int:biz_id>', methods=['PUT'])
def update_business(account, biz_id):
    """更新单个业务"""
    try:
        # 兼容多种请求数据格式
        req_data = {}
        if request.is_json:
            req_data = request.get_json() or {}
        elif request.form:
            req_data = request.form.to_dict()
        elif request.data:
            try:
                import json
                req_data = json.loads(request.data)
            except:
                req_data = {}
        
        conn = get_db_connection()

        
        if conn is None:
            return make_response(result=False, code=500, message="数据库不可用")
        
        # 移除不可更新的字段
        update_data = req_data.copy()
        update_data.pop('bk_biz_id', None)
        update_data.pop('create_time', None)
        
        # 更新最后修改时间
        update_data['last_time'] = get_current_time()
        
        # 执行更新
        result = conn.cc_ApplicationBase.update_one(
            {'bk_biz_id': biz_id},
            {'$set': update_data}
        )
        
        if result.matched_count == 0:
            return make_response(result=False, code=404, message="业务不存在")
        
        # 获取更新后的业务数据
        updated_biz = conn.cc_ApplicationBase.find_one(
            {'bk_biz_id': biz_id},
            {'_id': 0}
        )
        
        return make_response(data=updated_biz)
    except Exception as e:
        print(f"更新业务失败: {e}")
        return make_response(result=False, code=500, message=str(e))


@biz_bp.route('/updatemany/biz/property', methods=['PUT'])
def batch_update_business():
    """批量更新业务属性"""
    try:
        # 兼容多种请求数据格式
        req_data = {}
        if request.is_json:
            req_data = request.get_json() or {}
        elif request.form:
            req_data = request.form.to_dict()
        elif request.data:
            try:
                import json
                req_data = json.loads(request.data)
            except:
                req_data = {}
        properties = req_data.get('properties', {})
        condition = req_data.get('condition', {})
        
        conn = get_db_connection()

        
        if conn is None:
            return make_response(result=False, code=500, message="数据库不可用")
        
        # 构建查询条件
        query = build_query_conditions(condition)
        
        # 更新数据
        update_data = properties.copy()
        update_data['last_time'] = get_current_time()
        
        # 执行批量更新
        result = conn.cc_ApplicationBase.update_many(
            query,
            {'$set': update_data}
        )
        
        return make_response(data={"matched_count": result.matched_count, "modified_count": result.modified_count})
    except Exception as e:
        print(f"批量更新业务失败: {e}")
        return make_response(result=False, code=500, message=str(e))


@biz_bp.route('/biz/status/disabled/<account>/<int:biz_id>', methods=['PUT'])
def archive_business(account, biz_id):
    """归档业务（禁用）"""
    try:
        conn = get_db_connection()

        if conn is None:
            return make_response(result=False, code=500, message="数据库不可用")
        
        # 检查是否是蓝鲸业务
        business = conn.cc_ApplicationBase.find_one({'bk_biz_id': biz_id})
        if business and business.get('bk_biz_name') == '蓝鲸':
            return make_response(result=False, code=400, message="内置业务不可归档")
        
        # 执行归档
        result = conn.cc_ApplicationBase.update_one(
            {'bk_biz_id': biz_id},
            {'$set': {
                'bk_data_status': 'disabled',
                'last_time': get_current_time()
            }}
        )
        
        if result.matched_count == 0:
            return make_response(result=False, code=404, message="业务不存在")
        
        return make_response(message="业务归档成功")
    except Exception as e:
        print(f"归档业务失败: {e}")
        return make_response(result=False, code=500, message=str(e))


@biz_bp.route('/biz/status/enabled/<account>/<int:biz_id>', methods=['PUT'])
def restore_business(account, biz_id):
    """恢复业务（启用）"""
    try:
        conn = get_db_connection()

        if conn is None:
            return make_response(result=False, code=500, message="数据库不可用")
        
        # 执行恢复
        result = conn.cc_ApplicationBase.update_one(
            {'bk_biz_id': biz_id},
            {'$set': {
                'bk_data_status': 'enabled',
                'last_time': get_current_time()
            }}
        )
        
        if result.matched_count == 0:
            return make_response(result=False, code=404, message="业务不存在")
        
        return make_response(message="业务恢复成功")
    except Exception as e:
        print(f"恢复业务失败: {e}")
        return make_response(result=False, code=500, message=str(e))


@biz_bp.route('/biz/search/id/<int:biz_id>', methods=['GET'])
def get_business_by_id(biz_id):
    """根据ID获取业务详情"""
    try:
        conn = get_db_connection()

        if conn is None:
            return make_response(result=False, code=500, message="数据库连接失败")
        
        business = conn.cc_ApplicationBase.find_one(
            {'bk_biz_id': biz_id},
            {'_id': 0}
        )
        if not business:
            return make_response(result=False, code=404, message="业务不存在")
        return make_response(data=business)
    except Exception as e:
        print(f"获取业务详情失败: {e}")
        return make_response(result=False, code=500, message=str(e))
