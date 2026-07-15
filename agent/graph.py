"""
LangGraph 状态机构建

编排5大工具节点的执行顺序和条件分支，实现完整的智能体流程。
合规检测不通过时自动回环重试（最多3次）。

@author honghui
@date 2025/07/15
"""

from typing import Dict, Any

from langgraph.graph import StateGraph, END

from agent.nodes import (
    crawl_node,
    generate_copy_node,
    compliance_check_node,
    generate_cover_node,
    archive_node,
)
from agent.state import AgentState
from utils.logger import get_logger

logger = get_logger(__name__)

# 合规重试最大次数
MAX_COMPLIANCE_RETRIES = 3


def compliance_router(state: Dict[str, Any]) -> str:
    """
    合规检测路由函数

    根据检测结果和重试次数决定下一步流向：
    - passed: 进入封面生成
    - retry: 回到文案生成重新创作
    - failed: 终止任务

    @param state 当前 AgentState
    @return str 路由目标（"passed" / "retry" / "failed"）
    @author honghui
    @date 2025/07/15 10:00
    """
    check_result = state.get("check_result", "")
    retry_count = state.get("retry_count", 0)
    finished = state.get("finished", False)

    # 如果已经标记结束（如爬虫/文案节点失败），直接终止
    if finished:
        return "failed"

    if check_result == "passed":
        logger.info(f"[路由] 合规通过，进入封面生成")
        return "passed"
    elif retry_count < MAX_COMPLIANCE_RETRIES:
        logger.warning(
            f"[路由] 合规不通过，回到文案生成重试"
            f"（{retry_count + 1}/{MAX_COMPLIANCE_RETRIES}）"
        )
        return "retry"
    else:
        logger.error(
            f"[路由] 合规重试 {MAX_COMPLIANCE_RETRIES} 次仍失败，终止任务"
        )
        return "failed"


def should_continue_after_crawl(state: Dict[str, Any]) -> str:
    """
    爬虫后路由：判断是否继续

    爬虫失败（finished=True）时直接终止。

    @param state 当前 AgentState
    @return str "continue" 或 "end"
    @author honghui
    @date 2025/07/15 10:00
    """
    if state.get("finished", False):
        return "end"
    return "continue"


def should_continue_after_copy(state: Dict[str, Any]) -> str:
    """
    文案生成后路由：判断是否继续

    文案生成失败（finished=True）时直接终止。

    @param state 当前 AgentState
    @return str "continue" 或 "end"
    @author honghui
    @date 2025/07/15 10:00
    """
    if state.get("finished", False):
        return "end"
    return "continue"


def build_graph():
    """
    构建 LangGraph 状态机

    流程：crawl → generate_copy → compliance_check → 条件分支
      - passed → generate_cover → archive → END
      - retry → generate_copy（回环）
      - failed → END

    @return CompiledGraph 编译后的可执行图
    @author honghui
    @date 2025/07/15 10:00
    """
    # 创建状态图
    graph = StateGraph(AgentState)

    # 注册节点
    graph.add_node("crawl", crawl_node)
    graph.add_node("generate_copy", generate_copy_node)
    graph.add_node("compliance_check", compliance_check_node)
    graph.add_node("generate_cover", generate_cover_node)
    graph.add_node("archive", archive_node)

    # 设置入口
    graph.set_entry_point("crawl")

    # 爬虫后条件判断
    graph.add_conditional_edges(
        "crawl",
        should_continue_after_crawl,
        {
            "continue": "generate_copy",
            "end": END,
        },
    )

    # 文案生成后条件判断
    graph.add_conditional_edges(
        "generate_copy",
        should_continue_after_copy,
        {
            "continue": "compliance_check",
            "end": END,
        },
    )

    # 合规检测后条件分支（核心路由）
    graph.add_conditional_edges(
        "compliance_check",
        compliance_router,
        {
            "passed": "generate_cover",
            "retry": "generate_copy",
            "failed": END,
        },
    )

    # 封面生成 → 归档 → 结束
    graph.add_edge("generate_cover", "archive")
    graph.add_edge("archive", END)

    # 编译
    compiled = graph.compile()
    logger.info("LangGraph 状态机已构建")

    return compiled
