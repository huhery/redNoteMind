"""
爆款分析与原创文案生成工具

基于 LLM 分析爬虫采集的爆款素材共性规律，100% 原创重构生成新笔记文案。
输出标准小红书格式：吸睛标题 + emoji 分段正文 + 5个精准标签。

@author honghui
@date 2025/07/15
"""

import json
from typing import Optional

from adapters.llm_adapter import get_llm_adapter
from config.settings import get_settings
from tools.prompts import COPYWRITER_SYSTEM_PROMPT, COPYWRITER_USER_TEMPLATE
from utils.exceptions import LLMError
from utils.logger import get_logger

logger = get_logger(__name__)


class CopyWriter:
    """
    爆款分析与原创文案生成器

    先分析多条爆款共性规律，再全新原创一篇小红书笔记。
    内置格式校验和自动重写机制。

    @author honghui
    @version 1.0
    @date 2025/07/15
    """

    def __init__(self):
        self._settings = get_settings()
        self._llm = get_llm_adapter()

    def generate_copy(
        self,
        hot_material: str,
        keyword: str,
        word_count_range: Optional[tuple] = None,
    ) -> dict:
        """
        生成原创文案主入口

        @param hot_material 爆虫采集的爆款素材 JSON 字符串
        @param keyword 赛道关键词
        @param word_count_range 字数范围元组 (min, max)，默认从配置读取
        @return dict 包含 new_title, content, tags 的结构化结果
        @author honghui
        @date 2025/07/15 10:00
        """
        if not hot_material or not keyword:
            raise LLMError("爆款素材和关键词不能为空")

        # 字数范围
        if word_count_range:
            word_min, word_max = word_count_range
        else:
            word_min = self._settings.copy_word_min
            word_max = self._settings.copy_word_max

        logger.info(f"开始生成文案: keyword={keyword}, 字数范围={word_min}-{word_max}")

        # 最多尝试3次（首次 + 2次重写）
        max_attempts = 3
        last_error = ""

        for attempt in range(max_attempts):
            try:
                # 构建 Prompt
                user_prompt = COPYWRITER_USER_TEMPLATE.format(
                    keyword=keyword,
                    hot_material=hot_material,
                    word_min=word_min,
                    word_max=word_max,
                )

                # 调用 LLM
                response = self._llm.chat(COPYWRITER_SYSTEM_PROMPT, user_prompt)
                logger.debug(f"LLM 响应长度: {len(response)} 字符")

                # 解析 JSON
                result = self._parse_response(response)

                # 质量校验
                validation_error = self._validate_result(result, word_min, word_max)
                if validation_error:
                    logger.warning(
                        f"第{attempt + 1}次生成质量不达标: {validation_error}，重新生成"
                    )
                    last_error = validation_error
                    continue

                logger.info(
                    f"文案生成成功: 标题={result['new_title'][:20]}..., "
                    f"正文{len(result['content'])}字, 标签{len(result['tags'])}个"
                )
                return result

            except (json.JSONDecodeError, ValueError) as e:
                last_error = f"响应格式错误: {e}"
                logger.warning(f"第{attempt + 1}次生成格式异常: {e}，重新生成")
                continue
            except LLMError as e:
                # LLM 调用失败（已内部重试过），直接抛出
                raise

        # 所有尝试用完
        raise LLMError(
            f"文案生成失败: 经过{max_attempts}次尝试仍不合格",
            detail=last_error,
        )

    def _parse_response(self, response: str) -> dict:
        """
        解析 LLM 响应为结构化 JSON

        处理可能存在的 markdown 代码块包裹、多余文本等情况。

        @param response LLM 原始响应文本
        @return dict 解析后的字典
        @author honghui
        @date 2025/07/15 10:00
        """
        text = response.strip()

        # 去除可能的 markdown 代码块标记
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        # 尝试找到 JSON 对象
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("响应中未找到 JSON 对象")

        json_str = text[start:end]
        result = json.loads(json_str)

        # 校验必要字段
        required_keys = ["new_title", "content", "tags"]
        for key in required_keys:
            if key not in result:
                raise ValueError(f"响应缺少必要字段: {key}")

        # 确保 tags 是列表
        if isinstance(result["tags"], str):
            result["tags"] = [t.strip() for t in result["tags"].split(",") if t.strip()]

        return result

    def _validate_result(self, result: dict, word_min: int, word_max: int) -> str:
        """
        校验生成结果质量

        检查标题字数、正文篇幅、标签数量是否符合规范。

        @param result 生成结果字典
        @param word_min 最少字数
        @param word_max 最多字数
        @return str 空字符串表示通过，否则返回具体不合格原因
        @author honghui
        @date 2025/07/15 10:00
        """
        title = result.get("new_title", "")
        content = result.get("content", "")
        tags = result.get("tags", [])

        # 标题校验：12-20字
        title_len = len(title)
        if title_len < 10:
            return f"标题过短（{title_len}字，需≥10字）"
        if title_len > 30:
            return f"标题过长（{title_len}字，需≤30字）"

        # 正文校验：字数范围（允许±20%浮动）
        content_len = len(content)
        min_threshold = int(word_min * 0.8)
        max_threshold = int(word_max * 1.2)
        if content_len < min_threshold:
            return f"正文过短（{content_len}字，需≥{min_threshold}字）"
        if content_len > max_threshold:
            return f"正文过长（{content_len}字，需≤{max_threshold}字）"

        # 内容不能为空
        if not content.strip():
            return "正文内容为空"

        # 标签校验：至少3个
        if len(tags) < 3:
            return f"标签数量不足（{len(tags)}个，需≥3个）"

        return ""
