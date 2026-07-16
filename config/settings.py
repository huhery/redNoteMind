"""
全局配置类

基于 Pydantic Settings 实现，支持从 .env 文件读取配置。
所有配置项均有默认值，缺失时不会导致程序崩溃。

@author honghui
@date 2025/07/15
"""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """全局配置，自动从 .env 文件和环境变量加载"""

    # === LLM 配置 ===
    doubao_api_key: str = ""
    doubao_model_id: str = ""
    qwen_api_key: str = ""

    # === 绘图 API ===
    wanxiang_api_key: str = ""
    doubao_image_api_key: str = ""

    # === 服务选择 ===
    llm_provider: str = "doubao"  # doubao / qwen
    image_provider: str = "wanxiang"  # wanxiang / doubao

    # === 爬虫配置 ===
    crawler_min_like: int = 800
    crawler_max_note: int = 10
    crawler_wait_delay: int = 2000  # 毫秒
    crawler_mode: str = "no_login"  # no_login / cookie
    crawler_cookie: str = ""
    crawler_daily_limit: int = 5
    crawler_headless: bool = False  # False=有头模式（绕反爬），True=无头模式（Docker部署用）

    # === 文案配置 ===
    copy_word_min: int = 300
    copy_word_max: int = 800

    # === 路径配置 ===
    output_dir: str = "./output"
    db_path: str = "./data/xhs_agent.db"
    font_path: str = "./assets/fonts/SourceHanSansCN-Regular.otf"

    # === 日志配置 ===
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # 环境变量不区分大小写
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    获取全局配置单例

    使用 lru_cache 确保只实例化一次，避免重复读取 .env 文件。

    @return Settings 全局配置实例
    @author honghui
    @date 2025/07/15 10:00
    """
    return Settings()
