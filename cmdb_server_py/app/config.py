"""Configuration Module

应用配置模块，支持开发和生产环境的数据库配置。

Environment Variables:
    # 数据库环境选择
    DB_ENV: development|pglite|production  (默认: pglite)
    
    # MongoDB 配置
    MONGODB_URI: MongoDB 连接 URI
    MONGODB_DB: 数据库名称
    
    # py-pglite 配置（开发环境）
    PGLITE_DATA_DIR: py-pglite 数据目录
    
    # PostgreSQL 配置（生产环境）
    POSTGRES_HOST: PostgreSQL 主机
    POSTGRES_PORT: PostgreSQL 端口
    POSTGRES_DB: 数据库名称
    POSTGRES_USER: 用户名
    POSTGRES_PASSWORD: 密码

Usage:
    # 开发环境（默认）
    from app.config import Config
    
    # 生产环境
    export DB_ENV=production
    export POSTGRES_HOST=localhost
    export POSTGRES_DB=bk_cmdb
    export POSTGRES_USER=postgres
    export POSTGRES_PASSWORD=secret
"""

import os
import json


class Config:
    """应用配置类
    
    Attributes:
        SECRET_KEY: Flask 密钥
        DEBUG: 调试模式
        DB_ENV: 数据库环境 (pglite/postgresql)
        
        # MongoDB
        MONGODB_URI: MongoDB 连接 URI
        MONGODB_DB: 数据库名称
        
        # py-pglite (开发环境)
        PGLITE_DATA_DIR: py-pglite 数据目录
        
        # PostgreSQL (生产环境)
        POSTGRES_HOST: PostgreSQL 主机
        POSTGRES_PORT: PostgreSQL 端口
        POSTGRES_DB: PostgreSQL 数据库名
        POSTGRES_USER: PostgreSQL 用户
        POSTGRES_PASSWORD: PostgreSQL 密码
    """
    
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-for-bk-cmdb'
    DEBUG = True
    
    DB_ENV = os.environ.get('DB_ENV', 'pglite').lower()
    
    # 项目统一使用 bk-cmdb 通过 initdb 初始化的 ``cmdb`` MongoDB 实例。
    # 不再连接本项目私有的 bk_cmdb 库（其 mock 数据已清理）。
    MONGODB_URI = os.environ.get('MONGODB_URI') or 'mongodb://cc:cc@127.0.0.1:27017/cmdb?authSource=cmdb'
    MONGODB_DB = os.environ.get('MONGODB_DB') or 'cmdb'
    
    PGLITE_DATA_DIR = os.environ.get('PGLITE_DATA_DIR') or './pglite_data'
    
    POSTGRES_HOST = os.environ.get('POSTGRES_HOST', 'localhost')
    POSTGRES_PORT = os.environ.get('POSTGRES_PORT', '5432')
    POSTGRES_DB = os.environ.get('POSTGRES_DB', 'bk_cmdb')
    POSTGRES_USER = os.environ.get('POSTGRES_USER', 'postgres')
    POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD', '')
    
    # Session Configuration
    SESSION_TYPE = os.environ.get('SESSION_TYPE', 'filesystem')
    SESSION_PERMANENT = os.environ.get('SESSION_PERMANENT', 'true').lower() == 'true'
    SESSION_USE_SIGNER = os.environ.get('SESSION_USE_SIGNER', 'true').lower() == 'true'
    SESSION_KEY_PREFIX = os.environ.get('SESSION_KEY_PREFIX', 'bk_cmdb:')
    
    # Skip Login Configuration (开发环境跳过登录)
    # 通过环境变量 SKIP_LOGIN=true 开启自动登录
    SKIP_LOGIN = os.environ.get('SKIP_LOGIN', 'false').lower() == 'true'
    if SKIP_LOGIN:
        print("[Skip Login] 已启用自动登录功能（开发模式）")
    SKIP_LOGIN_USER = os.environ.get('SKIP_LOGIN_USER', 'admin')

    # 内置管理员（internal 鉴权模式）
    # 与 bk-cmdb common.yaml webServer.session.userInfo: admin:admin 对齐。
    # 仅作为运行时鉴权兜底，不写入 MongoDB（项目只保留 initdb 原生数据）。
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin')

    # 内置演示用户（最小依赖部署下无外部用户目录/IAM 时使用）。
    # 前端「创建业务」表单的运维人员(bk_operator)/开发人员(bk_biz_developer)
    # 选择组件经 GET /api/v3/user/list 拉取候选，逐项正确映射为
    #   { username: english_name, display_name: chinese_name }
    # 与 bk-cmdb Go 端 web_server GetUserList 返回的
    #   LoginSystemUserInfo{ CnName->chinese_name, EnName->english_name } 对齐。
    # 可通过环境变量 CMDB_DEFAULT_USERS 以 JSON 数组覆盖（例如：
    #   '[{"english_name":"alice","chinese_name":"爱丽丝","role":"user"}]'）。
    _default_users_json = os.environ.get('CMDB_DEFAULT_USERS', '')
    if _default_users_json:
        try:
            DEFAULT_USERS = json.loads(_default_users_json)
        except Exception:
            DEFAULT_USERS = None
    else:
        DEFAULT_USERS = None
    if not DEFAULT_USERS:
        DEFAULT_USERS = [
            {"english_name": "admin", "chinese_name": "管理员", "username": "admin", "role": "admin"},
            {"english_name": "ops01", "chinese_name": "运维一号", "username": "ops01", "role": "user"},
            {"english_name": "ops02", "chinese_name": "运维二号", "username": "ops02", "role": "user"},
            {"english_name": "dev01", "chinese_name": "开发一号", "username": "dev01", "role": "user"},
            {"english_name": "dev02", "chinese_name": "开发二号", "username": "dev02", "role": "user"},
        ]

    @classmethod
    def is_superuser(cls, username) -> bool:
        """判断是否为内置超级管理员（internal 模式下的 admin 账户）。

        超级管理员不受 user_business 业务权限表约束，可访问全部业务与拓扑。
        """
        return bool(username) and username == cls.ADMIN_USERNAME
    
    @classmethod
    def is_production(cls) -> bool:
        """检查是否为生产环境
        
        Returns:
            bool: 是否为生产环境
        """
        return cls.DB_ENV == 'production'
    
    @classmethod
    def is_development(cls) -> bool:
        """检查是否为开发环境
        
        Returns:
            bool: 是否为开发环境
        """
        return cls.DB_ENV in ('pglite', 'development', 'auto')
    
    @classmethod
    def get_postgres_dsn(cls) -> str:
        """获取 PostgreSQL DSN 连接字符串
        
        Returns:
            str: DSN 连接字符串
        """
        return (
            f"host={cls.POSTGRES_HOST} "
            f"port={cls.POSTGRES_PORT} "
            f"dbname={cls.POSTGRES_DB} "
            f"user={cls.POSTGRES_USER} "
            f"password={cls.POSTGRES_PASSWORD}"
        )
