"""
SQLite 数据库管理器

提供数据库连接管理、自动建表、CRUD 操作封装。
程序启动时自动检测并创建表结构。

@author honghui
@date 2025/07/15
"""

import sqlite3
from datetime import date
from pathlib import Path
from typing import List, Optional

from config.settings import get_settings
from database.models import TaskRecord, HotMaterial, CrawlCounter
from utils.logger import get_logger

logger = get_logger(__name__)

# 建表 DDL 语句
_DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS task_record (
        id TEXT PRIMARY KEY,
        keyword TEXT NOT NULL DEFAULT '',
        create_time TEXT NOT NULL DEFAULT '',
        title TEXT NOT NULL DEFAULT '',
        content TEXT NOT NULL DEFAULT '',
        tags TEXT NOT NULL DEFAULT '',
        check_result TEXT NOT NULL DEFAULT '',
        cover_path TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'pending',
        retry_count INTEGER NOT NULL DEFAULT 0,
        error_msg TEXT NOT NULL DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_task_record_keyword ON task_record(keyword)",
    "CREATE INDEX IF NOT EXISTS idx_task_record_status ON task_record(status)",
    "CREATE INDEX IF NOT EXISTS idx_task_record_create_time ON task_record(create_time)",
    """
    CREATE TABLE IF NOT EXISTS hot_material (
        id TEXT PRIMARY KEY,
        keyword TEXT NOT NULL DEFAULT '',
        ref_title TEXT NOT NULL DEFAULT '',
        ref_content TEXT NOT NULL DEFAULT '',
        ref_tags TEXT NOT NULL DEFAULT '',
        like_num INTEGER NOT NULL DEFAULT 0,
        crawl_url TEXT NOT NULL DEFAULT '',
        crawl_time TEXT NOT NULL DEFAULT '',
        task_id TEXT NOT NULL DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_hot_material_keyword ON hot_material(keyword)",
    "CREATE INDEX IF NOT EXISTS idx_hot_material_task_id ON hot_material(task_id)",
    "CREATE INDEX IF NOT EXISTS idx_hot_material_like_num ON hot_material(like_num)",
    """
    CREATE TABLE IF NOT EXISTS crawl_counter (
        id TEXT PRIMARY KEY,
        date TEXT NOT NULL DEFAULT '',
        count INTEGER NOT NULL DEFAULT 0
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_crawl_counter_date ON crawl_counter(date)",
]


class DatabaseManager:
    """
    SQLite 数据库管理器

    提供连接管理和 CRUD 操作，使用上下文管理器自动关闭连接。

    @author honghui
    @version 1.0
    @date 2025/07/15
    """

    _instance: Optional["DatabaseManager"] = None

    def __new__(cls):
        """单例模式，确保全局只有一个数据库管理器实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._db_path = get_settings().db_path
        # 确保数据目录存在
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialized = True
        logger.info(f"数据库路径: {self._db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """
        获取数据库连接

        @return sqlite3.Connection 数据库连接对象
        @author honghui
        @date 2025/07/15 10:00
        """
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def init_db(self):
        """
        初始化数据库，执行建表语句

        程序启动时调用，自动检测并创建所有表结构和索引。

        @author honghui
        @date 2025/07/15 10:00
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            for ddl in _DDL_STATEMENTS:
                cursor.execute(ddl)
            conn.commit()
            logger.info("数据库初始化完成，所有表已就绪")
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise
        finally:
            conn.close()

    # ============================================================
    # task_record 操作
    # ============================================================

    def insert_task_record(self, record: TaskRecord):
        """
        插入任务记录

        @param record TaskRecord 实例
        @author honghui
        @date 2025/07/15 10:00
        """
        data = record.to_dict()
        fields = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        sql = f"INSERT INTO task_record ({fields}) VALUES ({placeholders})"

        conn = self._get_connection()
        try:
            conn.execute(sql, list(data.values()))
            conn.commit()
            logger.debug(f"任务记录已插入: {record.id}")
        finally:
            conn.close()

    def update_task_record(self, task_id: str, **kwargs):
        """
        更新任务记录指定字段

        @param task_id 任务ID
        @param kwargs 要更新的字段和值
        @author honghui
        @date 2025/07/15 10:00
        """
        if not kwargs:
            return

        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        sql = f"UPDATE task_record SET {set_clause} WHERE id = ?"
        values = list(kwargs.values()) + [task_id]

        conn = self._get_connection()
        try:
            conn.execute(sql, values)
            conn.commit()
            logger.debug(f"任务记录已更新: {task_id}, 字段: {list(kwargs.keys())}")
        finally:
            conn.close()

    def query_task_records(
        self, keyword: Optional[str] = None, status: Optional[str] = None
    ) -> List[TaskRecord]:
        """
        查询任务记录

        @param keyword 按关键词过滤（可选）
        @param status 按状态过滤（可选）
        @return List[TaskRecord] 符合条件的任务记录列表
        @author honghui
        @date 2025/07/15 10:00
        """
        sql = "SELECT * FROM task_record WHERE 1=1"
        params = []

        if keyword:
            sql += " AND keyword = ?"
            params.append(keyword)
        if status:
            sql += " AND status = ?"
            params.append(status)

        sql += " ORDER BY create_time DESC"

        conn = self._get_connection()
        try:
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            return [TaskRecord.from_row(row) for row in rows]
        finally:
            conn.close()

    # ============================================================
    # hot_material 操作
    # ============================================================

    def insert_hot_materials(self, materials: List[HotMaterial]):
        """
        批量插入爆款素材

        @param materials HotMaterial 实例列表
        @author honghui
        @date 2025/07/15 10:00
        """
        if not materials:
            return

        conn = self._get_connection()
        try:
            for material in materials:
                data = material.to_dict()
                fields = ", ".join(data.keys())
                placeholders = ", ".join(["?"] * len(data))
                sql = f"INSERT INTO hot_material ({fields}) VALUES ({placeholders})"
                conn.execute(sql, list(data.values()))
            conn.commit()
            logger.debug(f"已插入 {len(materials)} 条爆款素材")
        finally:
            conn.close()

    def query_hot_materials(self, keyword: Optional[str] = None) -> List[HotMaterial]:
        """
        查询爆款素材

        @param keyword 按关键词过滤（可选）
        @return List[HotMaterial] 素材列表，按点赞数降序
        @author honghui
        @date 2025/07/15 10:00
        """
        sql = "SELECT * FROM hot_material WHERE 1=1"
        params = []

        if keyword:
            sql += " AND keyword = ?"
            params.append(keyword)

        sql += " ORDER BY like_num DESC"

        conn = self._get_connection()
        try:
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            return [HotMaterial.from_row(row) for row in rows]
        finally:
            conn.close()

    # ============================================================
    # crawl_counter 操作
    # ============================================================

    def get_crawl_count(self, target_date: Optional[str] = None) -> int:
        """
        获取指定日期的采集次数

        @param target_date 日期字符串 YYYY-MM-DD，默认今天
        @return int 当日已采集次数
        @author honghui
        @date 2025/07/15 10:00
        """
        if target_date is None:
            target_date = date.today().isoformat()

        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT count FROM crawl_counter WHERE date = ?", (target_date,)
            )
            row = cursor.fetchone()
            return row[0] if row else 0
        finally:
            conn.close()

    def increment_crawl_count(self, target_date: Optional[str] = None):
        """
        递增指定日期的采集计数

        如果当日无记录则新建，有记录则 +1。

        @param target_date 日期字符串 YYYY-MM-DD，默认今天
        @author honghui
        @date 2025/07/15 10:00
        """
        if target_date is None:
            target_date = date.today().isoformat()

        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT id, count FROM crawl_counter WHERE date = ?", (target_date,)
            )
            row = cursor.fetchone()

            if row:
                conn.execute(
                    "UPDATE crawl_counter SET count = ? WHERE id = ?",
                    (row[1] + 1, row[0]),
                )
            else:
                from database.models import _generate_id

                conn.execute(
                    "INSERT INTO crawl_counter (id, date, count) VALUES (?, ?, ?)",
                    (_generate_id(), target_date, 1),
                )
            conn.commit()
            logger.debug(f"采集计数已更新: {target_date}")
        finally:
            conn.close()


def get_db_manager() -> DatabaseManager:
    """
    获取数据库管理器单例

    @return DatabaseManager 实例
    @author honghui
    @date 2025/07/15 10:00
    """
    return DatabaseManager()
