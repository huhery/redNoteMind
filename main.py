"""
小红书AI内容智能体 — 程序入口

支持两种运行模式：
1. 命令行传参单次执行: python main.py --keyword "护肤"
2. 无参启动进入交互循环: python main.py

@author honghui
@date 2025/07/15
"""

import argparse
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).parent))

from agent.graph import build_graph
from agent.state import create_initial_state
from config.settings import get_settings
from database.db_manager import get_db_manager
from utils.logger import get_logger, add_file_handler, remove_file_handler

logger = get_logger(__name__)


def run_task(keyword: str) -> bool:
    """
    执行一次完整的内容生成任务

    @param keyword 赛道关键词
    @return bool 任务是否成功
    @author honghui
    @date 2025/07/15 10:00
    """
    logger.info(f"{'=' * 50}")
    logger.info(f"开始执行任务: {keyword}")
    logger.info(f"{'=' * 50}")

    # 创建初始状态
    state = create_initial_state(keyword)
    task_id = state["task_id"]
    logger.info(f"任务ID: {task_id}")

    # 构建状态机
    graph = build_graph()

    # 执行
    try:
        final_state = graph.invoke(state)

        # 输出结果
        finished = final_state.get("finished", False)
        error_msg = final_state.get("error_msg", "")
        title = final_state.get("title", "")
        cover_path = final_state.get("cover_path", "")

        if finished and not error_msg:
            logger.info(f"{'=' * 50}")
            logger.info(f"✅ 任务完成!")
            logger.info(f"标题: {title}")
            logger.info(f"封面: {cover_path}")
            logger.info(f"{'=' * 50}")
            print(f"\n✅ 任务完成!")
            print(f"   标题: {title}")
            if cover_path:
                print(f"   封面: {cover_path}")
            print(f"   请在 output/ 目录查看完整素材包\n")
            return True
        else:
            logger.error(f"{'=' * 50}")
            logger.error(f"❌ 任务失败: {error_msg}")
            logger.error(f"{'=' * 50}")
            print(f"\n❌ 任务失败: {error_msg}\n")
            return False

    except Exception as e:
        logger.error(f"任务执行异常: {e}")
        print(f"\n❌ 任务异常: {e}\n")
        return False


def interactive_mode():
    """
    交互式循环模式

    启动后持续接收用户输入，执行内容生成任务。

    @author honghui
    @date 2025/07/15 10:00
    """
    print("\n" + "=" * 50)
    print("  小红书AI内容智能体 v1.0")
    print("  输入赛道关键词开始生成，输入 quit 退出")
    print("=" * 50 + "\n")

    while True:
        try:
            keyword = input("🔍 请输入关键词: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见!")
            break

        if not keyword:
            print("⚠️  关键词不能为空，请重新输入\n")
            continue

        if keyword.lower() in ("quit", "exit", "q"):
            print("再见!")
            break

        run_task(keyword)


def main():
    """
    主入口函数

    解析命令行参数，决定运行模式。

    @author honghui
    @date 2025/07/15 10:00
    """
    parser = argparse.ArgumentParser(
        description="小红书AI内容智能体 - 全自动爆款内容生成工具"
    )
    parser.add_argument(
        "--keyword", "-k",
        type=str,
        default="",
        help="赛道关键词（传入则单次执行，不传则进入交互模式）",
    )
    args = parser.parse_args()

    # 初始化数据库
    db = get_db_manager()
    db.init_db()

    if args.keyword:
        # 单次执行模式
        success = run_task(args.keyword)
        sys.exit(0 if success else 1)
    else:
        # 交互循环模式
        interactive_mode()


if __name__ == "__main__":
    main()
