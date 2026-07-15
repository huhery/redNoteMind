"""
配置管理模块

提供全局配置类，从 .env 文件和环境变量加载配置项。
"""

from config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
