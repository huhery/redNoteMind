# 小红书AI内容智能体 使用手册

> 输入一个赛道关键词 → 自动完成「爬爆款→分析爆款→原创改写→合规检测→AI封面生成→素材归档」全流程

---

## 目录

- [项目简介](#项目简介)
- [环境要求](#环境要求)
- [安装部署](#安装部署)
- [配置说明](#配置说明)
- [使用方式](#使用方式)
- [输出说明](#输出说明)
- [常见问题](#常见问题)
- [项目结构](#项目结构)
- [注意事项](#注意事项)

---

## 项目简介

本项目是一个**私有化、个人博主专用**的小红书内容生产智能体，全流程自动化：

1. 🔍 **爬虫采集** — 搜索指定赛道，采集高赞爆款笔记
2. 📊 **爆款分析** — AI 提炼爆款共性规律（痛点、结构、标题范式）
3. ✍️ **原创生成** — 100% 原创重构，非改写非搬运
4. ✅ **合规检测** — 双层校验（极限词库 + AI 语义审核）
5. 🎨 **封面生成** — AI 生成竖版封面 + 标题文字叠加
6. 📁 **自动归档** — 结构化文件夹输出，可直接手动发布

**核心特性：**
- 纯本地运行，所有数据私有化
- 无自动发布、无模拟点击、零风控风险
- 支持配置切换不同 AI 模型和绘图服务

---

## 环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10/11（爬虫需要桌面环境） |
| Python | 3.10 或更高版本 |
| 网络 | 需要能访问小红书、豆包API/通义千问API |
| 磁盘空间 | 至少 500MB（含浏览器和字体） |

---

## 安装部署

### 第一步：获取项目代码

```bash
# 进入项目目录
cd F:\code\xhs
```

### 第二步：安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 第三步：安装 Playwright 浏览器

```bash
playwright install chromium
```

首次安装会下载 Chromium 浏览器（约 130MB），请耐心等待。

### 第四步：下载中文字体

封面文字叠加需要中文字体文件，请下载**思源黑体**：

1. 访问：https://github.com/adobe-fonts/source-han-sans/releases
2. 下载 `SourceHanSansCN-Regular.otf`
3. 放置到 `assets/fonts/SourceHanSansCN-Regular.otf`

> 如果不下载字体，封面生成仍可正常工作，会自动使用 Windows 系统字体（微软雅黑）。

### 第五步：配置环境变量

```bash
copy .env.example .env
```

用文本编辑器打开 `.env` 文件，填入你的 API Key（详见下方[配置说明](#配置说明)）。

---

## 配置说明

### .env 文件完整配置项

```env
# ============================
# LLM 大模型配置（必填其一）
# ============================

# 豆包（字节跳动）— 默认使用
DOUBAO_API_KEY=你的豆包API密钥
DOUBAO_MODEL_ID=你的模型端点ID

# 通义千问（阿里）— 备选
QWEN_API_KEY=你的通义千问API密钥

# ============================
# 绘图 API 配置（必填其一）
# ============================

# 通义万相（阿里）— 默认使用
WANXIANG_API_KEY=你的通义万相API密钥

# 豆包绘图（字节）— 备选
DOUBAO_IMAGE_API_KEY=你的豆包绘图密钥

# ============================
# 服务选择
# ============================

LLM_PROVIDER=doubao          # 文案/审核模型：doubao 或 qwen
IMAGE_PROVIDER=wanxiang      # 绘图服务：wanxiang 或 doubao

# ============================
# 爬虫配置
# ============================

CRAWLER_MODE=no_login        # 登录模式：no_login（免登录）或 cookie
CRAWLER_COOKIE=              # Cookie 模式时填入（见下方获取方法）
CRAWLER_MIN_LIKE=800         # 最低点赞数过滤阈值
CRAWLER_MAX_NOTE=10          # 单次最大采集数量
CRAWLER_WAIT_DELAY=2000      # 页面等待延时（毫秒）
CRAWLER_DAILY_LIMIT=5        # 每日采集次数软限制

# ============================
# 文案配置
# ============================

COPY_WORD_MIN=300            # 正文最少字数
COPY_WORD_MAX=800            # 正文最多字数

# ============================
# 路径配置
# ============================

OUTPUT_DIR=./output                                    # 成品输出目录
DB_PATH=./data/xhs_agent.db                           # 数据库文件路径
FONT_PATH=./assets/fonts/SourceHanSansCN-Regular.otf  # 中文字体路径

# ============================
# 日志配置
# ============================

LOG_LEVEL=INFO               # 日志级别：DEBUG/INFO/WARNING/ERROR
```

### API Key 获取方式

#### 豆包 API（推荐）

1. 访问 [火山引擎控制台](https://console.volcengine.com/ark)
2. 开通「模型推理」服务
3. 创建推理接入点（Endpoint），获取 `DOUBAO_MODEL_ID`
4. 在 API Key 管理中获取 `DOUBAO_API_KEY`

> 豆包有免费额度，个人博主日更足够使用。

#### 通义千问 API

1. 访问 [阿里云 DashScope](https://dashscope.aliyun.com/)
2. 开通服务，获取 API Key

#### 通义万相（绘图）

1. 同样在 [DashScope](https://dashscope.aliyun.com/) 中开通
2. 使用与通义千问相同的 API Key 即可

### Cookie 获取方式（可选）

如果免登录模式采集不稳定，可切换为 Cookie 模式：

1. 用 Chrome 浏览器登录小红书网页版 (www.xiaohongshu.com)
2. 按 F12 打开开发者工具
3. 切换到「Application」→「Cookies」→ `www.xiaohongshu.com`
4. 复制所有 Cookie 为字符串格式（`name1=value1; name2=value2; ...`）
5. 粘贴到 `.env` 的 `CRAWLER_COOKIE` 字段
6. 将 `CRAWLER_MODE` 改为 `cookie`

---

## 使用方式

### 方式一：命令行传参（单次执行）

```bash
python main.py --keyword "护肤"
python main.py -k "家居好物"
python main.py --keyword "数码测评"
```

执行完成后自动退出。

### 方式二：交互模式（持续使用）

```bash
python main.py
```

启动后显示交互界面：

```
==================================================
  小红书AI内容智能体 v1.0
  输入赛道关键词开始生成，输入 quit 退出
==================================================

🔍 请输入关键词: 护肤
```

输入关键词回车即开始执行，完成后可继续输入下一个关键词。输入 `quit` 或 `exit` 退出。

### 完整执行流程示例

```
🔍 请输入关键词: 护肤

[INFO] 开始执行任务: 护肤
[INFO] 任务ID: a3f7b2c1...
[INFO] [爬虫节点] 开始采集: 护肤
[INFO] 访问搜索页: https://www.xiaohongshu.com/search_result?keyword=...
[INFO] [爬虫节点] 采集完成，共 8 条笔记
[INFO] [文案节点] 开始生成文案: 护肤
[INFO] [文案节点] 生成成功: 5个你不知道的护肤冷知识...
[INFO] [合规节点] 开始合规检测
[INFO] [合规节点] 检测通过 ✓
[INFO] [封面节点] 开始生成封面
[INFO] [封面节点] 生成成功: ./output/cover_abc123.jpg
[INFO] [归档节点] 归档成功: ./output/20250715_护肤_5个你不知道/

✅ 任务完成!
   标题: 5个你不知道的护肤冷知识，第3个我后悔知道晚了
   封面: ./output/20250715_护肤_5个你不知道/封面.jpg
   请在 output/ 目录查看完整素材包
```

---

## 输出说明

### 输出目录结构

每次任务生成一个独立文件夹：

```
output/
└── 20250715_护肤_5个你不知道/
    ├── 文案.txt          ← 可直接复制发布的完整文案
    ├── 封面.jpg          ← 可直接上传的封面图
    ├── source_hot.json   ← 本次参考的爆款素材（用于复盘）
    └── log.txt           ← 本次任务的完整执行日志
```

### 文案.txt 格式

```
5个你不知道的护肤冷知识，第3个我后悔知道晚了

姐妹们👋今天来聊聊那些被忽略的护肤真相...

💡第一个：洗面奶不是越贵越好
...（完整正文内容）

#护肤 #护肤知识 #敏感肌 #平价护肤 #成分党
```

直接全选复制粘贴到小红书编辑器即可。

### 封面.jpg

- 尺寸：750 × 1000 像素（小红书标准 3:4 竖版）
- 包含：AI 生成的背景图 + 叠加的标题文字
- 格式：高质量 JPG

### source_hot.json

```json
[
  {
    "ref_title": "原始爆款标题",
    "ref_content": "原始爆款正文...",
    "ref_tags": ["标签1", "标签2"],
    "like_num": 12000,
    "crawl_url": "https://...",
    "crawl_time": "2025-07-15 10:30:00"
  }
]
```

---

## 常见问题

### Q: 爬虫采集不到笔记怎么办？

**可能原因及解决方案：**

1. **小红书反爬拦截**
   - 切换为 Cookie 模式（配置 `CRAWLER_MODE=cookie`）
   - 适当增大延时（`CRAWLER_WAIT_DELAY=3000`）

2. **关键词过于冷门**
   - 尝试更热门的关键词
   - 降低点赞阈值（`CRAWLER_MIN_LIKE=500`）

3. **网络问题**
   - 确认可以正常访问 www.xiaohongshu.com

### Q: 文案一直不合规怎么办？

系统会自动重试3次。如果仍然不通过：

1. 可能是赛道本身涉及敏感内容（如医美、保健品）
2. 尝试换一个赛道关键词
3. 检查 `output/` 目录中的日志查看具体违规原因

### Q: 封面生成失败怎么办？

封面生成失败**不影响文案产出**。你可以：

1. 检查绘图 API Key 是否正确
2. 检查 API 额度是否用完
3. 手动用 Canva 或其他工具制作封面

### Q: 如何查看历史生成记录？

所有任务记录保存在 SQLite 数据库中：

```bash
# 使用 Python 查看
python -c "
import sys; sys.path.insert(0, '.')
from database.db_manager import get_db_manager
db = get_db_manager(); db.init_db()
records = db.query_task_records()
for r in records:
    print(f'{r.create_time} | {r.keyword} | {r.title[:30]} | {r.status}')
"
```

### Q: 如何切换不同的 AI 模型？

修改 `.env` 文件中的 `LLM_PROVIDER`：

```env
# 切换到通义千问
LLM_PROVIDER=qwen
QWEN_API_KEY=你的密钥
```

保存后重新运行即可，无需修改代码。

### Q: 采集次数达到限制怎么办？

每日采集限制是**软限制**（默认5次/天），超限时会显示警告但仍可继续执行。

如需调整限制：

```env
CRAWLER_DAILY_LIMIT=10
```

### Q: 如何调试爬虫（看到浏览器界面）？

目前默认无头模式。如需调试，临时修改 `tools/crawler.py` 中的 `headless=True` 改为 `headless=False`，即可看到浏览器操作过程。

---

## 项目结构

```
xhs/
├── main.py                      # 程序入口
├── requirements.txt             # Python 依赖
├── .env.example                 # 环境变量模板
├── .env                         # 实际配置（不入Git）
├── .gitignore
│
├── config/                      # 配置管理
│   └── settings.py              # Pydantic Settings 配置类
│
├── agent/                       # 智能体调度
│   ├── state.py                 # AgentState 状态定义
│   ├── nodes.py                 # 节点函数（5个）
│   └── graph.py                 # LangGraph 状态机
│
├── adapters/                    # API 适配器
│   ├── llm_adapter.py           # LLM（豆包/通义千问）
│   └── image_adapter.py         # 绘图（通义万相/豆包）
│
├── tools/                       # 核心工具
│   ├── prompts.py               # Prompt 模板
│   ├── crawler.py               # 爬虫
│   ├── copywriter.py            # 文案生成
│   ├── compliance.py            # 合规检测
│   ├── cover_generator.py       # 封面生成
│   └── archiver.py              # 归档
│
├── database/                    # 数据层
│   ├── models.py                # 数据模型
│   └── db_manager.py            # SQLite 管理
│
├── utils/                       # 公共工具
│   ├── logger.py                # 日志系统
│   └── exceptions.py            # 异常+重试
│
├── assets/                      # 静态资源
│   ├── fonts/                   # 字体文件
│   └── forbidden_words.txt      # 极限词库
│
├── data/                        # 数据库（自动创建）
└── output/                      # 成品输出（自动创建）
```

---

## 注意事项

### 风控安全

- ⚠️ 本工具**不会自动发布**内容，所有产出需手动发布
- ⚠️ 爬虫有严格限流（单次≤10条、每日≤5次、每条间隔≥2秒）
- ⚠️ 不模拟点击、不模拟登录操作，仅采集公开信息
- ⚠️ 建议每天使用不超过5次，避免频繁访问

### 使用建议

1. **第一次使用**建议先用热门关键词测试（如"护肤"、"穿搭"），确保流程跑通
2. 生成的文案建议**人工通读一遍**再发布，根据个人风格微调
3. 封面图可根据需要用 Canva 等工具二次美化
4. 定期查看 `source_hot.json` 复盘爆款规律，积累赛道经验

### 数据安全

- 所有数据存储在本地，不上传任何第三方平台
- API Key 仅用于调用大模型和绘图服务
- `.env` 文件已在 `.gitignore` 中排除，不会误提交

---

## 后续迭代方向

- [ ] RAG 爆款知识库（沉淀个人赛道专属模板）
- [ ] 批量生成模式（一次生成多篇）
- [ ] 爆款评分系统（点赞/收藏/评论权重打分）
- [ ] Web 管理界面
- [ ] 历史记录管理与对比复盘
