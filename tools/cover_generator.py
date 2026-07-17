"""
封面与内容图生成工具

采用纯 PIL 排版方式生成小红书竖版图片（768×1024）：
- 封面页：米色背景 + 黑色粗体大标题 + 灰色副标题 + 右下角点缀语
- 内容页：米色背景 + 正文自动分页（每屏一张）+ 右下角点缀语

统一走本地绘制，不依赖 AI 绘图 API，保证批量出图风格稳定一致。

@author honghui
@date 2026/07/17
"""

import random
import string
from pathlib import Path
from typing import List, Optional

from PIL import Image, ImageDraw, ImageFont

from config.settings import get_settings
from utils.exceptions import CoverError
from utils.logger import get_logger

logger = get_logger(__name__)

# 图片固定尺寸（小红书标准竖版 3:4）
COVER_WIDTH = 768
COVER_HEIGHT = 1024

# === 视觉风格配色（取自参考样图的米色极简风）===
BG_COLOR = (250, 246, 233)        # 背景：米色 #FAF6E9
TITLE_COLOR = (26, 26, 26)        # 主标题：近黑 #1A1A1A
BODY_COLOR = (51, 51, 51)         # 正文：深灰 #333333
SUBTITLE_COLOR = (168, 159, 140)  # 副标题/角标：暖灰 #A89F8C

# 左右安全边距（像素）
SIDE_MARGIN = 72


class CoverGenerator:
    """
    封面与内容图生成器

    基于 PIL 本地绘制，输出统一米色排版风格的封面页和正文内容页。

    @author honghui
    @version 2.0
    @date 2026/07/17
    """

    def __init__(self):
        self._settings = get_settings()

    def generate_all(
        self,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
        save_dir: str = "./output",
        subtitle: Optional[str] = None,
        corner_text: Optional[str] = None,
    ) -> dict:
        """
        生成整套图片（封面 + 内容页）主入口

        @param title 笔记标题（用于封面主标题及文件命名）
        @param content 笔记正文（用于分页生成内容图）
        @param tags 标签列表（副标题缺省时取前若干个标签拼接）
        @param save_dir 保存目录
        @param subtitle 封面副标题（可选，缺省由标签生成）
        @param corner_text 右下角点缀语（可选）
        @return dict {"cover_path": str, "content_image_paths": list, "cover_status": bool}
        @author honghui
        @date 2026/07/17 10:00
        """
        if not title:
            raise CoverError("标题不能为空")

        tags = tags or []
        # 副标题缺省：取前 3 个标签用全角分隔符拼接（对齐样图风格）
        if subtitle is None:
            subtitle = "｜".join(tags[:3]) if tags else ""
        # 点缀语缺省：读取配置
        if corner_text is None:
            corner_text = self._settings.cover_corner_text

        logger.info(f"开始生成图片: title={title[:20]}..., 正文{len(content or '')}字")

        try:
            Path(save_dir).mkdir(parents=True, exist_ok=True)
            # 同一任务的所有图片共用一个文件名前缀，便于归档识别
            base_name = self._build_base_name(title)

            # 封面页
            cover_img = self._render_cover(title, subtitle, corner_text)
            cover_path = self._save_image(cover_img, save_dir, f"{base_name}_cover")

            # 内容页（正文为空时不生成）
            content_paths: List[str] = []
            if content and content.strip():
                pages = self._paginate_content(content)
                total = len(pages)
                for idx, page_lines in enumerate(pages, start=1):
                    page_img = self._render_content_page(
                        page_lines, idx, total, corner_text
                    )
                    page_path = self._save_image(
                        page_img, save_dir, f"{base_name}_content_{idx}"
                    )
                    content_paths.append(page_path)

            logger.info(
                f"图片生成成功: 封面1张 + 内容{len(content_paths)}张 -> {cover_path}"
            )
            return {
                "cover_path": cover_path,
                "content_image_paths": content_paths,
                "cover_status": True,
            }

        except CoverError:
            raise
        except Exception as e:
            logger.error(f"图片生成失败: {e}")
            return {"cover_path": "", "content_image_paths": [], "cover_status": False}

    def generate_cover(
        self,
        title: str,
        save_dir: str,
        style: Optional[str] = None,
    ) -> dict:
        """
        仅生成封面图（兼容旧入口）

        @param title 笔记标题
        @param save_dir 保存目录
        @param style 兼容参数，当前实现未使用
        @return dict {"cover_path": str, "cover_status": bool}
        @author honghui
        @date 2026/07/17 10:00
        """
        result = self.generate_all(title, content="", save_dir=save_dir)
        return {
            "cover_path": result["cover_path"],
            "cover_status": result["cover_status"],
        }

    def _render_cover(
        self, title: str, subtitle: str, corner_text: Optional[str]
    ) -> Image.Image:
        """
        绘制封面页

        布局：主标题左对齐大号粗体 → 下方灰色副标题 → 右下角点缀语。

        @param title 主标题文字
        @param subtitle 副标题文字
        @param corner_text 右下角点缀语
        @return Image.Image 封面图对象
        @author honghui
        @date 2026/07/17 10:00
        """
        img = Image.new("RGB", (COVER_WIDTH, COVER_HEIGHT), BG_COLOR)
        draw = ImageDraw.Draw(img)

        title_font = self._load_font(size=68, bold=True)
        subtitle_font = self._load_font(size=30, bold=False)

        max_width = COVER_WIDTH - SIDE_MARGIN * 2
        title_lines = self._wrap_text(title, title_font, max_width, draw)

        # 标题整体在上半部分靠上排布
        line_height = int(68 * 1.45)
        y = int(COVER_HEIGHT * 0.18)
        for line in title_lines:
            draw.text((SIDE_MARGIN, y), line, font=title_font, fill=TITLE_COLOR)
            y += line_height

        # 副标题：标题下方留一段间距
        if subtitle:
            y += int(line_height * 0.4)
            draw.text((SIDE_MARGIN, y), subtitle, font=subtitle_font, fill=SUBTITLE_COLOR)

        # 右下角点缀语
        self._draw_corner_text(draw, corner_text)

        return img

    def _render_content_page(
        self,
        lines: List[str],
        page_index: int,
        page_total: int,
        corner_text: Optional[str],
    ) -> Image.Image:
        """
        绘制单张内容页

        布局：顶部页码标识 → 正文逐行左对齐 → 右下角点缀语。

        @param lines 当前页已排好的正文行列表
        @param page_index 当前页序号（从 1 开始）
        @param page_total 总页数
        @param corner_text 右下角点缀语
        @return Image.Image 内容页图对象
        @author honghui
        @date 2026/07/17 10:00
        """
        img = Image.new("RGB", (COVER_WIDTH, COVER_HEIGHT), BG_COLOR)
        draw = ImageDraw.Draw(img)

        body_font = self._load_font(size=40, bold=False)
        marker_font = self._load_font(size=26, bold=True)

        # 顶部页码标识（多页时显示）
        top = int(COVER_HEIGHT * 0.10)
        if page_total > 1:
            marker = f"{page_index} / {page_total}"
            draw.text((SIDE_MARGIN, top), marker, font=marker_font, fill=SUBTITLE_COLOR)
            top += int(40 * 1.6)

        # 正文逐行绘制
        line_height = int(40 * 1.7)
        y = top
        for line in lines:
            draw.text((SIDE_MARGIN, y), line, font=body_font, fill=BODY_COLOR)
            y += line_height

        # 右下角点缀语
        self._draw_corner_text(draw, corner_text)

        return img

    def _draw_corner_text(self, draw: ImageDraw.ImageDraw, corner_text: Optional[str]):
        """
        绘制右下角点缀语

        @param draw ImageDraw 对象
        @param corner_text 点缀语文字，为空则不绘制
        @author honghui
        @date 2026/07/17 10:00
        """
        if not corner_text:
            return
        corner_font = self._load_font(size=28, bold=False)
        bbox = draw.textbbox((0, 0), corner_text, font=corner_font)
        text_width = bbox[2] - bbox[0]
        x = COVER_WIDTH - SIDE_MARGIN - text_width
        y = COVER_HEIGHT - int(COVER_HEIGHT * 0.08)
        draw.text((x, y), corner_text, font=corner_font, fill=SUBTITLE_COLOR)

    def _paginate_content(self, content: str) -> List[List[str]]:
        """
        正文智能分页

        先按原始换行拆段落，再逐段按页宽换行，累计行高超出内容区则翻页。

        @param content 笔记正文
        @return list 每个元素为一页的正文行列表
        @author honghui
        @date 2026/07/17 10:00
        """
        body_font = self._load_font(size=40, bold=False)
        max_width = COVER_WIDTH - SIDE_MARGIN * 2
        line_height = int(40 * 1.7)

        # 内容区可用高度（预留上下边距和角标区域）
        usable_top = int(COVER_HEIGHT * 0.12)
        usable_bottom = int(COVER_HEIGHT * 0.88)
        max_lines_per_page = max(1, (usable_bottom - usable_top) // line_height)

        # 借助临时 draw 计算文字宽度
        tmp_img = Image.new("RGB", (COVER_WIDTH, COVER_HEIGHT), BG_COLOR)
        tmp_draw = ImageDraw.Draw(tmp_img)

        # 逐段落展开为可显示的行
        all_lines: List[str] = []
        for raw_line in content.split("\n"):
            stripped = raw_line.rstrip()
            if not stripped:
                # 空行作为段落间隔保留
                all_lines.append("")
                continue
            wrapped = self._wrap_text(stripped, body_font, max_width, tmp_draw)
            all_lines.extend(wrapped)

        # 去除首尾多余空行
        while all_lines and all_lines[0] == "":
            all_lines.pop(0)
        while all_lines and all_lines[-1] == "":
            all_lines.pop()

        # 按每页最大行数切分
        pages: List[List[str]] = []
        for i in range(0, len(all_lines), max_lines_per_page):
            pages.append(all_lines[i : i + max_lines_per_page])

        return pages or [[""]]

    def _wrap_text(
        self,
        text: str,
        font: ImageFont.FreeTypeFont,
        max_width: int,
        draw: ImageDraw.ImageDraw,
    ) -> List[str]:
        """
        文字自动换行

        以"词块"为最小单位换行：连续的 ASCII 非空白字符视为一个整体（避免英文单词被拆断），
        中文字符逐字处理，空格作为分隔保留在行内。

        @param text 原始文本
        @param font 字体对象
        @param max_width 最大行宽（像素）
        @param draw ImageDraw 对象
        @return list 分行后的文本列表
        @author honghui
        @date 2026/07/17 10:00
        """
        tokens = self._tokenize(text)
        lines: List[str] = []
        current = ""

        for token in tokens:
            candidate = current + token
            bbox = draw.textbbox((0, 0), candidate, font=font)
            width = bbox[2] - bbox[0]

            if width <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current.rstrip())
                # 单个 token 本身就超宽时（超长英文），按字符强制切分
                if self._text_width(token, font, draw) > max_width:
                    for ch in token:
                        c = current + ch
                        if self._text_width(c, font, draw) <= max_width:
                            current = c
                        else:
                            lines.append(current)
                            current = ch
                else:
                    current = token.lstrip()

        if current.strip():
            lines.append(current.rstrip())

        return lines

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """
        将文本切分为换行用的词块

        中文字符及标点各自成块；连续 ASCII 可见字符合并为一块；空格单独成块。

        @param text 原始文本
        @return list 词块列表
        @author honghui
        @date 2026/07/17 10:00
        """
        tokens: List[str] = []
        buffer = ""
        for ch in text:
            if ch == " ":
                if buffer:
                    tokens.append(buffer)
                    buffer = ""
                tokens.append(" ")
            elif ord(ch) < 128 and not ch.isspace():
                # ASCII 可见字符累积成英文/数字词
                buffer += ch
            else:
                if buffer:
                    tokens.append(buffer)
                    buffer = ""
                tokens.append(ch)
        if buffer:
            tokens.append(buffer)
        return tokens

    @staticmethod
    def _text_width(
        text: str, font: ImageFont.FreeTypeFont, draw: ImageDraw.ImageDraw
    ) -> int:
        """
        计算文字像素宽度

        @param text 文本
        @param font 字体对象
        @param draw ImageDraw 对象
        @return int 宽度像素
        @author honghui
        @date 2026/07/17 10:00
        """
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]

    def _load_font(self, size: int = 48, bold: bool = False) -> ImageFont.FreeTypeFont:
        """
        加载中文字体

        优先使用配置字体，其次使用系统字体；粗体优先加载微软雅黑/黑体粗体。

        @param size 字体大小
        @param bold 是否使用粗体
        @return ImageFont.FreeTypeFont 字体对象
        @author honghui
        @date 2026/07/17 10:00
        """
        candidates: List[str] = []

        # 配置字体（非粗体时优先）
        if not bold and self._settings.font_path:
            candidates.append(self._settings.font_path)

        # 系统字体回退（Windows）
        if bold:
            candidates += [
                "C:/Windows/Fonts/msyhbd.ttc",   # 微软雅黑粗体
                "C:/Windows/Fonts/simhei.ttf",   # 黑体
                "C:/Windows/Fonts/msyh.ttc",     # 微软雅黑
            ]
        else:
            candidates += [
                "C:/Windows/Fonts/msyh.ttc",     # 微软雅黑
                "C:/Windows/Fonts/simhei.ttf",   # 黑体
                "C:/Windows/Fonts/simsun.ttc",   # 宋体
            ]

        for font_path in candidates:
            if Path(font_path).exists():
                try:
                    return ImageFont.truetype(font_path, size)
                except Exception as e:
                    logger.warning(f"加载字体失败: {font_path}, {e}")
                    continue

        logger.warning("未找到可用中文字体，使用默认字体（中文可能显示异常）")
        return ImageFont.load_default()

    @staticmethod
    def _build_base_name(title: str) -> str:
        """
        构建文件名前缀

        规则：标题前 12 字符 + 随机 6 位后缀，清理路径非法字符。

        @param title 笔记标题
        @return str 文件名前缀（不含扩展名）
        @author honghui
        @date 2026/07/17 10:00
        """
        title_part = title[:12]
        for ch in ' /\\:*?"<>|\n\r\t':
            title_part = title_part.replace(ch, "")
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return f"{title_part}_{suffix}"

    @staticmethod
    def _save_image(image: Image.Image, save_dir: str, name: str) -> str:
        """
        保存图片到指定目录

        @param image PIL Image 对象
        @param save_dir 保存目录
        @param name 文件名（不含扩展名）
        @return str 保存的文件绝对路径
        @author honghui
        @date 2026/07/17 10:00
        """
        file_path = str(Path(save_dir) / f"{name}.jpg")
        image.save(file_path, "JPEG", quality=92)
        logger.debug(f"图片已保存: {file_path}")
        return file_path
