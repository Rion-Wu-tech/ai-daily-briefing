# 每日简报运行方案

这个项目的稳定入口是本地 Python 脚本。Codex、Claude Code、Hermes 都可以围绕这个脚本运行，不需要每次让 agent 重新发明抓取流程。

## Codex 直接调用（主入口）

```bash
./scripts/install-codex-skill.sh
```

重新打开一个 Codex 任务后输入：

```text
$daily-briefing 生成今日早报
```

最终结果会直接保存为 `outputs/briefing_YYYY-MM-DD.md`。不需要 Telegram，也不需要先启动 Hermes。

## 推荐流程

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

python briefing.py --dry-run --no-save
python briefing.py
```

## Codex

在 Codex 打开仓库后，先跑：

```bash
python briefing.py --dry-run --no-save
python -m unittest discover -s tests
```

通过后可直接生成确定性 Markdown：

```bash
python briefing.py --no-save
```

需要 Codex 用当前模型做最终精编时：

```bash
python briefing.py --editorial-packet --output-file outputs/editorial_packet.json
```

Codex 读取候选包后输出最终 Markdown，不需要 Hermes 或 Telegram，也不要求在 Python 里配置模型 API Key。

Codex 还可以把用户反馈写回本地历史库：

```bash
python briefing.py --feedback "<链接>" --feedback-action published
python briefing.py --feedback "<链接>" --feedback-action dismissed
```

每周复盘入口：

```bash
python briefing.py --weekly-review
```

如果需要保存 Markdown：

```bash
python briefing.py --format markdown --output-file outputs/today.md
```

## Claude Code / Hermes

让 agent 进入仓库目录后执行脚本即可：

```bash
python briefing.py --format markdown
```

如果是 Hermes skill，可以把用户请求映射到这条命令。不要优先让 agent 手动逐站浏览，除非脚本抓取结果不够，需要人工补充。

## 系统 Cron

每天早上 8:30 生成 Markdown 版：

```cron
30 8 * * * cd /path/to/ai-daily-briefing && .venv/bin/python briefing.py >> briefing.log 2>&1
```

如果需要纯文本版：

```cron
30 8 * * * cd /path/to/ai-daily-briefing && .venv/bin/python briefing.py --format text >> briefing.log 2>&1
```

## 可选推送

当前仓库只负责生成内容，Codex 可直接读取生成文件。需要额外推送时，再放到外层自动化里做：

1. `python briefing.py --output-file outputs/today.txt`
2. 读取 `outputs/today.txt`
3. 调用 Telegram Bot API 发送

不要把 Bot Token 写进仓库。使用环境变量：

```bash
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
```

## 验收命令

```bash
python -m compileall briefing.py briefing_store.py
python -m unittest discover -s tests
python briefing.py --dry-run --no-save
```

如果改了抓取选择器，再补：

```bash
python briefing.py --no-save
```
