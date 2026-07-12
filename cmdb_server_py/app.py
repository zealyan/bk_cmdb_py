from flask import Flask, jsonify, request
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
from app.models.db import list_collections, get_collection_count, is_mongo_available

app = Flask(__name__)
app.config.from_object(Config)

Session(app)

# 配置 CORS，支持 withCredentials
# 包含 UI 服务端口（默认 8085），便于浏览器跨源调用 /api/v3
CORS(app, supports_credentials=True, origins=[
    'http://localhost:8080', 'http://127.0.0.1:8080',
    'http://localhost:8085', 'http://127.0.0.1:8085',
])

# 注册路由蓝图（带 /api/v3 前缀的版本）
app.register_blueprint(user_bp, url_prefix='/api/v3')
app.register_blueprint(biz_bp, url_prefix='/api/v3')
app.register_blueprint(admin_bp, url_prefix='/api/v3')
app.register_blueprint(object_bp, url_prefix='/api/v3')
app.register_blueprint(auth_bp, url_prefix='/api/v3')
app.register_blueprint(set_bp, url_prefix='/api/v3')
app.register_blueprint(module_bp, url_prefix='/api/v3')


def verify_db():
    """启动校验：确认 MongoDB 引擎连接有效。

    项目统一使用 bk-cmdb 的 ``cmdb`` 实例数据，不再做本地 mock 初始化。
    """
    if is_mongo_available():
        print(f"[DB] MongoDB 引擎连接有效，当前数据库: {Config.MONGODB_DB}")
    else:
        print("[DB] 警告: MongoDB 不可用，请检查 MONGODB_URI / 实例状态")






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
    verify_db()
    app.run(host='0.0.0.0', port=3000, debug=False, use_reloader=False)
