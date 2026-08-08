# AGENTS.md - Codex Runbook

这个仓库的目标很简单：让 Rion 可以在 Codex、Claude Code、Hermes 或本地 Python 里生成每日 AI/Web3 简报。

## 默认工作方式

- 默认用简体中文回复，表达自然、直接。
- 优先保持项目能独立运行：`python briefing.py --dry-run --no-save` 必须可用。
- 不要擅自修改 `SOUL.md`、`USER.md`、`MEMORY.md`、`memory/*.md`、`HEARTBEAT.md` 这类个人上下文文件，除非用户明确要求。
- 不要提交每天生成的简报文件；输出应写到 `outputs/` 或 `briefing_*.txt/md/json`，这些已在 `.gitignore`。

## 快速验证

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python briefing.py --dry-run --no-save
python -m unittest discover -s tests
```

## 常用命令

```bash
# 离线样例数据，适合 Codex/CI 验证
python briefing.py --dry-run

# 真实联网抓取，并保存到 outputs/
python briefing.py

# 输出 Markdown
python briefing.py --format markdown

# 输出 JSON，不保存文件
python briefing.py --format json --no-save
```

## 修改代码后的验收

至少运行：

```bash
python -m compileall briefing.py
python -m unittest discover -s tests
python briefing.py --dry-run --no-save
```

如果改了抓取逻辑，再运行一次真实联网命令：

```bash
python briefing.py --no-save
```

外部网站页面结构会变化，抓取失败时要优雅降级，不能让整个脚本崩掉。
