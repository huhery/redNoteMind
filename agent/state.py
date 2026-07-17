"""
AgentState 全局状态定义

定义贯穿智能体整个任务生命周期的状态结构，
供 LangGraph 状态机各节点读取和更新。

@author honghui
@date 2025/07/15
"""

import uuid
from typing import List, TypedDict


class AgentState(TypedDict):
    """
    智能体全局状态

    贯穿爬虫→文案→合规→封面→归档全流程的状态数据。

    @author honghui
    @date 2025/07/15
    """

    keyword: str          # 用户输入的赛道关键词
    hot_material: str     # 爬虫采集的爆款素材 JSON 字符串
    title: str            # 生成的笔记标题
    content: str          # 生成的笔记正文
    tags: List[str]       # 生成的标签列表
    check_result: str     # 合规检测结果（passed / failed）
    cover_path: str       # 封面图本地路径
    content_image_paths: List[str]  # 内容图本地路径列表（正文分页图）
    finished: bool        # 任务是否完成
    retry_count: int      # 合规重试计数（最多3次）
    error_msg: str        # 错误信息
    task_id: str          # 当前任务唯一ID
    force_crawl: bool     # 是否强制重新爬取（忽略数据库缓存）


def create_initial_state(keyword: str, force_crawl: bool = False) -> AgentState:
    """
    创建初始状态

    @param keyword 赛道关键词
    @param force_crawl 是否强制重新爬取，默认 False（优先复用数据库）
    @return AgentState 初始状态字典
    @author honghui
    @date 2025/07/15 10:00
    """
    return AgentState(
        keyword=keyword,
        hot_material="",
        title="",
        content="",
        tags=[],
        check_result="",
        cover_path="",
        content_image_paths=[],
        finished=False,
        retry_count=0,
        error_msg="",
        task_id=uuid.uuid4().hex,
        force_crawl=force_crawl,
    )
