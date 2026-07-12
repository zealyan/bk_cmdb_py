"""cmdb_server_py 核心业务层（对齐 bk-cmdb Go 端 ``source_controller/coreservice/core``）。

模型元数据相关的真实落库业务逻辑集中在 ``app.core.model``，路由层（``app.routes.model_routes``）
仅做 HTTP 参数处理与编排，调用本层完成 CRUD。
"""
