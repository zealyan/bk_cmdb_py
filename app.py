from flask import Flask, jsonify
from flask_cors import CORS
from flask_session import Session
from app.config import Config
from app.routes.user_routes import user_bp
from app.routes.biz_routes import biz_bp
from app.routes.admin_routes import admin_bp
from app.routes.object_routes import object_bp
from app.routes.auth_routes import auth_bp
from app.routes.set_routes import set_bp
from app.routes.module_routes import module_bp
from app.models.db import init_mock_data, list_collections, get_collection_count, is_mongo_available
from app.auth.policies import init_admin_super_permission, init_default_policies

app = Flask(__name__)
app.config.from_object(Config)

Session(app)

CORS(app, supports_credentials=True, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": [
            "Content-Type", 
            "Authorization", 
            "X-Requested-With", 
            "X-CSRFToken",
            "BK_User",
            "HTTP_BLUEKING_SUPPLIER_ID",
            "Cc_Request_Id",
            "traceparent"
        ],
        "expose_headers": [
            "Content-Type",
            "Authorization"
        ]
    }
})

# 同时注册两个版本的路由：带 /api/v3 前缀和不带前缀
app.register_blueprint(user_bp)
app.register_blueprint(user_bp, url_prefix='/api/v3', name='user_v3')
app.register_blueprint(biz_bp)
app.register_blueprint(biz_bp, url_prefix='/api/v3', name='biz_v3')
app.register_blueprint(admin_bp)
app.register_blueprint(admin_bp, url_prefix='/api/v3', name='admin_v3')
app.register_blueprint(object_bp)
app.register_blueprint(object_bp, url_prefix='/api/v3', name='object_v3')
app.register_blueprint(auth_bp)
app.register_blueprint(auth_bp, url_prefix='/api/v3', name='auth_v3')
app.register_blueprint(set_bp)
app.register_blueprint(set_bp, url_prefix='/api/v3', name='set_v3')
app.register_blueprint(module_bp)
app.register_blueprint(module_bp, url_prefix='/api/v3', name='module_v3')


def init_data():
    init_mock_data()
    # 初始化权限策略
    init_admin_super_permission()
    init_default_policies()


@app.route('/')
def index():
    return jsonify({
        "message": "BK-CMDB Python Backend",
        "status": "running",
        "data_sources": {
            "mongodb": is_mongo_available(),
            "pglite": True
        }
    })


@app.route('/health')
def health():
    return jsonify({
        "result": True,
        "code": 0,
        "message": "success",
        "data": "healthy"
    })


@app.route('/init/check')
def check_init():
    """检查数据库初始化状态"""
    try:
        mongo_collections = list_collections()
        
        mongo_stats = {}
        for col in mongo_collections:
            mongo_stats[col] = get_collection_count(col)
        
        return jsonify({
            "result": True,
            "code": 0,
            "message": "success",
            "data": {
                "mongodb": {
                    "available": is_mongo_available(),
                    "collections": mongo_collections,
                    "counts": mongo_stats
                },
                "relational_db": {
                    "available": False,
                    "note": "py-pglite 仅为附属副本库，不强制依赖"
                }
            }
        })
    except Exception as e:
        return jsonify({
            "result": False,
            "code": 500,
            "message": str(e)
        }), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({"result": False, "code": 404, "message": "Not Found"}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({"result": False, "code": 500, "message": "Internal Server Error"}), 500


if __name__ == '__main__':
    init_data()
    app.run(host='0.0.0.0', port=3000, debug=True)
