from sqlalchemy.orm import DeclarativeBase

"""
DeclarativeBase 是 SQLAlchemy 2.0 官方推荐的唯一基类,是实现 SQLAlchemy ORM 的「基类」，所有数据库模型都必须继承它,

统一管理所有表结构
统一连接、元数据管理
提供 ORM 映射能力
SQLAlchemy 2.0 标准写法
"""
class Base(DeclarativeBase):
    pass