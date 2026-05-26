"""ORM Models Package

SQLAlchemy ORM 模型定义，支持 PostgreSQL 和 py-pglite。
使用数据库抽象层自动选择数据库引擎。

Design Principles:
    1. 使用 SQLAlchemy ORM 实现数据库无关
    2. 表名与 MongoDB 集合名保持一致
    3. 支持 py-pglite（开发）和 PostgreSQL（生产）

Usage:
    # 创建表
    from app.models.orm_models import Base, get_engine
    from app.models.database import DatabaseFactory
    
    engine = DatabaseFactory.get_engine()
    Base.metadata.create_all(engine)
    
    # 查询数据
    from sqlalchemy.orm import Session
    from app.models.orm_models import User
    
    session = Session(bind=engine)
    users = session.query(User).all()

Models:
    CCApplicationBase: 业务表
    CCPlatBase: 云区域表
    CCSystem: 系统配置表
    CCObjClassification: 对象分类表
    User: 用户表
    UserBusiness: 用户-业务关联表
    CCUserCustom: 用户个性化配置表
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime,
    ForeignKey, PrimaryKeyConstraint, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class CCApplicationBase(Base):
    """业务表
    
    存储业务基本信息，对应 MongoDB 的 cc_ApplicationBase 集合。
    
    Attributes:
        bk_biz_id (int): 业务 ID，主键
        bk_biz_name (str): 业务名称
        bk_supplier_account (str): 开发商账号
        operator (str): 运维人员
        bk_maintainer (str): 维护人员
        time_zone (str): 时区
        create_time (str): 创建时间
        last_time (str): 更新时间
        bk_data_status (str): 数据状态（enabled/disabled）
    """
    __tablename__ = 'cc_ApplicationBase'

    bk_biz_id = Column(Integer, primary_key=True)
    bk_biz_name = Column(String(255))
    bk_supplier_account = Column(String(64))
    operator = Column(String(64))
    bk_maintainer = Column(String(64))
    time_zone = Column(String(64))
    create_time = Column(String(32))
    last_time = Column(String(32))
    bk_data_status = Column(String(32), default='enabled')


class CCPlatBase(Base):
    """云区域表
    
    存储云区域信息，对应 MongoDB 的 cc_PlatBase 集合。
    
    Attributes:
        bk_cloud_id (int): 云区域 ID，主键
        bk_cloud_name (str): 云区域名称
        bk_supplier_account (str): 开发商账号
        create_time (str): 创建时间
        last_time (str): 更新时间
    """
    __tablename__ = 'cc_PlatBase'

    bk_cloud_id = Column(Integer, primary_key=True)
    bk_cloud_name = Column(String(255))
    bk_supplier_account = Column(String(64))
    create_time = Column(String(32))
    last_time = Column(String(32))


class CCSystem(Base):
    """系统配置表
    
    存储系统级配置，对应 MongoDB 的 cc_System 集合。
    
    Attributes:
        id (int): 主键
        host_cross_biz (bool): 主机跨业务开关
    """
    __tablename__ = 'cc_System'

    id = Column(Integer, primary_key=True, autoincrement=True)
    host_cross_biz = Column(Boolean, default=False)


class CCObjClassification(Base):
    """对象分类表
    
    存储模型分类信息，对应 MongoDB 的 cc_ObjClassification 集合。
    
    Attributes:
        bk_classification_id (str): 分类 ID，主键
        bk_classification_name (str): 分类名称
    """
    __tablename__ = 'cc_ObjClassification'

    bk_classification_id = Column(String(64), primary_key=True)
    bk_classification_name = Column(String(255))


class User(Base):
    """用户表
    
    存储用户信息，对应 MongoDB 的 users 集合。
    
    Attributes:
        username (str): 用户名，主键
        password (str): 密码（明文或加密）
        display_name (str): 显示名称
        qq (str): QQ 号
        phone (str): 手机号
        email (str): 邮箱
    """
    __tablename__ = 'users'

    username = Column(String(64), primary_key=True)
    password = Column(String(255))
    display_name = Column(String(255))
    qq = Column(String(32))
    phone = Column(String(32))
    email = Column(String(128))


class UserBusiness(Base):
    """用户-业务关联表
    
    存储用户与业务的关联关系，对应 MongoDB 的 user_business 集合。
    
    Attributes:
        username (str): 用户名
        bk_biz_id (int): 业务 ID
    """
    __tablename__ = 'user_business'

    username = Column(String(64), primary_key=True)
    bk_biz_id = Column(Integer, primary_key=True)


class CCUserCustom(Base):
    """用户个性化配置表
    
    存储用户个性化配置，对应 MongoDB 的 cc_UserCustom 集合。
    
    Attributes:
        id (int): 主键
        user (str): 用户名
        data (str): 配置数据（JSON 格式）
        create_time (str): 创建时间
        last_time (str): 更新时间
    """
    __tablename__ = 'cc_UserCustom'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user = Column(String(64))
    data = Column(Text)
    create_time = Column(String(32))
    last_time = Column(String(32))


class AuthPolicy(Base):
    """权限策略表
    
    存储权限策略信息，用于 Casbin 等权限框架。
    
    Attributes:
        id (int): 主键
        sub (str): 主体（用户或角色）
        obj (str): 资源类型
        act (str): 动作
        sub_type (str): 主体类型 (user/role)
        obj_id (str): 具体资源 ID
        effect (str): 权限效果 (allow/deny)
        created_at (str): 创建时间
        updated_at (str): 更新时间
    """
    __tablename__ = 'auth_policies'

    id = Column(Integer, primary_key=True, autoincrement=True)
    sub = Column(String(64))
    obj = Column(String(64))
    act = Column(String(32))
    sub_type = Column(String(16), default='user')
    obj_id = Column(String(128))
    effect = Column(String(16), default='allow')
    created_at = Column(String(32))
    updated_at = Column(String(32))


def get_all_model_classes():
    """获取所有模型类
    
    Returns:
        list: 所有 SQLAlchemy 模型类列表
    """
    return [
        CCApplicationBase,
        CCPlatBase,
        CCSystem,
        CCObjClassification,
        User,
        UserBusiness,
        CCUserCustom,
        AuthPolicy,
    ]


def create_all_tables(engine):
    """创建所有表
    
    Args:
        engine: SQLAlchemy 引擎
    """
    Base.metadata.create_all(engine)


def drop_all_tables(engine):
    """删除所有表
    
    Args:
        engine: SQLAlchemy 引擎
    """
    Base.metadata.drop_all(engine)
