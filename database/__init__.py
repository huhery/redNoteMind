"""
数据持久层模块

提供 SQLite 数据库管理、自动建表、CRUD 操作封装。
"""

from database.models import TaskRecord, HotMaterial, CrawlCounter
from database.db_manager import DatabaseManager, get_db_manager

__all__ = [
    "TaskRecord",
    "HotMaterial",
    "CrawlCounter",
    "DatabaseManager",
    "get_db_manager",
]
