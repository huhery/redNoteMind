"""
本地智能归档工具

全流程素材结构化整理，输出可直接手动发布的完整笔记素材包。
自动创建独立文件夹，生成4个标准文件，并写入数据库。

@author honghui
@date 2025/07/15
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List

from config.settings import get_settings
from database.db_manager import get_db_manager
from database.models import TaskRecord
from utils.exceptions import ArchiveError
from utils.logger import get_logger

logger = get_logger(__name__)


class Archiver:
    """
    本地智能归档器

    输出可直接发布的完整笔记素材包：文案.txt + 封面.jpg + source_hot.json + log.txt

    @author honghui
    @version 1.0
    @date 2025/07/15
    """

    def __init__(self):
        self._settings = get_settings()
        self._db = get_db_manager()

    def archive_task(self, task_state: dict) -> dict:
        """
        归档任务成果主入口

        @param task_state AgentState 全流程状态数据
        @return dict {"folder_path": str, "archive_status": bool}
        @author honghui
        @date 2025/07/15 10:00
        """
        keyword = task_state.get("keyword", "未知")
        title = task_state.get("title", "未知标题")
        content = task_state.get("content", "")
        tags = task_state.get("tags", [])
        cover_path = task_state.get("cover_path", "")
        content_image_paths = task_state.get("content_image_paths", [])
        hot_material = task_state.get("hot_material", "")
        check_result = task_state.get("check_result", "")
        task_id = task_state.get("task_id", "")

        logger.info(f"开始归档: keyword={keyword}, title={title[:20]}...")

        try:
            # 创建归档文件夹
            folder_path = self._create_folder(keyword, title)
            logger.info(f"归档文件夹: {folder_path}")

            # 写入文案.txt
            self._write_copy_file(folder_path, title, content, tags)

            # 复制封面图
            self._copy_cover(folder_path, cover_path)

            # 复制内容图
            self._copy_content_images(folder_path, content_image_paths)

            # 写入 source_hot.json
            self._write_hot_json(folder_path, hot_material)

            # 写入 log.txt
            self._write_log(folder_path, task_state)

            # 写入数据库
            self._save_to_db(task_state, folder_path)

            logger.info(f"归档完成 ✓ 文件夹: {folder_path}")
            return {"folder_path": folder_path, "archive_status": True}

        except Exception as e:
            logger.error(f"归档失败: {e}")
            return {"folder_path": "", "archive_status": False}

    def _create_folder(self, keyword: str, title: str) -> str:
        """
        创建归档文件夹

        命名规则：YYYYMMDD_关键词_标题缩写

        @param keyword 关键词
        @param title 标题
        @return str 文件夹绝对路径
        @author honghui
        @date 2025/07/15 10:00
        """
        date_str = datetime.now().strftime("%Y%m%d")
        # 清理文件名中的非法字符
        keyword_clean = self._sanitize_filename(keyword)[:10]
        title_clean = self._sanitize_filename(title)[:6]
        folder_name = f"{date_str}_{keyword_clean}_{title_clean}"

        output_dir = Path(self._settings.output_dir)
        folder_path = output_dir / folder_name

        # 如果已存在则追加序号
        if folder_path.exists():
            for i in range(1, 100):
                new_path = output_dir / f"{folder_name}_{i}"
                if not new_path.exists():
                    folder_path = new_path
                    break

        try:
            folder_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            # 创建失败时切换到临时目录
            logger.warning(f"创建文件夹失败: {e}，切换到临时目录")
            import tempfile
            folder_path = Path(tempfile.mkdtemp(prefix=f"xhs_{folder_name}_"))

        return str(folder_path)

    def _write_copy_file(self, folder_path: str, title: str, content: str, tags: List[str]):
        """
        写入文案.txt

        结构：标题单独一行 → 空行 → 正文 → 空行 → 标签

        @param folder_path 文件夹路径
        @param title 标题
        @param content 正文
        @param tags 标签列表
        @author honghui
        @date 2025/07/15 10:00
        """
        file_path = Path(folder_path) / "文案.txt"

        lines = []
        lines.append(title)
        lines.append("")
        lines.append(content)
        lines.append("")

        # 标签格式：#标签1 #标签2 ...
        if tags:
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except json.JSONDecodeError:
                    tags = [tags]
            tag_line = " ".join([f"#{t}" if not t.startswith("#") else t for t in tags])
            lines.append(tag_line)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            logger.debug(f"文案.txt 已写入: {file_path}")
        except Exception as e:
            logger.error(f"文案.txt 写入失败: {e}")

    def _copy_cover(self, folder_path: str, cover_path: str):
        """
        复制封面图到归档文件夹

        @param folder_path 文件夹路径
        @param cover_path 原封面图路径
        @author honghui
        @date 2025/07/15 10:00
        """
        if not cover_path or not Path(cover_path).exists():
            logger.warning("封面图不存在，跳过复制")
            return

        dest_path = Path(folder_path) / "封面.jpg"
        try:
            shutil.copy2(cover_path, dest_path)
            logger.debug(f"封面.jpg 已复制: {dest_path}")
        except Exception as e:
            logger.error(f"封面复制失败: {e}")

    def _copy_content_images(self, folder_path: str, content_image_paths: List[str]):
        """
        复制内容图到归档文件夹

        命名规则：内容_1.jpg、内容_2.jpg ...，按顺序对应正文分页。

        @param folder_path 文件夹路径
        @param content_image_paths 内容图原路径列表
        @author honghui
        @date 2026/07/17 10:00
        """
        if not content_image_paths:
            logger.debug("无内容图，跳过复制")
            return

        for idx, src in enumerate(content_image_paths, start=1):
            if not src or not Path(src).exists():
                logger.warning(f"内容图不存在，跳过: {src}")
                continue
            dest_path = Path(folder_path) / f"内容_{idx}.jpg"
            try:
                shutil.copy2(src, dest_path)
                logger.debug(f"内容_{idx}.jpg 已复制: {dest_path}")
            except Exception as e:
                logger.error(f"内容图复制失败: {e}")

    def _write_hot_json(self, folder_path: str, hot_material: str):
        """
        写入 source_hot.json（原始爆款素材备份）

        @param folder_path 文件夹路径
        @param hot_material 爆款素材 JSON 字符串
        @author honghui
        @date 2025/07/15 10:00
        """
        file_path = Path(folder_path) / "source_hot.json"

        try:
            # 尝试格式化 JSON
            if hot_material:
                data = json.loads(hot_material) if isinstance(hot_material, str) else hot_material
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            else:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump([], f, ensure_ascii=False, indent=2)

            logger.debug(f"source_hot.json 已写入: {file_path}")
        except Exception as e:
            logger.error(f"source_hot.json 写入失败: {e}")

    def _write_log(self, folder_path: str, task_state: dict):
        """
        写入 log.txt（全流程日志摘要）

        @param folder_path 文件夹路径
        @param task_state 任务状态
        @author honghui
        @date 2025/07/15 10:00
        """
        file_path = Path(folder_path) / "log.txt"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = [
            f"{'=' * 50}",
            f"小红书AI内容智能体 - 任务日志",
            f"{'=' * 50}",
            f"",
            f"任务ID: {task_state.get('task_id', 'N/A')}",
            f"关键词: {task_state.get('keyword', 'N/A')}",
            f"执行时间: {now}",
            f"",
            f"--- 流程记录 ---",
            f"[爬虫] 采集完成",
            f"[文案] 标题: {task_state.get('title', 'N/A')[:30]}",
            f"[文案] 正文字数: {len(task_state.get('content', ''))}",
            f"[文案] 标签数: {len(task_state.get('tags', []))}",
            f"[合规] 检测结果: {task_state.get('check_result', 'N/A')}",
            f"[合规] 重试次数: {task_state.get('retry_count', 0)}",
            f"[封面] 路径: {task_state.get('cover_path', 'N/A')}",
            f"[归档] 状态: 完成",
            f"",
            f"--- 最终状态 ---",
            f"finished: {task_state.get('finished', False)}",
            f"error_msg: {task_state.get('error_msg', '')}",
            f"",
            f"{'=' * 50}",
        ]

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            logger.debug(f"log.txt 已写入: {file_path}")
        except Exception as e:
            logger.error(f"log.txt 写入失败: {e}")

    def _save_to_db(self, task_state: dict, folder_path: str):
        """
        写入任务记录到数据库

        数据库写入失败不影响本地文件归档。

        @param task_state 任务状态
        @param folder_path 归档文件夹路径
        @author honghui
        @date 2025/07/15 10:00
        """
        try:
            tags = task_state.get("tags", [])
            if isinstance(tags, list):
                tags_str = json.dumps(tags, ensure_ascii=False)
            else:
                tags_str = str(tags)

            record = TaskRecord(
                id=task_state.get("task_id", ""),
                keyword=task_state.get("keyword", ""),
                title=task_state.get("title", ""),
                content=task_state.get("content", ""),
                tags=tags_str,
                check_result=task_state.get("check_result", ""),
                cover_path=task_state.get("cover_path", ""),
                status="success",
                retry_count=task_state.get("retry_count", 0),
                error_msg=task_state.get("error_msg", ""),
            )
            self._db.insert_task_record(record)
            logger.debug("任务记录已写入数据库")
        except Exception as e:
            # 数据库写入失败不影响文件归档
            logger.error(f"数据库写入失败（不影响归档）: {e}")

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """
        清理文件名中的非法字符

        @param name 原始名称
        @return str 清理后的安全文件名
        @author honghui
        @date 2025/07/15 10:00
        """
        # 移除 Windows 文件名非法字符
        illegal_chars = '<>:"/\\|?*\n\r\t'
        for char in illegal_chars:
            name = name.replace(char, "")
        return name.strip()
