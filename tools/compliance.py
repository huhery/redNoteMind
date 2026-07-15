"""
双层合规检测工具

第一层：本地极限词库 + 在线接口（句易网）双保险匹配
第二层：LLM 语义风险审核
任一层不通过则判定违规。

@author honghui
@date 2025/07/15
"""

import json
from pathlib import Path
from typing import List, Set

import requests

from adapters.llm_adapter import get_llm_adapter
from config.settings import get_settings
from tools.prompts import COMPLIANCE_SYSTEM_PROMPT, COMPLIANCE_USER_TEMPLATE
from utils.exceptions import ComplianceError, LLMError
from utils.logger import get_logger

logger = get_logger(__name__)


class ComplianceChecker:
    """
    双层合规检测器

    第一层：本地极限词库精准/模糊匹配 + 在线接口增强
    第二层：LLM 语义风险审核
    任一层不通过则拦截。

    @author honghui
    @version 1.0
    @date 2025/07/15
    """

    def __init__(self):
        self._settings = get_settings()
        self._forbidden_words: Set[str] = set()
        self._load_forbidden_words()

    def check_compliance(self, title: str, content: str) -> dict:
        """
        执行双层合规检测

        @param title 笔记标题
        @param content 笔记正文
        @return dict {"check_status": bool, "check_msg": str}
        @author honghui
        @date 2025/07/15 10:00
        """
        if not title and not content:
            return {"check_status": False, "check_msg": "标题和正文均为空，无法检测"}

        full_text = f"{title} {content}"
        logger.info("开始合规检测...")

        # === 第一层：词库匹配 ===
        layer1_result = self._check_layer1(full_text)
        if not layer1_result["passed"]:
            logger.warning(f"第一层检测不通过: {layer1_result['msg']}")
            return {
                "check_status": False,
                "check_msg": f"[极限词检测] {layer1_result['msg']}",
            }

        logger.debug("第一层检测通过")

        # === 第二层：LLM 语义审核 ===
        layer2_result = self._check_layer2(title, content)
        if not layer2_result["passed"]:
            logger.warning(f"第二层检测不通过: {layer2_result['msg']}")
            return {
                "check_status": False,
                "check_msg": f"[语义审核] {layer2_result['msg']}",
            }

        logger.info("合规检测通过 ✓")
        return {"check_status": True, "check_msg": "合规检测通过"}

    # ============================================================
    # 第一层：极限词检测
    # ============================================================

    def _check_layer1(self, text: str) -> dict:
        """
        第一层检测：本地词库 + 在线接口

        @param text 待检测文本（标题+正文）
        @return dict {"passed": bool, "msg": str, "words": list}
        @author honghui
        @date 2025/07/15 10:00
        """
        # 本地词库检测
        found_words = self._match_local_words(text)

        # 在线接口增强检测（可选）
        online_words = self._check_online_api(text)
        if online_words:
            found_words.extend(online_words)

        # 去重
        found_words = list(set(found_words))

        if found_words:
            return {
                "passed": False,
                "msg": f"检测到违禁词: {', '.join(found_words[:10])}",
                "words": found_words,
            }

        return {"passed": True, "msg": "词库检测通过", "words": []}

    def _load_forbidden_words(self):
        """
        加载本地极限词库到内存

        @author honghui
        @date 2025/07/15 10:00
        """
        words_file = Path("assets/forbidden_words.txt")
        if not words_file.exists():
            logger.warning(f"极限词库文件不存在: {words_file}，本地词库检测将跳过")
            return

        try:
            with open(words_file, "r", encoding="utf-8") as f:
                for line in f:
                    word = line.strip()
                    if word:
                        self._forbidden_words.add(word)
            logger.debug(f"已加载 {len(self._forbidden_words)} 个极限词")
        except Exception as e:
            logger.error(f"加载极限词库失败: {e}")

    def _match_local_words(self, text: str) -> List[str]:
        """
        本地词库匹配（包含关系匹配）

        @param text 待检测文本
        @return List[str] 命中的违禁词列表
        @author honghui
        @date 2025/07/15 10:00
        """
        if not self._forbidden_words:
            return []

        found = []
        text_lower = text.lower()

        for word in self._forbidden_words:
            if word.lower() in text_lower:
                found.append(word)

        return found

    def _check_online_api(self, text: str) -> List[str]:
        """
        在线接口检测（句易网 API）

        接口不可用时静默降级，返回空列表。

        @param text 待检测文本
        @return List[str] 在线接口命中的违禁词（如有）
        @author honghui
        @date 2025/07/15 10:00
        """
        try:
            # 句易网免费极限词检测接口
            url = "https://www.ju1.cn/api/checkword"
            payload = {"content": text[:2000]}  # 限制长度避免超时
            response = requests.post(url, data=payload, timeout=5)

            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200 and data.get("data"):
                    words = [item.get("word", "") for item in data["data"] if item.get("word")]
                    if words:
                        logger.debug(f"在线接口检测到 {len(words)} 个违禁词")
                    return words
            return []

        except requests.Timeout:
            logger.warning("在线极限词接口超时，降级为纯本地词库检测")
            return []
        except Exception as e:
            logger.warning(f"在线极限词接口异常: {e}，降级为纯本地词库检测")
            return []

    # ============================================================
    # 第二层：LLM 语义审核
    # ============================================================

    def _check_layer2(self, title: str, content: str) -> dict:
        """
        第二层检测：LLM 语义风险审核

        @param title 笔记标题
        @param content 笔记正文
        @return dict {"passed": bool, "msg": str}
        @author honghui
        @date 2025/07/15 10:00
        """
        try:
            llm = get_llm_adapter()

            user_prompt = COMPLIANCE_USER_TEMPLATE.format(
                title=title,
                content=content,
            )

            response = llm.chat(COMPLIANCE_SYSTEM_PROMPT, user_prompt)
            result = self._parse_compliance_response(response)

            if result.get("passed", False):
                return {"passed": True, "msg": "语义审核通过"}
            else:
                reason = result.get("reason", "未知风险")
                risk_type = result.get("risk_type", "")
                risk_words = result.get("risk_words", [])
                msg_parts = [reason]
                if risk_type:
                    msg_parts.append(f"风险类型: {risk_type}")
                if risk_words:
                    msg_parts.append(f"风险词: {', '.join(risk_words)}")
                return {"passed": False, "msg": "; ".join(msg_parts)}

        except LLMError as e:
            # LLM 调用失败（已经重试过），标记为待人工复核
            logger.error(f"LLM 语义审核失败: {e}，标记为待人工复核")
            return {
                "passed": False,
                "msg": f"LLM审核异常，保守判定为风险（{e.message}）",
            }
        except Exception as e:
            # 异常情况默认判定为风险
            logger.error(f"语义审核异常: {e}，默认判定为风险")
            return {"passed": False, "msg": f"审核异常，保守判定为风险: {e}"}

    def _parse_compliance_response(self, response: str) -> dict:
        """
        解析 LLM 合规审核响应

        @param response LLM 原始响应
        @return dict 审核结果
        @author honghui
        @date 2025/07/15 10:00
        """
        text = response.strip()

        # 去除 markdown 代码块
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        # 提取 JSON
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            # 无法解析时默认判定为风险
            logger.warning("LLM 审核响应无法解析为 JSON，默认判定风险")
            return {"passed": False, "reason": "审核响应解析失败"}

        try:
            result = json.loads(text[start:end])
            return result
        except json.JSONDecodeError:
            logger.warning("LLM 审核响应 JSON 解析失败，默认判定风险")
            return {"passed": False, "reason": "审核响应 JSON 格式错误"}
