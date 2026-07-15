"""
适配器模块

提供 LLM 和绘图 API 的统一调用接口，支持多后端切换。
"""

from adapters.llm_adapter import BaseLLMAdapter, get_llm_adapter
from adapters.image_adapter import BaseImageAdapter, get_image_adapter

__all__ = [
    "BaseLLMAdapter",
    "get_llm_adapter",
    "BaseImageAdapter",
    "get_image_adapter",
]
