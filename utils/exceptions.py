"""
统一异常定义与重试装饰器

定义智能体各模块的异常类层级，以及通用的重试装饰器。

@author honghui
@date 2025/07/15
"""

import functools
import logging
import time
from typing import Tuple, Type

logger = logging.getLogger(__name__)


# ============================================================
# 异常类层级
# ============================================================


class AgentError(Exception):
    """智能体基础异常，所有自定义异常的父类"""

    def __init__(self, message: str = "", detail: str = ""):
        self.message = message
        self.detail = detail
        super().__init__(self.message)


class CrawlerError(AgentError):
    """爬虫模块异常"""
    pass


class LLMError(AgentError):
    """LLM 调用异常（文案生成、合规审核等）"""
    pass


class ComplianceError(AgentError):
    """合规检测异常"""
    pass


class CoverError(AgentError):
    """封面生成异常"""
    pass


class ArchiveError(AgentError):
    """归档模块异常"""
    pass


# ============================================================
# 重试装饰器
# ============================================================


def retry(
    max_retries: int = 2,
    delay: float = 1.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry_msg: str = "",
):
    """
    统一重试装饰器

    当被装饰函数抛出指定异常时，自动重试。
    每次重试之间有固定延时，并记录重试日志。

    @param max_retries 最大重试次数（不含首次执行）
    @param delay 重试间隔秒数
    @param exceptions 触发重试的异常类型元组
    @param on_retry_msg 重试时的日志前缀信息
    @return 装饰器
    @author honghui
    @date 2025/07/15 10:00
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            func_name = func.__name__
            msg_prefix = on_retry_msg or func_name

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"[{msg_prefix}] 第{attempt + 1}次执行失败，"
                            f"将在 {delay}s 后重试（共{max_retries}次）。"
                            f"异常: {type(e).__name__}: {e}"
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"[{msg_prefix}] 已重试{max_retries}次仍然失败。"
                            f"异常: {type(e).__name__}: {e}"
                        )

            # 所有重试用完，抛出最后一个异常
            raise last_exception

        return wrapper

    return decorator
