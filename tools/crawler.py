"""
小红书爆款爬虫工具

基于 Playwright 真实浏览器渲染，采集小红书搜索页高赞公开笔记。
支持免登录模式和 Cookie 登录模式，严格遵守风控约束。

@author honghui
@date 2025/07/15
"""

import json
import time
import random
from datetime import date
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

from playwright.sync_api import sync_playwright, Page, Browser, TimeoutError as PwTimeout

from config.settings import get_settings
from database.db_manager import get_db_manager
from database.models import HotMaterial
from utils.exceptions import CrawlerError
from utils.logger import get_logger

logger = get_logger(__name__)


class XhsCrawler:
    """
    小红书爆款爬虫

    根据关键词在小红书搜索页采集高赞公开笔记，支持下滑加载、
    详情页正文采集、点赞过滤、去重、结构化输出。

    @author honghui
    @version 1.0
    @date 2025/07/15
    """

    # 小红书搜索页 URL 模板
    SEARCH_URL = "https://www.xiaohongshu.com/search_result?keyword={keyword}&source=web_search_result_note"

    def __init__(self):
        self._settings = get_settings()
        self._db = get_db_manager()

    def crawl_hot_notes(
        self,
        keyword: str,
        min_like: Optional[int] = None,
        max_note: Optional[int] = None,
        wait_delay: Optional[int] = None,
    ) -> List[dict]:
        """
        采集小红书爆款笔记主入口

        @param keyword 搜索关键词（必填）
        @param min_like 最低点赞数阈值，默认从配置读取
        @param max_note 最大采集数量，默认从配置读取
        @param wait_delay 页面等待延时（毫秒），默认从配置读取
        @return List[dict] 结构化笔记列表
        @author honghui
        @date 2025/07/15 10:00
        """
        if not keyword or not keyword.strip():
            raise CrawlerError("搜索关键词不能为空")

        # 读取配置默认值
        min_like = min_like or self._settings.crawler_min_like
        max_note = max_note or self._settings.crawler_max_note
        wait_delay = wait_delay or self._settings.crawler_wait_delay

        # 检查每日采集限制（软限制）
        self._check_daily_limit()

        logger.info(f"开始采集: keyword={keyword}, min_like={min_like}, max_note={max_note}")

        browser = None
        results = []

        try:
            with sync_playwright() as pw:
                # 启动浏览器
                browser = self._launch_browser(pw)
                page = browser.new_page()

                # 设置页面超时
                page.set_default_timeout(10000)

                # 注入 Cookie（如果配置了）
                self._inject_cookies(page)

                # 访问搜索页（如果需要登录，先走登录流程）
                search_url = self.SEARCH_URL.format(keyword=quote(keyword))
                logger.info(f"访问搜索页: {search_url}")
                page.goto(search_url, wait_until="domcontentloaded")
                self._random_delay(wait_delay)

                # 检测是否需要登录，需要则等待用户手动完成
                self._wait_for_login_if_needed(page, search_url)

                # 等待内容加载
                self._wait_for_content(page)

                # 下滑加载更多
                self._scroll_page(page, rounds=3, delay=wait_delay)

                # 提取笔记卡片信息（链接 + 点赞数）
                note_cards = self._extract_note_cards(page)
                logger.info(f"搜索页提取到 {len(note_cards)} 条笔记卡片")

                # 过滤低赞：like_num=0 说明 selector 未命中，保留这些卡片进详情页获取准确点赞数
                unknown_like = [c for c in note_cards if c["like_num"] == 0]
                qualified_cards = [c for c in note_cards if c["like_num"] >= min_like]

                if unknown_like and not qualified_cards:
                    # 搜索页点赞数全部解析失败，退化为取前 max_note 条进详情页
                    logger.warning(
                        f"搜索页点赞数全部解析为 0（selector 可能失效），"
                        f"将取前 {max_note} 条进详情页获取准确点赞数后再过滤"
                    )
                    qualified_cards = unknown_like
                else:
                    logger.info(f"点赞 >= {min_like} 的笔记: {len(qualified_cards)} 条")

                # 去重（按链接去重）
                qualified_cards = self._deduplicate(qualified_cards)

                # 按点赞数降序排列，取前 max_note 条
                qualified_cards.sort(key=lambda x: x["like_num"], reverse=True)
                qualified_cards = qualified_cards[:max_note]

                if not qualified_cards:
                    logger.warning("无符合条件的笔记，终止采集")
                    return []

                # 逐条进入详情页采集正文
                for i, card in enumerate(qualified_cards):
                    logger.info(f"采集详情 [{i + 1}/{len(qualified_cards)}]: {card['title'][:20]}...")
                    detail = self._fetch_note_detail(page, card)
                    if detail:
                        # 详情页点赞数更准确，用详情页的值做最终过滤
                        if detail["like_num"] >= min_like or detail["like_num"] == 0:
                            # like_num==0 表示详情页也解析失败，保留（宁可多不可少）
                            results.append(detail)
                        else:
                            logger.debug(
                                f"详情页点赞数 {detail['like_num']} < {min_like}，跳过: {card.get('title', '')[:20]}"
                            )
                    # 每条之间固定延时
                    self._random_delay(wait_delay)

                browser.close()

        except PwTimeout as e:
            logger.error(f"页面操作超时: {e}")
            raise CrawlerError(f"页面操作超时: {e}")
        except Exception as e:
            logger.error(f"爬虫异常: {e}")
            if browser:
                browser.close()
            raise CrawlerError(f"爬虫执行异常: {e}")

        # 按点赞数降序最终排序
        results.sort(key=lambda x: x["like_num"], reverse=True)

        logger.info(f"采集完成，共获取 {len(results)} 条有效笔记")

        # 递增每日采集计数
        self._db.increment_crawl_count()

        return results

    def save_results(self, results: List[dict], keyword: str, task_id: str, save_dir: str = "") -> str:
        """
        保存采集结果到数据库和 JSON 文件

        @param results 采集结果列表
        @param keyword 搜索关键词
        @param task_id 关联任务ID
        @param save_dir JSON 文件保存目录（可选）
        @return str JSON 文件路径
        @author honghui
        @date 2025/07/15 10:00
        """
        if not results:
            return ""

        # 写入数据库
        materials = []
        for item in results:
            material = HotMaterial(
                keyword=keyword,
                ref_title=item.get("ref_title", ""),
                ref_content=item.get("ref_content", ""),
                ref_tags=json.dumps(item.get("ref_tags", []), ensure_ascii=False),
                like_num=item.get("like_num", 0),
                crawl_url=item.get("crawl_url", ""),
                task_id=task_id,
            )
            materials.append(material)

        try:
            self._db.insert_hot_materials(materials)
            logger.info(f"已写入 {len(materials)} 条素材到数据库")
        except Exception as e:
            logger.error(f"数据库写入失败: {e}")

        # 生成 JSON 备份文件
        json_path = ""
        if save_dir:
            Path(save_dir).mkdir(parents=True, exist_ok=True)
            json_path = str(Path(save_dir) / "source_hot.json")
        else:
            json_path = "source_hot.json"

        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            logger.info(f"素材 JSON 已保存: {json_path}")
        except Exception as e:
            logger.error(f"JSON 文件写入失败: {e}")

        return json_path

    # ============================================================
    # 私有方法
    # ============================================================

    def _check_daily_limit(self):
        """
        检查每日采集次数（软限制）

        超过限制时打印警告，但不阻断执行。

        @author honghui
        @date 2025/07/15 10:00
        """
        today = date.today().isoformat()
        count = self._db.get_crawl_count(today)
        limit = self._settings.crawler_daily_limit

        if count >= limit:
            logger.warning(
                f"⚠️ 今日已采集 {count} 次（限制 {limit} 次），"
                f"继续采集可能增加平台检测风险。"
            )

    def _launch_browser(self, pw) -> Browser:
        """
        启动 Playwright 浏览器

        通过配置 CRAWLER_HEADLESS 控制是否无头，默认有头模式（headless=False）
        以绕过小红书对无头浏览器的反爬检测。生产环境 Docker 部署时再改为 True。

        @param pw Playwright 实例
        @return Browser 浏览器实例
        @author honghui
        @date 2025/07/15 10:00
        """
        headless = getattr(self._settings, "crawler_headless", False)
        browser = pw.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            ],
        )
        logger.debug(f"浏览器已启动（headless={headless}）")
        return browser

    def _inject_cookies(self, page: Page):
        """
        注入 Cookie（如果配置了 Cookie 模式）

        @param page 页面实例
        @author honghui
        @date 2025/07/15 10:00
        """
        if self._settings.crawler_mode != "cookie":
            return
        if not self._settings.crawler_cookie:
            logger.warning("Cookie 模式已启用但未配置 Cookie 内容，将以免登录模式运行")
            return

        # 解析 Cookie 字符串为列表
        cookies = []
        for item in self._settings.crawler_cookie.split(";"):
            item = item.strip()
            if "=" in item:
                name, value = item.split("=", 1)
                cookies.append({
                    "name": name.strip(),
                    "value": value.strip(),
                    "domain": ".xiaohongshu.com",
                    "path": "/",
                })

        if cookies:
            page.context.add_cookies(cookies)
            logger.info(f"已注入 {len(cookies)} 个 Cookie")

    def _wait_for_content(self, page: Page):
        """
        等待搜索结果内容加载

        超时后打印当前页面 URL，便于判断是否被重定向到登录页或风控页。

        @param page 页面实例
        @author honghui
        @date 2025/07/15 10:00
        """
        try:
            # 等待笔记卡片容器出现
            page.wait_for_selector(
                'div[class*="note-item"], section[class*="note-item"], a[class*="cover"]',
                timeout=15000,
            )
            logger.debug("搜索结果已加载")
        except PwTimeout:
            # 打印当前 URL，判断是否跳转到了登录页/风控页
            current_url = page.url
            page_title = page.title()
            logger.warning(f"搜索结果加载超时，当前页面: url={current_url}, title={page_title}")

    def _is_login_page(self, page: Page) -> bool:
        """
        判断当前页面是否是登录页或登录弹窗

        @param page 页面实例
        @return bool 是否需要登录
        @author honghui
        @date 2025/07/15 10:00
        """
        current_url = page.url
        # URL 包含 login / signin / explore（未登录首页重定向）
        if any(k in current_url for k in ["login", "signin", "passport"]):
            return True

        # 页面中存在登录弹窗或登录按钮
        login_selectors = [
            'div[class*="login"]',
            'div[class*="sign-in"]',
            'button[class*="login"]',
            'input[placeholder*="手机号"]',
            'input[placeholder*="请输入手机号"]',
        ]
        for sel in login_selectors:
            if page.query_selector(sel):
                return True

        return False

    def _wait_for_login_if_needed(self, page: Page, redirect_url: str):
        """
        如果当前页面需要登录，等待用户手动完成后再继续

        浏览器会停留在当前页面，控制台打印提示，
        用户扫码/输入验证码登录后，检测到首页或搜索页加载成功即继续。

        登录成功后自动提取并保存 Cookie，写入 .env 文件（可选）。

        @param page 页面实例
        @param redirect_url 登录成功后要跳转的目标 URL
        @author honghui
        @date 2025/07/15 10:00
        """
        if not self._is_login_page(page):
            return

        logger.warning("=" * 50)
        logger.warning("⚠️  检测到登录页，请在弹出的浏览器窗口中手动登录小红书")
        logger.warning("   扫码或输入手机号+验证码完成登录后，程序将自动继续")
        logger.warning("   等待时间最长 3 分钟...")
        logger.warning("=" * 50)

        # 等待登录成功：检测登录页消失 + 内容加载
        # 最多等待 3 分钟（180秒），每 2 秒检查一次
        max_wait = 180
        interval = 2
        elapsed = 0

        while elapsed < max_wait:
            time.sleep(interval)
            elapsed += interval

            current_url = page.url
            # 不再是登录页，说明登录成功
            if not self._is_login_page(page):
                logger.info(f"✅ 检测到登录成功，当前页面: {current_url}")
                break

            if elapsed % 20 == 0:
                logger.info(f"   仍在等待登录... 已等待 {elapsed}s / {max_wait}s")
        else:
            raise CrawlerError("等待登录超时（3分钟），请重新运行程序")

        # 登录成功后跳转到目标搜索页
        logger.info(f"登录完成，跳转到搜索页: {redirect_url}")
        page.goto(redirect_url, wait_until="domcontentloaded")
        self._random_delay(2000)

        # 提取登录后的 Cookie 并保存，方便下次直接使用
        self._save_cookies_after_login(page)

    def _scroll_page(self, page: Page, rounds: int = 3, delay: int = 2000):
        """
        页面下滑加载更多内容

        @param page 页面实例
        @param rounds 下滑轮数
        @param delay 每轮等待毫秒数
        @author honghui
        @date 2025/07/15 10:00
        """
        for i in range(rounds):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            self._random_delay(delay)
            logger.debug(f"下滑第 {i + 1}/{rounds} 轮完成")

    def _extract_note_cards(self, page: Page) -> List[dict]:
        """
        从搜索结果页提取笔记卡片基础信息

        提取每个卡片的标题、链接、点赞数。
        若提取失败，保存截图和 HTML 到 ./data/debug/ 便于排查 selector 问题。

        @param page 页面实例
        @return List[dict] 笔记卡片信息列表
        @author honghui
        @date 2025/07/15 10:00
        """
        cards = []

        try:
            # 小红书搜索结果页的笔记卡片选择器
            # 注意：小红书页面结构可能变化，这里使用多种选择器兼容
            note_elements = page.query_selector_all(
                'section.note-item, div[class*="note-item"], a[class*="note-item"]'
            )

            if not note_elements:
                # 备选选择器
                note_elements = page.query_selector_all('[data-v-a264b01a]')

            if not note_elements:
                # selector 全部失配，保存 debug 信息便于排查
                self._save_debug_snapshot(page)
            else:
                # 找到了卡片，把第一个真实笔记卡片（跳过推荐搜索卡片）的 HTML 存下来
                # 用于在点赞 selector 失配时分析真实结构
                self._dump_first_note_card(note_elements)

            for element in note_elements:
                try:
                    card = self._parse_card_element(page, element)
                    if card:
                        cards.append(card)
                except Exception as e:
                    logger.debug(f"解析卡片失败，跳过: {e}")
                    continue

        except Exception as e:
            logger.warning(f"提取笔记卡片异常: {e}")

        return cards

    def _dump_first_note_card(self, note_elements: list):
        """
        把第一个不是"推荐搜索"的笔记卡片 HTML 存到 ./data/debug/card_real.html

        @param note_elements 卡片元素列表
        @author honghui
        @date 2025/07/16 10:00
        """
        try:
            debug_dir = Path("./data/debug")
            debug_dir.mkdir(parents=True, exist_ok=True)
            for el in note_elements:
                html = el.evaluate("e => e.outerHTML")
                # 跳过"大家都在搜"推荐卡片
                if "query-note" in html or "query_note" in html:
                    continue
                dump_path = debug_dir / "card_real.html"
                dump_path.write_text(html, encoding="utf-8")
                logger.debug(f"已保存真实笔记卡片 HTML 样本到 {dump_path}")
                break
        except Exception as e:
            logger.debug(f"dump 笔记卡片 HTML 失败: {e}")

    def _save_debug_snapshot(self, page: Page):
        """
        保存调试快照（截图 + HTML）到 ./data/debug/

        selector 全部失配时调用，帮助分析当前页面结构。

        @param page 页面实例
        @author honghui
        @date 2025/07/15 10:00
        """
        try:
            import time as _time
            debug_dir = Path("./data/debug")
            debug_dir.mkdir(parents=True, exist_ok=True)
            ts = int(_time.time())

            screenshot_path = str(debug_dir / f"snapshot_{ts}.png")
            html_path = str(debug_dir / f"snapshot_{ts}.html")

            page.screenshot(path=screenshot_path, full_page=True)
            html_content = page.content()
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            logger.warning(
                f"笔记卡片 selector 未命中，已保存调试快照:\n"
                f"  截图: {screenshot_path}\n"
                f"  HTML: {html_path}\n"
                f"  请打开截图确认页面是否正常加载，再根据 HTML 更新 selector"
            )
        except Exception as e:
            logger.debug(f"保存调试快照失败: {e}")

    def _save_cookies_after_login(self, page: Page):
        """
        登录成功后提取当前 Cookie，保存到 ./data/cookies.txt
        并打印出来，方便用户复制到 .env 的 CRAWLER_COOKIE

        @param page 页面实例
        @author honghui
        @date 2025/07/15 10:00
        """
        try:
            cookies = page.context.cookies()
            # 只保留小红书域名的 Cookie
            xhs_cookies = [c for c in cookies if "xiaohongshu" in c.get("domain", "")]

            if not xhs_cookies:
                return

            # 拼成 key=value; key=value 格式
            cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in xhs_cookies)

            # 保存到文件
            cookie_file = Path("./data/cookies.txt")
            cookie_file.parent.mkdir(parents=True, exist_ok=True)
            cookie_file.write_text(cookie_str, encoding="utf-8")

            logger.info("=" * 50)
            logger.info("✅ Cookie 已自动提取并保存到 ./data/cookies.txt")
            logger.info("   下次运行可在 .env 中配置以下内容跳过手动登录：")
            logger.info("   CRAWLER_MODE=cookie")
            logger.info(f"   CRAWLER_COOKIE={cookie_str[:80]}...（完整内容见 cookies.txt）")
            logger.info("=" * 50)

        except Exception as e:
            logger.debug(f"提取 Cookie 失败: {e}")

    def _parse_card_element(self, page: Page, element) -> Optional[dict]:
        """
        解析单个笔记卡片元素

        @param page 页面实例
        @param element 卡片 DOM 元素
        @return dict 卡片信息或 None
        @author honghui
        @date 2025/07/15 10:00
        """
        # 跳过"大家都在搜"推荐搜索卡片（不是真实笔记）
        el_html = element.evaluate("e => e.outerHTML")
        if "query-note" in el_html or "query_note" in el_html:
            return None

        # 提取标题
        title_el = element.query_selector('a.title span, span[class*="title"]')
        title = title_el.inner_text().strip() if title_el else ""

        # 提取链接：用带 xsec_token 的 search_result 链接（才能正常访问详情页）
        href = ""
        # 优先取 a.cover 的 href（带完整 token）
        link_el = element.query_selector("a.cover, a.mask")
        if not link_el:
            link_el = element.query_selector("a.title")
        if not link_el:
            link_el = element.query_selector('a[href*="/search_result/"]')
        if not link_el:
            link_el = element.query_selector('a[href*="/explore/"]')
        if link_el:
            raw_href = link_el.get_attribute("href") or ""
            href = f"https://www.xiaohongshu.com{raw_href}" if raw_href.startswith("/") else raw_href

        # 提取点赞数：真实 class 是 "count"
        like_num = 0
        like_selectors = [
            "span.count",                          # 当前真实 class
            'span[class*="like-wrapper"] span.count',
            'span[class*="like-wrapper"] span',
            'span[class*="count"]',
            'div[class*="like"] span',
            '[class*="like-count"]',
            '[class*="likeCount"]',
        ]
        for sel in like_selectors:
            el = element.query_selector(sel)
            if el:
                text = el.inner_text().strip()
                parsed = self._parse_like_count(text)
                if parsed > 0:
                    like_num = parsed
                    break

        # 如果所有 selector 都失配，dump 第一个真实笔记卡片 HTML 用于排查
        if like_num == 0 and not hasattr(self, "_like_selector_dumped"):
            self._like_selector_dumped = True
            try:
                dump_path = Path("./data/debug/card_sample.html")
                dump_path.parent.mkdir(parents=True, exist_ok=True)
                dump_path.write_text(el_html, encoding="utf-8")
                logger.warning(
                    "点赞数 selector 全部未命中，已保存卡片 HTML 样本到 "
                    "./data/debug/card_sample.html，请查阅以更新 selector"
                )
            except Exception:
                pass

        if not title and not href:
            return None

        return {
            "title": title,
            "url": href,
            "like_num": like_num,
        }

    def _fetch_note_detail(self, page: Page, card: dict) -> Optional[dict]:
        """
        进入笔记详情页采集完整内容

        包含标题、正文、标签、点赞数。失败时跳过不中断。

        @param page 页面实例
        @param card 卡片基础信息
        @return dict 完整笔记信息或 None
        @author honghui
        @date 2025/07/15 10:00
        """
        url = card.get("url", "")
        if not url:
            return None

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
                self._random_delay(1500)

                # 等待正文加载，兼容多种 selector
                try:
                    page.wait_for_selector(
                        '#detail-desc, [id="detail-desc"], '
                        'div[class*="note-text"], span[class*="note-text"], '
                        'div[class*="desc"], div[class*="content"]',
                        timeout=8000,
                    )
                except PwTimeout:
                    # 超时则 dump 页面 HTML 便于排查，继续尝试提取
                    self._dump_detail_page(page, url)

                # 提取标题
                title = self._extract_detail_title(page)

                # 提取正文
                content = self._extract_detail_content(page)

                # 提取标签
                tags = self._extract_detail_tags(page)

                # 提取点赞数（详情页可能更准确）
                like_num = self._extract_detail_likes(page) or card.get("like_num", 0)

                if not content:
                    # 正文为空时 dump 页面结构以便分析
                    if not hasattr(self, "_detail_dumped"):
                        self._detail_dumped = True
                        self._dump_detail_page(page, url)
                    logger.debug(f"详情页正文为空，跳过: {url}")
                    return None

                return {
                    "ref_title": title or card.get("title", ""),
                    "ref_content": content,
                    "ref_tags": tags,
                    "like_num": like_num,
                    "crawl_url": url,
                    "crawl_time": self._now_iso(),
                }

            except PwTimeout:
                if attempt < max_retries:
                    logger.warning(f"详情页加载超时，重试 ({attempt + 1}/{max_retries}): {url}")
                    time.sleep(2)
                else:
                    logger.warning(f"详情页加载超时，跳过: {url}")
                    return None
            except Exception as e:
                logger.warning(f"详情页采集异常，跳过: {url}, 错误: {e}")
                return None

        return None

    def _extract_detail_title(self, page: Page) -> str:
        """
        从详情页提取笔记标题

        @param page 页面实例
        @return str 标题文本
        @author honghui
        @date 2025/07/15 10:00
        """
        selectors = [
            '#detail-title',
            'div[id="detail-title"]',
            'div[class*="title"] h1',
            'h1[class*="title"]',
            'div[class*="note-title"]',
            'span[class*="title"]',
        ]
        for selector in selectors:
            el = page.query_selector(selector)
            if el:
                text = el.inner_text().strip()
                if text:
                    return text
        return ""

    def _extract_detail_content(self, page: Page) -> str:
        """
        从详情页提取笔记正文

        @param page 页面实例
        @return str 正文文本
        @author honghui
        @date 2025/07/15 10:00
        """
        selectors = [
            '#detail-desc',
            'div[id="detail-desc"]',
            'span[class*="note-text"]',
            'div[class*="note-text"]',
            'div[class*="desc"] span',
            'div[class*="content"] span',
        ]
        for selector in selectors:
            el = page.query_selector(selector)
            if el:
                text = el.inner_text().strip()
                if text and len(text) > 20:
                    return text
        return ""

    def _extract_detail_tags(self, page: Page) -> List[str]:
        """
        从详情页提取笔记标签

        @param page 页面实例
        @return List[str] 标签列表
        @author honghui
        @date 2025/07/15 10:00
        """
        tags = []
        selectors = [
            'a[class*="tag"] span',
            'a[href*="/page/topics/"] span',
            'span[class*="tag"]',
        ]
        for selector in selectors:
            elements = page.query_selector_all(selector)
            for el in elements:
                tag_text = el.inner_text().strip().replace("#", "")
                if tag_text and tag_text not in tags:
                    tags.append(tag_text)
            if tags:
                break

        return tags

    def _extract_detail_likes(self, page: Page) -> int:
        """
        从详情页提取点赞数

        @param page 页面实例
        @return int 点赞数
        @author honghui
        @date 2025/07/15 10:00
        """
        selectors = [
            'span.count',
            'span[class*="like-wrapper"] span.count',
            'span[class*="like-wrapper"] span',
            'button[class*="like"] span.count',
            'button[class*="like"] span',
        ]
        for selector in selectors:
            el = page.query_selector(selector)
            if el:
                text = el.inner_text().strip()
                val = self._parse_like_count(text)
                if val > 0:
                    return val
        return 0

    def _dump_detail_page(self, page: Page, url: str):
        """
        保存详情页 HTML 到 ./data/debug/detail_sample.html 便于分析 selector

        @param page 页面实例
        @param url 详情页 URL
        @author honghui
        @date 2025/07/16 10:00
        """
        try:
            debug_dir = Path("./data/debug")
            debug_dir.mkdir(parents=True, exist_ok=True)
            html = page.content()
            dump_path = debug_dir / "detail_sample.html"
            dump_path.write_text(html, encoding="utf-8")
            logger.warning(
                f"详情页正文 selector 未命中，已保存页面 HTML 到 "
                f"./data/debug/detail_sample.html\n  URL: {url}"
            )
        except Exception as e:
            logger.debug(f"dump 详情页 HTML 失败: {e}")

    def _deduplicate(self, cards: List[dict]) -> List[dict]:
        """
        对笔记卡片去重（按URL和标题）

        @param cards 卡片列表
        @return List[dict] 去重后的列表
        @author honghui
        @date 2025/07/15 10:00
        """
        seen_urls = set()
        seen_titles = set()
        unique = []

        for card in cards:
            url = card.get("url", "")
            title = card.get("title", "")

            if url and url in seen_urls:
                continue
            if title and title in seen_titles:
                continue

            if url:
                seen_urls.add(url)
            if title:
                seen_titles.add(title)
            unique.append(card)

        deduplicated_count = len(cards) - len(unique)
        if deduplicated_count > 0:
            logger.debug(f"去重移除 {deduplicated_count} 条重复笔记")

        return unique

    @staticmethod
    def _parse_like_count(text: str) -> int:
        """
        解析点赞数文本为整数

        支持 "1.2万"、"1200"、"999+" 等格式。

        @param text 点赞数文本
        @return int 点赞数
        @author honghui
        @date 2025/07/15 10:00
        """
        if not text:
            return 0

        text = text.strip().replace("+", "").replace(",", "")

        try:
            if "万" in text:
                return int(float(text.replace("万", "")) * 10000)
            elif "w" in text.lower():
                return int(float(text.lower().replace("w", "")) * 10000)
            else:
                return int(text)
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _random_delay(base_ms: int):
        """
        随机延时，避免固定节奏触发风控

        实际延时为 base_ms 的 0.8~1.3 倍。

        @param base_ms 基础延时毫秒数
        @author honghui
        @date 2025/07/15 10:00
        """
        factor = random.uniform(0.8, 1.3)
        actual_delay = (base_ms * factor) / 1000.0
        time.sleep(actual_delay)

    @staticmethod
    def _now_iso() -> str:
        """获取当前时间 ISO 格式"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
