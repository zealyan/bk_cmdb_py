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
    
    MONGODB_URI = os.environ.get('MONGODB_URI') or 'mongodb://localhost:27017/'
    MONGODB_DB = os.environ.get('MONGODB_DB') or 'bk_cmdb'
    
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
    # 或者通过 LOGIN_VERSION=skip-login 开启（与Go版本保持一致）
    LOGIN_VERSION = os.environ.get('LOGIN_VERSION', '').lower()
    SKIP_LOGIN = os.environ.get('SKIP_LOGIN', 'false').lower() == 'true'
    if SKIP_LOGIN or LOGIN_VERSION == 'skip-login':
        SKIP_LOGIN = True
        print("[Skip Login] 已启用自动登录功能（开发模式）")
        if LOGIN_VERSION:
            print(f"[Skip Login] LOGIN_VERSION: {LOGIN_VERSION}")
    SKIP_LOGIN_USER = os.environ.get('SKIP_LOGIN_USER', 'admin')
    
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
