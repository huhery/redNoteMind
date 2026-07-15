"""
LLM 统一适配器

提供统一的大模型调用接口，支持豆包（Doubao）和通义千问（Qwen）切换。
通过工厂函数根据配置自动选择对应的适配器实现。

@author honghui
@date 2025/07/15
"""

import json
from abc import ABC, abstractmethod

import requests

from config.settings import get_settings
from utils.exceptions import LLMError, retry
from utils.logger import get_logger

logger = get_logger(__name__)


class BaseLLMAdapter(ABC):
    """
    LLM 统一调用接口基类

    所有 LLM 适配器必须实现 chat 方法，接收系统提示和用户提示，返回模型回复文本。

    @author honghui
    @version 1.0
    @date 2025/07/15
    """

    @abstractmethod
    def chat(self, system_prompt: str, user_prompt: str) -> str:
        """
        发送对话请求

        @param system_prompt 系统提示词，定义模型角色和行为
        @param user_prompt 用户输入内容
        @return str 模型回复文本
        @author honghui
        @date 2025/07/15 10:00
        """
        pass


class DoubaoAdapter(BaseLLMAdapter):
    """
    豆包（字节跳动 Doubao）模型适配器

    基于 OpenAI 兼容接口调用豆包大模型。
    需要配置 DOUBAO_API_KEY 和 DOUBAO_MODEL_ID。

    @author honghui
    @version 1.0
    @date 2025/07/15
    """

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.doubao_api_key
        self._model_id = settings.doubao_model_id
        # 豆包使用火山引擎 API，兼容 OpenAI 格式
        self._base_url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"

        if not self._api_key:
            logger.warning("DOUBAO_API_KEY 未配置，豆包模型调用将失败")

    @retry(max_retries=2, delay=1.0, exceptions=(LLMError,), on_retry_msg="豆包LLM调用")
    def chat(self, system_prompt: str, user_prompt: str) -> str:
        """
        调用豆包模型进行对话

        @param system_prompt 系统提示词
        @param user_prompt 用户输入
        @return str 模型回复文本
        @author honghui
        @date 2025/07/15 10:00
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        payload = {
            "model": self._model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
        }

        try:
            response = requests.post(
                self._base_url,
                headers=headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            logger.debug(f"豆包模型响应长度: {len(content)} 字符")
            return content
        except requests.Timeout:
            raise LLMError("豆包模型调用超时", detail="timeout=30s")
        except requests.RequestException as e:
            raise LLMError(f"豆包模型请求失败: {e}", detail=str(e))
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise LLMError(f"豆包模型响应解析失败: {e}", detail=str(e))


class QwenAdapter(BaseLLMAdapter):
    """
    通义千问（阿里 Qwen）模型适配器

    基于阿里云 DashScope API 调用通义千问大模型。
    需要配置 QWEN_API_KEY。

    @author honghui
    @version 1.0
    @date 2025/07/15
    """

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.qwen_api_key
        self._base_url = (
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        )

        if not self._api_key:
            logger.warning("QWEN_API_KEY 未配置，通义千问模型调用将失败")

    @retry(max_retries=2, delay=1.0, exceptions=(LLMError,), on_retry_msg="通义千问LLM调用")
    def chat(self, system_prompt: str, user_prompt: str) -> str:
        """
        调用通义千问模型进行对话

        @param system_prompt 系统提示词
        @param user_prompt 用户输入
        @return str 模型回复文本
        @author honghui
        @date 2025/07/15 10:00
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        payload = {
            "model": "qwen-plus",
            "input": {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            },
            "parameters": {
                "temperature": 0.7,
                "result_format": "message",
            },
        }

        try:
            response = requests.post(
                self._base_url,
                headers=headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            content = data["output"]["choices"][0]["message"]["content"]
            logger.debug(f"通义千问响应长度: {len(content)} 字符")
            return content
        except requests.Timeout:
            raise LLMError("通义千问调用超时", detail="timeout=30s")
        except requests.RequestException as e:
            raise LLMError(f"通义千问请求失败: {e}", detail=str(e))
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise LLMError(f"通义千问响应解析失败: {e}", detail=str(e))


def get_llm_adapter(provider: str = "") -> BaseLLMAdapter:
    """
    LLM 适配器工厂函数

    根据 provider 参数（或配置文件）选择对应的 LLM 适配器。

    @param provider 模型提供商标识（doubao/qwen），为空则从配置读取
    @return BaseLLMAdapter 适配器实例
    @author honghui
    @date 2025/07/15 10:00
    """
    if not provider:
        provider = get_settings().llm_provider

    adapter_map = {
        "doubao": DoubaoAdapter,
        "qwen": QwenAdapter,
    }

    adapter_class = adapter_map.get(provider.lower())
    if adapter_class is None:
        raise LLMError(
            f"不支持的 LLM 提供商: {provider}",
            detail=f"可选值: {list(adapter_map.keys())}",
        )

    logger.info(f"LLM 适配器已加载: {provider}")
    return adapter_class()
