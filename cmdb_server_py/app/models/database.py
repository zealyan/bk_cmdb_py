"""Database Abstraction Layer

统一的数据库抽象层，同时支持 py-pglite（开发环境）和 PostgreSQL（生产环境）。

Design Principles:
    1. Database-agnostic: 同一套代码兼容两种数据库
    2. SQLAlchemy-first: 优先使用 ORM，必要时使用原生 SQL
    3. Environment-aware: 根据配置自动选择数据库

Architecture:
    Config → DatabaseFactory → SQLAlchemy Engine → ORM/SQL

Usage:
    # 开发环境（默认使用 py-pglite）
    from app.models.database import get_engine, get_connection
    
    # 生产环境（使用 PostgreSQL）
    export DB_ENV=production
    from app.models.database import get_engine, get_connection
"""

import os
from enum import Enum
from typing import Optional, Any, Dict, List, Tuple
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool


class DBEnvironment(Enum):
    """数据库环境枚举"""
    PGLITE = "pglite"      # 开发环境：py-pglite
    POSTGRESQL = "postgresql"  # 生产环境：PostgreSQL
    AUTO = "auto"          # 自动检测


class DatabaseFactory:
    """数据库工厂类
    
    根据环境配置创建和管理数据库连接，支持 py-pglite 和 PostgreSQL。
    
    Attributes:
        _engine: SQLAlchemy 引擎实例
        _session_factory: SQLAlchemy Session 工厂
        _environment: 当前数据库环境
    """
    
    _engine = None
    _session_factory = None
    _environment = None
    _initialized = False
    
    @classmethod
    def get_environment(cls) -> DBEnvironment:
        """获取当前数据库环境
        
        Returns:
            DBEnvironment: 当前环境
        """
        if cls._environment:
            return cls._environment
        
        db_env = os.environ.get('DB_ENV', 'auto').lower()
        
        if db_env == 'production':
            cls._environment = DBEnvironment.POSTGRESQL
        elif db_env == 'development' or db_env == 'pglite':
            cls._environment = DBEnvironment.PGLITE
        else:
            cls._environment = DBEnvironment.PGLITE
        
        return cls._environment
    
    @classmethod
    def _create_pglite_engine(cls):
        """创建 py-pglite 引擎
        
        Returns:
            Engine: SQLAlchemy 引擎
        """
        from app.config import Config
        import psycopg
        
        data_dir = os.path.abspath(Config.PGLITE_DATA_DIR)
        os.makedirs(data_dir, exist_ok=True)
        
        socket_path = os.path.join(data_dir, '.s.PGSQL.5432')
        
        import subprocess
        import time
        subprocess.Popen(
            ['node', 'pglite_manager.js'],
            cwd=data_dir,
            env={**os.environ, 'NODE_PATH': f'{data_dir}/node_modules'},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        for _ in range(30):
            if os.path.exists(socket_path):
                break
            time.sleep(1)
        
        if os.path.exists(socket_path):
            os.chmod(socket_path, 0o777)
        else:
            print(f"Warning: Socket file not found at {socket_path}, continuing without chmod")
        
        def get_connection():
            return psycopg.connect(
                host=data_dir,
                dbname='postgres',
                user='postgres'
            )
        
        engine = create_engine(
            f"postgresql+psycopg://",
            creator=get_connection,
            poolclass=StaticPool,
            echo=False
        )
        
        print(f"[Database] 使用 py-pglite (开发环境) - 数据目录: {data_dir}")
        return engine
    
    @classmethod
    def _create_postgresql_engine(cls):
        """创建 PostgreSQL 引擎
        
        Returns:
            Engine: SQLAlchemy 引擎
        """
        from app.config import Config
        import psycopg
        
        host = os.environ.get('POSTGRES_HOST', 'localhost')
        port = os.environ.get('POSTGRES_PORT', '5432')
        dbname = os.environ.get('POSTGRES_DB', 'bk_cmdb')
        user = os.environ.get('POSTGRES_USER', 'postgres')
        password = os.environ.get('POSTGRES_PASSWORD', '')
        
        dsn = f"host={host} port={port} dbname={dbname} user={user} password={password}"
        
        engine = create_engine(
            f"postgresql+psycopg://{user}:{password}@{host}:{port}/{dbname}",
            pool_size=5,
            max_overflow=10,
            echo=False
        )
        
        print(f"[Database] 使用 PostgreSQL (生产环境)")
        return engine
    
    @classmethod
    def get_engine(cls):
        """获取 SQLAlchemy 引擎
        
        根据环境配置返回对应的数据库引擎。
        
        Returns:
            Engine: SQLAlchemy 引擎实例
        """
        if cls._engine is None:
            env = cls.get_environment()
            
            if env == DBEnvironment.POSTGRESQL:
                cls._engine = cls._create_postgresql_engine()
            else:
                cls._engine = cls._create_pglite_engine()
        
        return cls._engine
    
    @classmethod
    def get_session_factory(cls) -> sessionmaker:
        """获取 Session 工厂
        
        Returns:
            sessionmaker: SQLAlchemy Session 工厂
        """
        if cls._session_factory is None:
            engine = cls.get_engine()
            cls._session_factory = sessionmaker(bind=engine)
        
        return cls._session_factory
    
    @classmethod
    def get_session(cls) -> Session:
        """获取数据库 Session
        
        Returns:
            Session: SQLAlchemy Session
        """
        factory = cls.get_session_factory()
        return factory()
    
    @classmethod
    def get_connection(cls):
        """获取原生数据库连接
        
        用于需要原生连接的场合（如事务管理）。
        
        Returns:
            Connection: 数据库连接
        """
        engine = cls.get_engine()
        return engine.connect()
    
    @classmethod
    def execute(cls, sql: str, params: Optional[Dict] = None) -> List:
        """执行 SQL 查询
        
        Args:
            sql (str): SQL 语句
            params (Dict, optional): 查询参数
            
        Returns:
            List: 查询结果
        """
        engine = cls.get_engine()
        with engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            if result.returns_rows:
                return result.fetchall()
            return []
    
    @classmethod
    def execute_many(cls, sql: str, params_list: List[Dict]) -> None:
        """批量执行 SQL
        
        Args:
            sql (str): SQL 语句
            params_list (List[Dict]): 参数列表
        """
        engine = cls.get_engine()
        with engine.connect() as conn:
            for params in params_list:
                conn.execute(text(sql), params)
            conn.commit()
    
    @classmethod
    def create_tables(cls, base):
        """创建所有表
        
        Args:
            base: SQLAlchemy Base 类
        """
        engine = cls.get_engine()
        base.metadata.create_all(engine)
        print(f"[Database] 表结构创建完成")
    
    @classmethod
    def list_tables(cls) -> List[str]:
        """列出所有表
        
        Returns:
            List[str]: 表名列表
        """
        engine = cls.get_engine()
        inspector = inspect(engine)
        return inspector.get_table_names()
    
    @classmethod
    def table_exists(cls, table_name: str) -> bool:
        """检查表是否存在
        
        Args:
            table_name (str): 表名
            
        Returns:
            bool: 表是否存在
        """
        engine = cls.get_engine()
        inspector = inspect(engine)
        return table_name in inspector.get_table_names()
    
    @classmethod
    def reset(cls):
        """重置数据库连接
        
        用于切换环境或重新初始化。
        """
        if cls._engine:
            cls._engine.dispose()
        cls._engine = None
        cls._session_factory = None
        cls._initialized = False


def get_engine():
    """获取 SQLAlchemy 引擎（便捷函数）
    
    Returns:
        Engine: SQLAlchemy 引擎
    """
    return DatabaseFactory.get_engine()


def get_session():
    """获取 Session（便捷函数）
    
    Returns:
        Session: SQLAlchemy Session
    """
    return DatabaseFactory.get_session()


def get_connection():
    """获取原生连接（便捷函数）
    
    Returns:
        Connection: 数据库连接
    """
    return DatabaseFactory.get_connection()


def execute(sql: str, params: Optional[Dict] = None) -> List:
    """执行 SQL（便捷函数）
    
    Args:
        sql (str): SQL 语句
        params (Dict, optional): 查询参数
        
    Returns:
        List: 查询结果
    """
    return DatabaseFactory.execute(sql, params)


def get_environment() -> DBEnvironment:
    """获取当前环境（便捷函数）
    
    Returns:
        DBEnvironment: 当前环境
    """
    return DatabaseFactory.get_environment()
