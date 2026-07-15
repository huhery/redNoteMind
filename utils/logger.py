"""
全局日志系统

支持控制台和文件双输出，日志级别可通过环境变量 LOG_LEVEL 配置。
每个模块通过 get_logger(name) 获取独立的 logger 实例。

@author honghui
@date 2025/07/15
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional


# 日志格式
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 模块级缓存，避免重复创建 handler
_initialized = False
_file_handler: Optional[logging.FileHandler] = None


def _get_log_level() -> int:
    """从环境变量获取日志级别，默认 INFO"""
    level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    return level_map.get(level_str, logging.INFO)


def _ensure_initialized():
    """确保根 logger 已配置（只执行一次）"""
    global _initialized
    if _initialized:
        return

    root_logger = logging.getLogger()
    root_logger.setLevel(_get_log_level())

    # 控制台输出
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(_get_log_level())
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    root_logger.addHandler(console_handler)

    _initialized = True


def get_logger(name: str) -> logging.Logger:
    """
    获取指定模块的 logger 实例

    @param name 模块名称，通常传 __name__
    @return logging.Logger 实例
    @author honghui
    @date 2025/07/15 10:00
    """
    _ensure_initialized()
    logger = logging.getLogger(name)
    logger.setLevel(_get_log_level())
    return logger


def add_file_handler(log_file_path: str):
    """
    为根 logger 添加文件输出 handler

    用于任务执行时将日志同时写入任务文件夹的 log.txt。
    如果之前有文件 handler，会先移除再添加新的。

    @param log_file_path 日志文件路径
    @author honghui
    @date 2025/07/15 10:00
    """
    global _file_handler
    _ensure_initialized()

    root_logger = logging.getLogger()

    # 移除旧的文件 handler
    if _file_handler is not None:
        root_logger.removeHandler(_file_handler)
        _file_handler.close()

    # 确保日志目录存在
    Path(log_file_path).parent.mkdir(parents=True, exist_ok=True)

    # 添加新的文件 handler
    _file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    _file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别
    _file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    root_logger.addHandler(_file_handler)


def remove_file_handler():
    """
    移除文件输出 handler

    任务完成后调用，停止写入文件日志。

    @author honghui
    @date 2025/07/15 10:00
    """
    global _file_handler
    if _file_handler is not None:
        root_logger = logging.getLogger()
        root_logger.removeHandler(_file_handler)
        _file_handler.close()
        _file_handler = None
