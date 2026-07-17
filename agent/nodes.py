"""
LangGraph 节点函数

每个节点函数接收 AgentState，执行对应工具逻辑，返回状态更新字典。
节点内部做异常捕获，失败时设置 error_msg 并标记 finished。

@author honghui
@date 2025/07/15
"""

import json
from typing import Dict, Any

from config.settings import get_settings
from tools.archiver import Archiver
from tools.compliance import ComplianceChecker
from tools.copywriter import CopyWriter
from tools.cover_generator import CoverGenerator
from tools.crawler import XhsCrawler
from utils.logger import get_logger

logger = get_logger(__name__)


def crawl_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    爬虫节点：采集小红书爆款笔记

    优先复用数据库中已有的同关键词素材，避免重复爬取。
    仅在数据库无记录，或 force_crawl=True 时才实际爬取。

    @param state 当前 AgentState
    @return dict 状态更新字典
    @author honghui
    @date 2025/07/15 10:00
    """
    keyword = state["keyword"]
    task_id = state["task_id"]
    force_crawl = state.get("force_crawl", False)
    logger.info(f"[爬虫节点] 开始采集: {keyword}")

    # === 优先从数据库读取已有素材 ===
    if not force_crawl:
        try:
            from database.db_manager import get_db_manager
            db = get_db_manager()
            existing = db.query_hot_materials(keyword=keyword)
            if existing:
                results = [
                    {
                        "ref_title": m.ref_title,
                        "ref_content": m.ref_content,
                        "ref_tags": m.ref_tags,
                        "like_num": m.like_num,
                        "crawl_url": m.crawl_url,
                    }
                    for m in existing
                ]
                logger.info(
                    f"[爬虫节点] 数据库已有 {len(results)} 条「{keyword}」素材，跳过爬取直接复用"
                )
                import json
                return {"hot_material": json.dumps(results, ensure_ascii=False)}
        except Exception as e:
            logger.warning(f"[爬虫节点] 读取数据库素材失败，回退到爬取: {e}")

    # === 实际爬取 ===
    try:
        crawler = XhsCrawler()
        results = crawler.crawl_hot_notes(keyword)

        if not results:
            logger.warning("[爬虫节点] 未采集到符合条件的笔记")
            return {
                "hot_material": "[]",
                "error_msg": "未采集到符合条件的爆款笔记",
                "finished": True,
            }

        # 保存到数据库和 JSON 文件
        settings = get_settings()
        crawler.save_results(results, keyword, task_id, save_dir=settings.output_dir)

        # 序列化为 JSON 字符串存入状态
        hot_material_json = json.dumps(results, ensure_ascii=False)
        logger.info(f"[爬虫节点] 采集完成，共 {len(results)} 条笔记")

        return {"hot_material": hot_material_json}

    except Exception as e:
        logger.error(f"[爬虫节点] 异常: {e}")
        return {
            "error_msg": f"爬虫执行失败: {e}",
            "finished": True,
        }


def generate_copy_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    文案生成节点：分析爆款 + 原创文案

    调用 CopyWriter 基于爆款素材生成全新原创笔记内容。
    合规重试时 retry_count 递增。

    @param state 当前 AgentState
    @return dict 状态更新字典
    @author honghui
    @date 2025/07/15 10:00
    """
    keyword = state["keyword"]
    hot_material = state["hot_material"]
    retry_count = state.get("retry_count", 0)

    if retry_count > 0:
        logger.info(f"[文案节点] 合规重试第 {retry_count} 次，重新生成文案")
    else:
        logger.info(f"[文案节点] 开始生成文案: {keyword}")

    try:
        writer = CopyWriter()
        result = writer.generate_copy(hot_material, keyword)

        title = result.get("new_title", "")
        content = result.get("content", "")
        tags = result.get("tags", [])

        logger.info(f"[文案节点] 生成成功: {title[:20]}...")

        update = {
            "title": title,
            "content": content,
            "tags": tags,
        }

        # 如果是重试，递增计数
        if state.get("check_result") == "failed":
            update["retry_count"] = retry_count + 1

        return update

    except Exception as e:
        logger.error(f"[文案节点] 异常: {e}")
        return {
            "error_msg": f"文案生成失败: {e}",
            "finished": True,
        }


def compliance_check_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    合规检测节点：双层校验

    调用 ComplianceChecker 对标题和正文进行合规检测。
    检测结果存入 check_result 字段（passed / failed）。

    @param state 当前 AgentState
    @return dict 状态更新字典
    @author honghui
    @date 2025/07/15 10:00
    """
    title = state["title"]
    content = state["content"]
    logger.info("[合规节点] 开始合规检测")

    try:
        checker = ComplianceChecker()
        result = checker.check_compliance(title, content)

        check_status = result.get("check_status", False)
        check_msg = result.get("check_msg", "")

        if check_status:
            logger.info("[合规节点] 检测通过 ✓")
            return {"check_result": "passed"}
        else:
            logger.warning(f"[合规节点] 检测不通过: {check_msg}")
            return {"check_result": "failed"}

    except Exception as e:
        logger.error(f"[合规节点] 异常: {e}")
        # 异常时保守判定为不通过
        return {"check_result": "failed"}


def generate_cover_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    封面生成节点：封面页 + 内容页排版出图

    调用 CoverGenerator 生成米色风格封面图及正文分页内容图并保存。
    出图失败不影响整体流程（文案仍可手动使用）。

    @param state 当前 AgentState
    @return dict 状态更新字典
    @author honghui
    @date 2026/07/17 10:00
    """
    title = state["title"]
    content = state.get("content", "")
    tags = state.get("tags", [])
    logger.info(f"[封面节点] 开始生成封面及内容图: {title[:20]}...")

    try:
        settings = get_settings()
        generator = CoverGenerator()

        # 保存目录使用 output 目录
        save_dir = settings.output_dir
        result = generator.generate_all(title, content, tags, save_dir)

        cover_path = result.get("cover_path", "")
        content_image_paths = result.get("content_image_paths", [])
        cover_status = result.get("cover_status", False)

        if cover_status:
            logger.info(
                f"[封面节点] 生成成功: 封面={cover_path}，内容图{len(content_image_paths)}张"
            )
            return {
                "cover_path": cover_path,
                "content_image_paths": content_image_paths,
            }
        else:
            logger.warning("[封面节点] 生成失败，继续归档（无封面）")
            return {"cover_path": "", "content_image_paths": []}

    except Exception as e:
        logger.warning(f"[封面节点] 异常: {e}，继续归档（无封面）")
        import traceback
        logger.warning(f"[封面节点] 详细错误: {traceback.format_exc()}")
        return {"cover_path": "", "content_image_paths": []}


def archive_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    归档节点：结构化输出成品素材包

    调用 Archiver 创建文件夹、写入文案/封面/素材/日志、落库。

    @param state 当前 AgentState
    @return dict 状态更新字典
    @author honghui
    @date 2025/07/15 10:00
    """
    logger.info("[归档节点] 开始归档")

    try:
        archiver = Archiver()
        result = archiver.archive_task(state)

        folder_path = result.get("folder_path", "")
        archive_status = result.get("archive_status", False)

        if archive_status:
            logger.info(f"[归档节点] 归档成功: {folder_path}")
            return {"finished": True}
        else:
            logger.error("[归档节点] 归档失败")
            return {
                "finished": True,
                "error_msg": "归档失败",
            }

    except Exception as e:
        logger.error(f"[归档节点] 异常: {e}")
        return {
            "finished": True,
            "error_msg": f"归档异常: {e}",
        }
