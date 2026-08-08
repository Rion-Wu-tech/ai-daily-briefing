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

看到 `Rion 每日早报`、`今日必须看`、`适合发 X`、`B端/商业机会`、`AI 热点` 和 `GitHub 优质项目`，就说明基础链路正常。

## 3. 真实抓取

```bash
python briefing.py
```

默认会保存到 `outputs/briefing_YYYY-MM-DD.md`，里面的新闻标题和项目名都是可点击链接。候选池包含媒体、官方 RSS/sitemap、Hacker News、arXiv、Hugging Face Trending、AI HOT 和指定 GitHub Releases。输出会给出跨日变化、五维评分、可信度分层、商业机会和三种 X 草稿。

Skill 内部使用的两阶段精编命令：

```bash
python briefing.py --editorial-packet --output-file outputs/editorial_packet.json
```

读取 `sections.editorial_queue`，由当前 Codex 模型完成最终选稿与中文改写。只允许基于候选包事实写作，必须保留原始链接。CLI 的 Markdown 是无模型环境下的确定性兜底。

常用变体：

```bash
python briefing.py --format markdown
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
