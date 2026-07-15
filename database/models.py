"""
数据库模型定义

定义与 SQLite 表对应的 Python 数据类，用于结构化数据传递。

@author honghui
@date 2025/07/15
"""

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


def _generate_id() -> str:
    """生成 UUID 主键"""
    return str(uuid.uuid4().hex)


def _now_iso() -> str:
    """获取当前时间 ISO 格式字符串"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class TaskRecord:
    """
    任务记录模型

    对应数据表 task_record，记录每次智能体执行的完整结果。

    @author honghui
    @date 2025/07/15
    """

    id: str = field(default_factory=_generate_id)
    keyword: str = ""
    create_time: str = field(default_factory=_now_iso)
    title: str = ""
    content: str = ""
    tags: str = ""  # JSON 数组字符串
    check_result: str = ""
    cover_path: str = ""
    status: str = "pending"  # pending / success / failed
    retry_count: int = 0
    error_msg: str = ""

    def to_dict(self) -> dict:
        """
        转换为字典，用于数据库插入

        @return dict 字段名到值的映射
        @author honghui
        @date 2025/07/15 10:00
        """
        return asdict(self)

    @classmethod
    def from_row(cls, row: tuple) -> "TaskRecord":
        """
        从数据库查询结果行构建实例

        @param row 数据库查询返回的元组（字段顺序与表定义一致）
        @return TaskRecord 实例
        @author honghui
        @date 2025/07/15 10:00
        """
        return cls(
            id=row[0],
            keyword=row[1],
            create_time=row[2],
            title=row[3],
            content=row[4],
            tags=row[5],
            check_result=row[6],
            cover_path=row[7],
            status=row[8],
            retry_count=row[9],
            error_msg=row[10],
        )


@dataclass
class HotMaterial:
    """
    爆款素材模型

    对应数据表 hot_material，存储爬虫采集的原始笔记数据。

    @author honghui
    @date 2025/07/15
    """

    id: str = field(default_factory=_generate_id)
    keyword: str = ""
    ref_title: str = ""
    ref_content: str = ""
    ref_tags: str = ""  # JSON 数组字符串
    like_num: int = 0
    crawl_url: str = ""
    crawl_time: str = field(default_factory=_now_iso)
    task_id: str = ""

    def to_dict(self) -> dict:
        """
        转换为字典，用于数据库插入

        @return dict 字段名到值的映射
        @author honghui
        @date 2025/07/15 10:00
        """
        return asdict(self)

    @classmethod
    def from_row(cls, row: tuple) -> "HotMaterial":
        """
        从数据库查询结果行构建实例

        @param row 数据库查询返回的元组
        @return HotMaterial 实例
        @author honghui
        @date 2025/07/15 10:00
        """
        return cls(
            id=row[0],
            keyword=row[1],
            ref_title=row[2],
            ref_content=row[3],
            ref_tags=row[4],
            like_num=row[5],
            crawl_url=row[6],
            crawl_time=row[7],
            task_id=row[8],
        )


@dataclass
class CrawlCounter:
    """
    采集计数器模型

    对应数据表 crawl_counter，记录每日采集次数，用于软限制。

    @author honghui
    @date 2025/07/15
    """

    id: str = field(default_factory=_generate_id)
    date: str = ""  # YYYY-MM-DD 格式
    count: int = 0

    def to_dict(self) -> dict:
        """
        转换为字典

        @return dict 字段名到值的映射
        @author honghui
        @date 2025/07/15 10:00
        """
        return asdict(self)

    @classmethod
    def from_row(cls, row: tuple) -> "CrawlCounter":
        """
        从数据库查询结果行构建实例

        @param row 数据库查询返回的元组
        @return CrawlCounter 实例
        @author honghui
        @date 2025/07/15 10:00
        """
        return cls(
            id=row[0],
            date=row[1],
            count=row[2],
        )
