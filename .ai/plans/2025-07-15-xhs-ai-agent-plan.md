# 小红书AI内容智能体系统 — 实现计划

日期：2025-07-15
设计文档：.ai/designs/2025-07-15-xhs-ai-agent-design.md

---

## 任务总览

共 20 个任务，按依赖关系分为 5 个阶段：

| 阶段 | 说明 | 任务数 | 预估时间 |
|------|------|--------|----------|
| 阶段1 | 基础设施搭建 | 5 | 0.5天 |
| 阶段2 | 数据层 + 适配器层 | 4 | 0.5天 |
| 阶段3 | 工具技能层（5大Skill） | 6 | 2天 |
| 阶段4 | 调度层（LangGraph） | 3 | 1天 |
| 阶段5 | 入口 + 联调 + 优化 | 2 | 1天 |

---

## 阶段1: 基础设施搭建

### Task-001: 项目骨架与依赖配置

**关联需求：** REQ-001
**操作文件：**
- `requirements.txt`（新建）
- `.env.example`（新建）
- `.gitignore`（新建）
- `config/__init__.py`（新建）
- `config/settings.py`（新建）

**具体操作：**
1. 创建 requirements.txt，写入所有依赖及版本约束
2. 创建 .env.example 模板，包含所有可配置的环境变量
3. 创建 .gitignore，排除 .env、data/、output/、__pycache__/ 等
4. 实现 config/settings.py：基于 Pydantic Settings 的配置类，从 .env 读取，所有字段有默认值

**验证标准：**
- `pip install -r requirements.txt` 安装成功
- `from config.settings import Settings; s = Settings()` 不报错，默认值正确

---

### Task-002: 全局日志系统

**关联需求：** REQ-010
**操作文件：**
- `utils/__init__.py`（新建）
- `utils/logger.py`（新建）

**具体操作：**
1. 封装日志工厂函数 `get_logger(name)`
2. 支持双输出：控制台（StreamHandler）+ 文件（FileHandler）
3. 日志格式：`[时间戳] [级别] [模块名] 消息内容`
4. 日志级别通过环境变量 LOG_LEVEL 可配置，默认 INFO
5. 支持动态切换任务级文件输出路径（供归档工具使用）

**验证标准：**
- 调用 `logger.info("test")` 可同时在控制台和文件看到输出
- 日志格式符合规范

---

### Task-003: 统一异常处理与重试装饰器

**关联需求：** REQ-001, REQ-010
**操作文件：**
- `utils/exceptions.py`（新建）

**具体操作：**
1. 定义基础异常类层级：`AgentError` → `CrawlerError`, `LLMError`, `ComplianceError`, `CoverError`, `ArchiveError`
2. 实现 `@retry(max_retries, timeout, exceptions)` 装饰器
3. 重试时自动记录日志（第N次重试，异常信息）
4. 超时通过 `concurrent.futures` 或 `signal` 实现

**验证标准：**
- 装饰器可正确重试指定次数
- 超时后抛出 TimeoutError
- 每次重试有日志输出

---

### Task-004: 项目包初始化文件

**关联需求：** REQ-001
**操作文件：**
- `adapters/__init__.py`（新建）
- `tools/__init__.py`（新建）
- `database/__init__.py`（新建）
- `agent/__init__.py`（新建）

**具体操作：**
1. 创建所有包的 `__init__.py` 文件
2. 各 `__init__.py` 中导出主要公共接口

**验证标准：**
- 所有模块可正确 import

---

### Task-005: 静态资源准备

**关联需求：** REQ-005, REQ-006
**操作文件：**
- `assets/forbidden_words.txt`（新建）
- `assets/fonts/`（创建目录，放置字体文件说明）

**具体操作：**
1. 创建本地极限词库文件 `forbidden_words.txt`，收录数百个高频违禁词（绝对化用语、夸大功效、医疗词汇等），每行一个词
2. 创建 `assets/fonts/README.md`，说明需要下载思源黑体字体文件及下载地址

**验证标准：**
- forbidden_words.txt 包含 200+ 常见违禁词
- 字体目录和说明文件存在

---

## 阶段2: 数据层 + 适配器层

### Task-006: 数据库模型定义

**关联需求：** REQ-002
**操作文件：**
- `database/models.py`（新建）

**具体操作：**
1. 定义 `TaskRecord` dataclass，字段对应 task_record 表
2. 定义 `HotMaterial` dataclass，字段对应 hot_material 表
3. 定义 `CrawlCounter` dataclass，字段对应 crawl_counter 表
4. 每个 dataclass 包含 `to_dict()` 和 `from_row()` 方法

**验证标准：**
- dataclass 可正常实例化
- `to_dict()` 输出正确的字典

---

### Task-007: SQLite 数据库管理器

**关联需求：** REQ-002
**操作文件：**
- `database/db_manager.py`（新建）

**具体操作：**
1. 实现 `DatabaseManager` 类，单例模式
2. `init_db()`：程序启动时自动检测并创建表（执行 DDL）
3. CRUD 方法封装：
   - `insert_task_record(record: TaskRecord)`
   - `update_task_record(task_id, **kwargs)`
   - `query_task_records(keyword=None, status=None) -> List[TaskRecord]`
   - `insert_hot_materials(materials: List[HotMaterial])`
   - `get_crawl_count(date: str) -> int`
   - `increment_crawl_count(date: str)`
4. 连接管理：使用 `with` 语句自动关闭

**验证标准：**
- `init_db()` 后三张表存在
- CRUD 操作正常，数据可查询

---

### Task-008: LLM 统一适配器

**关联需求：** REQ-004, REQ-005
**操作文件：**
- `adapters/llm_adapter.py`（新建）

**具体操作：**
1. 定义 `BaseLLMAdapter` 抽象基类，`chat(system_prompt, user_prompt) -> str`
2. 实现 `DoubaoAdapter`：调用豆包 API（兼容 OpenAI 格式）
3. 实现 `QwenAdapter`：调用通义千问 API
4. 实现工厂函数 `get_llm_adapter(provider: str) -> BaseLLMAdapter`
5. 每个适配器内置超时控制和基础错误处理

**验证标准：**
- `get_llm_adapter("doubao").chat("你是助手", "你好")` 可正常返回（需配置真实 Key）
- provider 切换后调用对应后端

---

### Task-009: 绘图 API 统一适配器

**关联需求：** REQ-006
**操作文件：**
- `adapters/image_adapter.py`（新建）

**具体操作：**
1. 定义 `BaseImageAdapter` 抽象基类，`generate(prompt, width, height) -> bytes`
2. 实现 `WanxiangAdapter`：调用通义万相 API
3. 实现 `DoubaoImageAdapter`：调用豆包绘图 API
4. 实现工厂函数 `get_image_adapter(provider: str) -> BaseImageAdapter`
5. 内置超时控制

**验证标准：**
- `get_image_adapter("wanxiang").generate(prompt, 750, 1000)` 返回图片字节数据
- 切换 provider 后调用对应后端

---

## 阶段3: 工具技能层（5大 Skill）

### Task-010: 爬虫工具——核心采集逻辑

**关联需求：** REQ-003
**操作文件：**
- `tools/crawler.py`（新建）

**具体操作：**
1. 实现 `XhsCrawler` 类，主方法 `crawl_hot_notes(keyword, min_like, max_note, wait_delay) -> List[dict]`
2. 核心流程：
   - 检查每日采集计数（软限制，超限警告）
   - 启动 Playwright 浏览器（无头模式）
   - 支持 Cookie 模式：从配置读取 Cookie 注入
   - 访问小红书搜索页 `https://www.xiaohongshu.com/search_result?keyword=xxx`
   - 下滑3轮加载更多
   - 解析搜索结果卡片，提取笔记链接和点赞数
   - 过滤低赞 + 去重
   - 逐条点击进入详情页，采集标题、正文、标签
   - 每条之间 sleep(2s)
   - 按点赞数倒序排序
   - 结果写入数据库 + 生成 JSON 文件
3. 异常处理：超时重试、元素定位失败跳过、网络异常捕获

**验证标准：**
- 输入关键词后可采集到符合条件的笔记列表
- 输出 JSON 结构正确
- 数据库有记录
- 延时和限制正常生效

---

### Task-011: 文案生成工具——爆款分析与原创

**关联需求：** REQ-004
**操作文件：**
- `tools/copywriter.py`（新建）

**具体操作：**
1. 实现 `CopyWriter` 类，主方法 `generate_copy(hot_material, keyword, word_count_range) -> dict`
2. 核心流程：
   - 构建 System Prompt：定义小红书博主人设、创作规范、格式要求
   - 构建 User Prompt：传入爆款素材 + 关键词 + 字数范围
   - Prompt 中明确要求：先分析爆款共性，再100%原创
   - Prompt 中明确禁止：广告法极限词、绝对化用语
   - 调用 LLM 适配器获取响应
   - 解析响应为 JSON：new_title, content, tags
   - 质量校验：标题字数12-20、正文字数范围、标签数量5个
   - 校验不通过自动重新生成（最多2次）
3. JSON 格式校验 + 异常重试

**验证标准：**
- 输入爆款素材后输出标准 JSON
- 标题字数、正文字数、标签数量符合规范
- 格式错误时能自动重试

---

### Task-012: 合规检测工具——双层校验

**关联需求：** REQ-005
**操作文件：**
- `tools/compliance.py`（新建）

**具体操作：**
1. 实现 `ComplianceChecker` 类，主方法 `check_compliance(title, content) -> dict`
2. 第一层——本地词库 + 在线接口：
   - 加载 `assets/forbidden_words.txt` 到内存集合
   - 精准匹配 + 模糊匹配（包含关系）
   - 在线接口调用句易网 API（可选，降级兜底）
   - 命中返回违规词列表
3. 第二层——LLM 语义审核：
   - 构建审核 Prompt：检测虚假宣传、医疗功效、低俗等
   - 调用 LLM 适配器
   - 解析审核结果（pass/fail + 原因）
4. 返回格式：`{"check_status": bool, "check_msg": str}`

**验证标准：**
- 含极限词的文本返回 False + 违规词列表
- 正常文本两层检测均通过返回 True
- 在线接口超时时降级为纯本地词库

---

### Task-013: 封面生成工具——AI绘图 + 文字叠加

**关联需求：** REQ-006
**操作文件：**
- `tools/cover_generator.py`（新建）

**具体操作：**
1. 实现 `CoverGenerator` 类，主方法 `generate_cover(title, save_dir, style) -> dict`
2. 核心流程：
   - 动态构建绘图 Prompt（基于标题 + 风格 + 随机微调词）
   - 调用绘图适配器生成 750×1000 底图
   - Pillow 打开图片
   - 加载中文字体（思源黑体）
   - 在图片上叠加标题文字（自动换行、居中、半透明底色）
   - 校验最终图片尺寸
   - 保存为 jpg（命名：标题前12字符 + 随机6位）
3. 超时重试2次

**验证标准：**
- 生成的图片为 750×1000 jpg
- 图片上有清晰的中文标题文字
- 文件保存到指定目录

---

### Task-014: 归档工具——结构化输出

**关联需求：** REQ-007
**操作文件：**
- `tools/archiver.py`（新建）

**具体操作：**
1. 实现 `Archiver` 类，主方法 `archive_task(task_state) -> dict`
2. 核心流程：
   - 生成文件夹名：`YYYYMMDD_关键词_标题前6字`
   - 在 output/ 下创建独立文件夹
   - 写入 `文案.txt`：标题 + 空行 + 正文 + 空行 + 标签
   - 复制封面图为 `封面.jpg`
   - 写入 `source_hot.json`：格式化缩进
   - 写入 `log.txt`：全流程日志
   - 写入 task_record 到数据库
3. 异常处理：文件夹创建失败重试、写入失败保留核心素材

**验证标准：**
- output/ 下生成正确命名的文件夹
- 文件夹内4个文件完整
- 文案.txt 排版整洁，可直接复制
- 数据库 task_record 有对应记录

---

### Task-015: Prompt 模板管理

**关联需求：** REQ-004, REQ-005
**操作文件：**
- `tools/prompts.py`（新建）

**具体操作：**
1. 集中管理所有 Prompt 模板常量
2. 包含：
   - `COPYWRITER_SYSTEM_PROMPT`：文案生成系统提示
   - `COPYWRITER_USER_TEMPLATE`：文案生成用户输入模板
   - `COMPLIANCE_SYSTEM_PROMPT`：合规审核系统提示
   - `COMPLIANCE_USER_TEMPLATE`：合规审核用户输入模板
3. 模板使用 Python f-string 或 `.format()` 留参数占位

**验证标准：**
- 所有模板可被正确格式化
- 模板内容符合各工具的业务需求

---

## 阶段4: 调度层（LangGraph 状态机）

### Task-016: AgentState 状态定义

**关联需求：** REQ-008
**操作文件：**
- `agent/state.py`（新建）

**具体操作：**
1. 定义 `AgentState(TypedDict)` 全局状态
2. 字段：keyword, hot_material, title, content, tags, check_result, cover_path, finished, retry_count, error_msg, task_id
3. 定义状态初始化工厂函数 `create_initial_state(keyword) -> AgentState`

**验证标准：**
- AgentState 类型可被 LangGraph 正确使用
- 初始化函数返回完整默认状态

---

### Task-017: 节点函数实现

**关联需求：** REQ-008
**操作文件：**
- `agent/nodes.py`（新建）

**具体操作：**
1. 实现5个节点函数，每个接收 `AgentState` 返回更新后的状态字典：
   - `crawl_node(state) -> dict`：调用 crawler，更新 hot_material
   - `generate_copy_node(state) -> dict`：调用 copywriter，更新 title/content/tags，合规重试时 retry_count+1
   - `compliance_check_node(state) -> dict`：调用 compliance，更新 check_result
   - `generate_cover_node(state) -> dict`：调用 cover_generator，更新 cover_path
   - `archive_node(state) -> dict`：调用 archiver，更新 finished
2. 每个节点内部有 try-except，异常时设置 error_msg 并标记 finished

**验证标准：**
- 每个节点函数可独立调用并正确更新状态
- 异常时不崩溃，error_msg 被正确设置

---

### Task-018: LangGraph 状态机构建

**关联需求：** REQ-008
**操作文件：**
- `agent/graph.py`（新建）

**具体操作：**
1. 实现 `build_graph()` 函数，构建 StateGraph
2. 注册5个节点
3. 定义边：crawl → generate_copy → compliance_check → 条件分支
4. 条件分支路由函数 `compliance_router(state)`：
   - check_result == "passed" → generate_cover
   - retry_count < 3 → generate_copy（重试）
   - else → END（终止）
5. generate_cover → archive → END
6. 返回 compiled graph

**验证标准：**
- `build_graph()` 返回可调用的 compiled graph
- 给定初始状态调用 `graph.invoke(state)` 能正确执行流程

---

## 阶段5: 入口 + 联调

### Task-019: 程序入口

**关联需求：** REQ-009
**操作文件：**
- `main.py`（新建）

**具体操作：**
1. argparse 定义参数：`--keyword`（可选）
2. 有 keyword 时：单次执行，调用 graph.invoke，输出结果后退出
3. 无 keyword 时：进入交互循环
   - 打印欢迎信息和使用说明
   - 循环读取用户输入
   - 输入 quit/exit 退出
   - 输入关键词后执行完整流程
   - 执行完毕打印成品文件夹路径
4. 启动时调用 `init_db()` 确保数据库就绪

**验证标准：**
- `python main.py --keyword "护肤"` 单次执行完整流程
- `python main.py` 进入交互模式
- 异常时有友好错误提示

---

### Task-020: 全流程联调与集成验证

**关联需求：** REQ-001 ~ REQ-010（全部）
**操作文件：**
- 所有文件（联调阶段）

**具体操作：**
1. 端到端执行：输入关键词 → 爬虫 → 文案 → 合规 → 封面 → 归档
2. 验证各节点数据传递正确性
3. 验证合规失败重试流程（可手动触发违规词测试）
4. 验证异常场景：
   - 爬虫无结果时正确终止
   - LLM 超时时重试并报错
   - 封面生成失败时不影响文案归档
5. 检查日志完整性
6. 检查数据库记录正确性
7. 优化爬虫延时参数
8. 检查输出文件夹内容完整性

**验证标准：**
- 完整流程可跑通，产出合格的笔记素材包
- 异常场景有正确的降级和日志
- 所有产出文件格式正确、可直接使用

---

## 任务依赖图

```
阶段1（并行）:
  Task-001 ─┐
  Task-002 ─┤
  Task-003 ─┼──→ 阶段2
  Task-004 ─┤
  Task-005 ─┘

阶段2（部分并行）:
  Task-006 ──→ Task-007（数据库）
  Task-008（LLM适配器，独立）
  Task-009（绘图适配器，独立）
      │
      └──→ 阶段3

阶段3（部分并行）:
  Task-015（Prompt模板，独立）
  Task-010（爬虫，依赖 Task-007）
  Task-011（文案，依赖 Task-008, Task-015）
  Task-012（合规，依赖 Task-005, Task-008, Task-015）
  Task-013（封面，依赖 Task-009）
  Task-014（归档，依赖 Task-007）
      │
      └──→ 阶段4

阶段4（顺序）:
  Task-016 → Task-017 → Task-018
      │
      └──→ 阶段5

阶段5:
  Task-019 → Task-020
```

---

## 风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| 小红书页面结构变化 | 爬虫选择器失效 | 选择器集中定义在常量中，便于快速修改 |
| 豆包 API 格式变化 | LLM 调用失败 | 适配器隔离，只改适配器代码 |
| Playwright 在部分 Windows 版本不稳定 | 爬虫异常 | 超时重试 + 日志 + 用户提示 |
| 思源黑体字体文件较大（~10MB） | 项目体积 | README 说明手动下载，不入 Git |

