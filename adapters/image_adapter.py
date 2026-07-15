"""
绘图 API 统一适配器

提供统一的图片生成接口，支持通义万相和豆包绘图切换。
通过工厂函数根据配置自动选择对应的适配器实现。

@author honghui
@date 2025/07/15
"""

import json
import time
from abc import ABC, abstractmethod

import requests

from config.settings import get_settings
from utils.exceptions import CoverError, retry
from utils.logger import get_logger

logger = get_logger(__name__)


class BaseImageAdapter(ABC):
    """
    绘图 API 统一调用接口基类

    所有绘图适配器必须实现 generate 方法，返回图片二进制数据。

    @author honghui
    @version 1.0
    @date 2025/07/15
    """

    @abstractmethod
    def generate(self, prompt: str, width: int = 750, height: int = 1000) -> bytes:
        """
        生成图片

        @param prompt 绘图提示词
        @param width 图片宽度（像素）
        @param height 图片高度（像素）
        @return bytes 图片二进制数据
        @author honghui
        @date 2025/07/15 10:00
        """
        pass


class WanxiangAdapter(BaseImageAdapter):
    """
    通义万相（阿里）绘图适配器

    基于阿里云 DashScope API 调用通义万相文生图能力。
    需要配置 WANXIANG_API_KEY。

    @author honghui
    @version 1.0
    @date 2025/07/15
    """

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.wanxiang_api_key
        self._submit_url = (
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
        )
        self._task_url = "https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"

        if not self._api_key:
            logger.warning("WANXIANG_API_KEY 未配置，通义万相绘图将失败")

    @retry(max_retries=2, delay=2.0, exceptions=(CoverError,), on_retry_msg="通义万相绘图")
    def generate(self, prompt: str, width: int = 750, height: int = 1000) -> bytes:
        """
        调用通义万相生成图片

        采用异步任务模式：提交任务 → 轮询状态 → 下载图片。

        @param prompt 绘图提示词
        @param width 图片宽度
        @param height 图片高度
        @return bytes 图片二进制数据
        @author honghui
        @date 2025/07/15 10:00
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
            "X-DashScope-Async": "enable",
        }
        payload = {
            "model": "wanx-v1",
            "input": {"prompt": prompt},
            "parameters": {
                "size": f"{width}*{height}",
                "n": 1,
            },
        }

        # 提交生成任务
        try:
            response = requests.post(
                self._submit_url, headers=headers, json=payload, timeout=15
            )
            response.raise_for_status()
            data = response.json()
            task_id = data["output"]["task_id"]
            logger.debug(f"通义万相任务已提交: {task_id}")
        except requests.Timeout:
            raise CoverError("通义万相任务提交超时")
        except (requests.RequestException, KeyError) as e:
            raise CoverError(f"通义万相任务提交失败: {e}")

        # 轮询任务状态
        image_url = self._poll_task(task_id)

        # 下载图片
        return self._download_image(image_url)

    def _poll_task(self, task_id: str, max_wait: int = 60) -> str:
        """
        轮询异步任务状态，等待完成

        @param task_id 任务ID
        @param max_wait 最大等待秒数
        @return str 生成的图片 URL
        @author honghui
        @date 2025/07/15 10:00
        """
        headers = {"Authorization": f"Bearer {self._api_key}"}
        url = self._task_url.format(task_id=task_id)
        start_time = time.time()

        while time.time() - start_time < max_wait:
            try:
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json()
                status = data["output"]["task_status"]

                if status == "SUCCEEDED":
                    image_url = data["output"]["results"][0]["url"]
                    logger.debug(f"通义万相生成成功: {image_url[:50]}...")
                    return image_url
                elif status == "FAILED":
                    raise CoverError(f"通义万相生成失败: {data['output'].get('message', '')}")

                # 等待后继续轮询
                time.sleep(3)
            except requests.RequestException as e:
                raise CoverError(f"通义万相状态查询失败: {e}")

        raise CoverError(f"通义万相生成超时（等待超过{max_wait}秒）")

    def _download_image(self, url: str) -> bytes:
        """
        下载图片二进制数据

        @param url 图片URL
        @return bytes 图片数据
        @author honghui
        @date 2025/07/15 10:00
        """
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            return response.content
        except requests.RequestException as e:
            raise CoverError(f"图片下载失败: {e}")


class DoubaoImageAdapter(BaseImageAdapter):
    """
    豆包（字节跳动）绘图适配器

    基于火山引擎 API 调用豆包文生图能力。
    需要配置 DOUBAO_IMAGE_API_KEY。

    @author honghui
    @version 1.0
    @date 2025/07/15
    """

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.doubao_image_api_key
        self._base_url = "https://visual.volcengineapi.com/v1/text2image"

        if not self._api_key:
            logger.warning("DOUBAO_IMAGE_API_KEY 未配置，豆包绘图将失败")

    @retry(max_retries=2, delay=2.0, exceptions=(CoverError,), on_retry_msg="豆包绘图")
    def generate(self, prompt: str, width: int = 750, height: int = 1000) -> bytes:
        """
        调用豆包绘图生成图片

        @param prompt 绘图提示词
        @param width 图片宽度
        @param height 图片高度
        @return bytes 图片二进制数据
        @author honghui
        @date 2025/07/15 10:00
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        payload = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "num_images": 1,
        }

        try:
            response = requests.post(
                self._base_url, headers=headers, json=payload, timeout=30
            )
            response.raise_for_status()
            data = response.json()

            # 获取图片URL并下载
            image_url = data["data"][0]["url"]
            logger.debug(f"豆包绘图成功: {image_url[:50]}...")

            # 下载图片
            img_response = requests.get(image_url, timeout=15)
            img_response.raise_for_status()
            return img_response.content

        except requests.Timeout:
            raise CoverError("豆包绘图调用超时")
        except requests.RequestException as e:
            raise CoverError(f"豆包绘图请求失败: {e}")
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise CoverError(f"豆包绘图响应解析失败: {e}")


def get_image_adapter(provider: str = "") -> BaseImageAdapter:
    """
    绘图适配器工厂函数

    根据 provider 参数（或配置文件）选择对应的绘图适配器。

    @param provider 绘图服务提供商标识（wanxiang/doubao），为空则从配置读取
    @return BaseImageAdapter 适配器实例
    @author honghui
    @date 2025/07/15 10:00
    """
    if not provider:
        provider = get_settings().image_provider

    adapter_map = {
        "wanxiang": WanxiangAdapter,
        "doubao": DoubaoImageAdapter,
    }

    adapter_class = adapter_map.get(provider.lower())
    if adapter_class is None:
        raise CoverError(
            f"不支持的绘图提供商: {provider}",
            detail=f"可选值: {list(adapter_map.keys())}",
        )

    logger.info(f"绘图适配器已加载: {provider}")
    return adapter_class()
