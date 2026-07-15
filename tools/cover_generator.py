"""
AI封面生成工具

调用绘图 API 生成小红书标准竖版封面底图（750×1000），
再通过 PIL 叠加笔记标题文字，生成最终成品封面。

@author honghui
@date 2025/07/15
"""

import random
import string
from io import BytesIO
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from adapters.image_adapter import get_image_adapter
from config.settings import get_settings
from utils.exceptions import CoverError
from utils.logger import get_logger

logger = get_logger(__name__)

# 封面固定尺寸
COVER_WIDTH = 750
COVER_HEIGHT = 1000

# 动态 Prompt 随机修饰词
_STYLE_MODIFIERS = [
    "minimalist aesthetic",
    "soft pastel tones",
    "clean composition",
    "elegant layout",
    "warm lighting",
    "modern design",
    "gentle gradient background",
    "subtle texture",
    "professional look",
    "cozy atmosphere",
]


class CoverGenerator:
    """
    AI 封面生成器

    生成流程：构建动态 Prompt → 调用绘图 API → PIL 叠加标题文字 → 保存成品

    @author honghui
    @version 1.0
    @date 2025/07/15
    """

    def __init__(self):
        self._settings = get_settings()
        self._image_adapter = get_image_adapter()

    def generate_cover(
        self,
        title: str,
        save_dir: str,
        style: Optional[str] = None,
    ) -> dict:
        """
        生成封面图主入口

        @param title 笔记标题（用于生成主题和叠加文字）
        @param save_dir 保存目录
        @param style 风格描述（可选，默认"简约高级自媒体风"）
        @return dict {"cover_path": str, "cover_status": bool}
        @author honghui
        @date 2025/07/15 10:00
        """
        if not title:
            raise CoverError("标题不能为空")

        style = style or "简约高级自媒体风"

        logger.info(f"开始生成封面: title={title[:20]}..., style={style}")

        try:
            # 构建动态绘图 Prompt
            prompt = self._build_prompt(title, style)
            logger.debug(f"绘图 Prompt: {prompt[:100]}...")

            # 调用绘图 API 生成底图
            image_bytes = self._image_adapter.generate(prompt, COVER_WIDTH, COVER_HEIGHT)
            logger.debug(f"底图生成成功，大小: {len(image_bytes)} bytes")

            # PIL 处理：叠加标题文字
            final_image = self._overlay_title(image_bytes, title)

            # 校验尺寸
            if final_image.size != (COVER_WIDTH, COVER_HEIGHT):
                logger.warning(
                    f"图片尺寸不合格 {final_image.size}，调整为 {COVER_WIDTH}x{COVER_HEIGHT}"
                )
                final_image = final_image.resize((COVER_WIDTH, COVER_HEIGHT), Image.LANCZOS)

            # 保存
            cover_path = self._save_cover(final_image, title, save_dir)

            logger.info(f"封面生成成功: {cover_path}")
            return {"cover_path": cover_path, "cover_status": True}

        except CoverError:
            raise
        except Exception as e:
            logger.error(f"封面生成失败: {e}")
            return {"cover_path": "", "cover_status": False}

    def _build_prompt(self, title: str, style: str) -> str:
        """
        构建动态绘图 Prompt

        每次随机加入修饰词，避免批量图片同质化。

        @param title 笔记标题
        @param style 风格描述
        @return str 英文绘图 Prompt
        @author honghui
        @date 2025/07/15 10:00
        """
        # 随机选取2个修饰词
        modifiers = random.sample(_STYLE_MODIFIERS, 2)
        modifier_text = ", ".join(modifiers)

        # 构建提示词（纯英文，绘图模型对英文效果更好）
        prompt = (
            f"A beautiful social media cover image, {modifier_text}, "
            f"style: {style}, theme related to: {title}, "
            f"vertical format 3:4 ratio, high quality, no text on image, "
            f"clean background suitable for text overlay, "
            f"8K resolution, professional photography style"
        )

        return prompt

    def _overlay_title(self, image_bytes: bytes, title: str) -> Image.Image:
        """
        在底图上叠加标题文字

        自动换行、居中对齐、半透明底色背景。

        @param image_bytes 底图二进制数据
        @param title 要叠加的标题文字
        @return Image.Image 处理后的 PIL Image 对象
        @author honghui
        @date 2025/07/15 10:00
        """
        # 打开底图
        img = Image.open(BytesIO(image_bytes)).convert("RGBA")

        # 创建文字叠加层
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # 加载中文字体
        font = self._load_font(size=48)

        # 计算文字区域
        max_width = int(COVER_WIDTH * 0.8)  # 文字区域占宽度的80%
        lines = self._wrap_text(title, font, max_width, draw)

        # 计算总文字高度
        line_height = 60
        total_text_height = len(lines) * line_height

        # 文字区域位置（垂直居中偏下）
        text_area_top = int(COVER_HEIGHT * 0.6) - total_text_height // 2
        padding = 20

        # 绘制半透明背景
        bg_top = text_area_top - padding
        bg_bottom = text_area_top + total_text_height + padding
        bg_left = (COVER_WIDTH - max_width) // 2 - padding
        bg_right = (COVER_WIDTH + max_width) // 2 + padding
        draw.rectangle(
            [bg_left, bg_top, bg_right, bg_bottom],
            fill=(0, 0, 0, 120),  # 半透明黑色
        )

        # 逐行绘制文字
        for i, line in enumerate(lines):
            # 计算居中位置
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            x = (COVER_WIDTH - text_width) // 2
            y = text_area_top + i * line_height

            # 绘制白色文字
            draw.text((x, y), line, font=font, fill=(255, 255, 255, 240))

        # 合并图层
        result = Image.alpha_composite(img, overlay)
        return result.convert("RGB")

    def _wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.Draw) -> list:
        """
        文字自动换行

        @param text 原始文本
        @param font 字体对象
        @param max_width 最大行宽（像素）
        @param draw ImageDraw 对象
        @return list 分行后的文本列表
        @author honghui
        @date 2025/07/15 10:00
        """
        lines = []
        current_line = ""

        for char in text:
            test_line = current_line + char
            bbox = draw.textbbox((0, 0), test_line, font=font)
            line_width = bbox[2] - bbox[0]

            if line_width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char

        if current_line:
            lines.append(current_line)

        return lines

    def _load_font(self, size: int = 48) -> ImageFont.FreeTypeFont:
        """
        加载中文字体

        优先使用配置的字体路径，不存在时使用系统默认字体。

        @param size 字体大小
        @return ImageFont.FreeTypeFont 字体对象
        @author honghui
        @date 2025/07/15 10:00
        """
        font_path = self._settings.font_path

        # 尝试配置的字体路径
        if Path(font_path).exists():
            try:
                return ImageFont.truetype(font_path, size)
            except Exception as e:
                logger.warning(f"加载配置字体失败: {e}")

        # 尝试常见系统字体路径（Windows）
        system_fonts = [
            "C:/Windows/Fonts/msyh.ttc",     # 微软雅黑
            "C:/Windows/Fonts/simhei.ttf",   # 黑体
            "C:/Windows/Fonts/simsun.ttc",   # 宋体
        ]
        for sys_font in system_fonts:
            if Path(sys_font).exists():
                try:
                    return ImageFont.truetype(sys_font, size)
                except Exception:
                    continue

        # 最后使用默认字体（不支持中文但不会崩溃）
        logger.warning("未找到中文字体，使用默认字体（中文可能显示异常）")
        return ImageFont.load_default()

    def _save_cover(self, image: Image.Image, title: str, save_dir: str) -> str:
        """
        保存封面图到指定目录

        命名规则：标题前12字符 + 随机6位后缀。

        @param image PIL Image 对象
        @param title 笔记标题
        @param save_dir 保存目录
        @return str 保存的文件绝对路径
        @author honghui
        @date 2025/07/15 10:00
        """
        # 确保目录存在
        Path(save_dir).mkdir(parents=True, exist_ok=True)

        # 生成文件名
        title_part = title[:12].replace(" ", "").replace("/", "").replace("\\", "")
        random_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        filename = f"{title_part}_{random_suffix}.jpg"

        # 保存
        file_path = str(Path(save_dir) / filename)
        image.save(file_path, "JPEG", quality=90)
        logger.debug(f"封面已保存: {file_path}")

        return file_path
