# Codex 运行说明

这份文件给 Codex 或任何刚进入仓库的 agent 使用。

## 0. 推荐：安装后直接调用

```bash
./scripts/install-codex-skill.sh
```

重新打开一个 Codex 任务，然后输入：

```text
$daily-briefing 生成今日早报
```

Codex 会调用 [skills/daily-briefing/SKILL.md](./skills/daily-briefing/SKILL.md)，先生成结构化候选包，再由当前模型完成最终选稿和中文编排，保存为 `outputs/briefing_YYYY-MM-DD.md`。整个流程不依赖 Hermes 或 Telegram。

也可以只追踪第一手模型发布与更新：

```text
$daily-briefing 检索最近 24 小时最新模型发布与更新，只看官方来源
```

Skill 会先检查厂商官网、官方更新日志、官方模型卡、官方 Releases 和中美主要模型/Agent 产品的 X 官方账号，再处理媒体热点；二手报道不能代替模型发布源。模型动态包括首发、版本升级、能力更新、API 与价格变化、下线和开放权重变化。没有配置 X API 时，Codex 会按精编包中的账号清单直接联网检索。Claude Code、Codex、Cursor、Copilot 等产品更新从 `sections.official_product_watchlist` 单独核验，避免和基础模型发布混为一谈。

也可以按时间、赛道和类型生成定向简报：

```text
$daily-briefing 查看过去 48 小时可能爆火的 AI 热点
$daily-briefing 只看最近 7 天 AI 视频产品更新
$daily-briefing 查看过去 24 小时 AI 应用落地和采用趋势
$daily-briefing 查看最近 7 天 AI 投融资与商业化
$daily-briefing 生成过去 24 小时 AI 全产业链简报
$daily-briefing 只看过去 24 小时医疗 AI 新闻
```

## 1. 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## 2. 离线验证

先跑 dry-run。它使用内置样例数据，不访问 TechCrunch、OpenAI、Google DeepMind、Hugging Face、CoinDesk 或 GitHub，适合检查环境是否可用。

```bash
python briefing.py --dry-run --no-save
python -m unittest discover -s tests
```

看到 `Rion 每日早报`、`AI 产业链全景`、`产业链联动`、`最新模型发布与更新`、`产品与工具更新`、`应用层趋势`、`AI 投融资与商业化`、`可能爆火的 AI 新闻`、`今日必须看`、`适合发 X`、`B端/商业机会`、`AI 热点` 和 `GitHub 优质项目`，就说明基础链路正常。

## 3. 真实抓取

```bash
python briefing.py
```

默认会保存到 `outputs/briefing_YYYY-MM-DD.md`，里面的新闻标题和项目名都是可点击链接。候选池包含厂商官方模型发布源、算力与云基础设施、AI 应用、融资与商业信号、AI 编程/Agent 产品 Changelog、模型公司与产品 X 官方账号、媒体、官方 RSS/sitemap、Hacker News、arXiv、Hugging Face Trending、AI HOT 和指定 GitHub Releases。输出会给出上中下游产业链、跨层联动、最新模型发布、应用采用、投融资核验、官方账号动态、跨日变化、五维评分、商业机会和三种 X 草稿。

产业位置和事件类型必须分开：`industry_layer` 只允许上游、中游、下游；融资、并购、财报、产品更新和客户采用写入 `event_types`。资本不是第四层，融资后的应用公司仍然属于下游。

Skill 内部使用的两阶段精编命令：

```bash
python briefing.py --editorial-packet --output-file outputs/editorial_packet.json
```

先读取 `sections.model_releases`，再读取 `sections.editorial_queue`，由当前 Codex 模型完成最终选稿与中文改写。只允许基于候选包事实写作，必须保留原始链接。CLI 的 Markdown 是无模型环境下的确定性兜底。

Codex 保存精编版后会运行：

```bash
python skills/daily-briefing/scripts/validate-briefing.py outputs/briefing_YYYY-MM-DD.md
```

检查每个可点击条目后是否紧跟具体中文概括，并拦截只有来源/评分或空泛模板的内容。

常用变体：

```bash
python briefing.py --format markdown
python briefing.py --mode models --hours 48 --format markdown
python briefing.py --mode products --focus "AI视频" --hours 168 --format markdown
python briefing.py --mode applications --hours 24 --format markdown
python briefing.py --mode funding --hours 168 --format markdown
python briefing.py --mode industry --hours 24 --format markdown
python briefing.py --mode hotspots --focus "Agent" --hours 24 --format markdown
python briefing.py --format json --no-save
python briefing.py --no-save --no-history
python briefing.py --output-file outputs/today.md --format markdown
```

## 4. 记录反馈和周复盘

Codex 应从当前早报定位条目链接，不让用户重复输入：

```bash
python briefing.py --feedback "<链接>" --feedback-action saved
python briefing.py --feedback "<链接>" --feedback-action drafted
python briefing.py --feedback "<链接>" --feedback-action published
python briefing.py --feedback "<链接>" --feedback-action dismissed
```

动作越接近真实产出，正向权重越高；`dismissed` 会降低同类噪音。所有反馈调整都有上限。

```bash
python briefing.py --weekly-review
```

周复盘读取历史、反馈和来源健康度，不重新联网抓取。

## 5. 修改后的验收清单

```bash
python -m compileall briefing.py briefing_store.py
python -m unittest discover -s tests
python briefing.py --dry-run --no-save
```

如果改了网页抓取逻辑，再补一次：

```bash
python briefing.py --no-save
```

## 6. 设计约定

- 真实网站抓取失败不能让脚本崩掉，要返回空列表并在输出里说明。
- 新增来源时优先使用 RSS；重复内容按规范化 URL 和标题相似度合并。
- 每个新来源独立降级；一个接口失效不能中断其他来源。
- 正常保存时写入 `data/briefing_history.sqlite3`；dry-run 和临时诊断不污染历史。
- 反馈只影响有限排序增量，不能绕过可信度、时效和去重规则。
- `--dry-run` 必须永远可用，它是 Codex/CI 的稳定 smoke test。
- 输出文件不要提交到 Git。
- 个人上下文文件只读，除非 Rion 明确要求修改。
