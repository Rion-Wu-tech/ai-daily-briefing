# 使用指南

## Codex 一句话调用

```bash
./scripts/install-codex-skill.sh
```

重新打开 Codex 任务后输入：

```text
$daily-briefing 生成今日早报
```

Codex 会直接生成带可点击来源链接和中文解读的 `outputs/briefing_YYYY-MM-DD.md`，不需要 Hermes 或 Telegram。

## 安装

```bash
git clone https://github.com/Rion-Wu-tech/ai-daily-briefing.git
cd ai-daily-briefing

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## 先验证环境

```bash
python briefing.py --dry-run --no-save
python -m unittest discover -s tests
```

`--dry-run` 使用内置样例数据，不联网，适合新机器、Codex 或 CI 检查。

## 生成早报

```bash
python briefing.py
```

默认保存为带可点击链接的 Markdown。开头会有 `相比昨天的新变化`、`今日必须看`、`适合发 X`、`B端/商业机会`、`持续跟踪` 和三种形态的 `X 草稿`。每条都有五维评分、可信度标记和简短中文解释：

```text
outputs/briefing_YYYY-MM-DD.md
```

## 输出格式

```bash
# Markdown，默认
python briefing.py --format markdown

# 纯文本
python briefing.py --format text

# JSON
python briefing.py --format json

# Codex 二次精编候选包
python briefing.py --editorial-packet --output-file outputs/editorial_packet.json
```

## 常用参数

```bash
# 只打印，不保存
python briefing.py --no-save

# 临时运行，不读取或更新跨日历史
python briefing.py --no-save --no-history

# 指定输出目录
python briefing.py --output-dir outputs

# 指定完整输出文件
python briefing.py --format markdown --output-file outputs/today.md

# 指定配置文件
python briefing.py --config config.yaml
```

## 记录反馈

目标支持完整链接、`item_key` 或唯一标题：

```bash
python briefing.py --feedback "<链接>" --feedback-action opened
python briefing.py --feedback "<链接>" --feedback-action saved
python briefing.py --feedback "<链接>" --feedback-action drafted
python briefing.py --feedback "<链接>" --feedback-action published
python briefing.py --feedback "<链接>" --feedback-action dismissed
```

Codex 可以根据“第 2 条我发了”直接从当前早报找到链接并记录，不需要再次询问。

## 生成周复盘

```bash
# 默认最近 7 天并保存 Markdown
python briefing.py --weekly-review

# 最近 14 天，只打印 JSON
python briefing.py --weekly-review --weekly-days 14 --format json --no-save
```

周复盘不联网，读取本地 SQLite 中的持续信号、反馈偏好和来源健康度。

## 配置

编辑 `config.yaml`：

```yaml
output:
  format: "markdown"
  output_dir: "outputs"

limits:
  ai_news: 10
  web3_news: 3
  venture_news: 5
  github_projects: 10
  topics: 5
```

## 常见问题

### 抓取失败

外部网站会改页面结构，也可能临时反爬。脚本会保留其他成功板块，并在失败板块显示空结果，不会整条链路崩掉。

### Codex 里怎么确认跑通

```bash
python -m compileall briefing.py briefing_store.py
python -m unittest discover -s tests
python briefing.py --dry-run --no-save
```

如果这三条都过了，项目基础链路就是通的。

### 为什么第一次没有“持续跟踪”

第一次正常保存会创建 `data/briefing_history.sqlite3`。从第二天开始，同一事件会显示首次出现时间、重复次数、综合分变化和排名变化。同一天重复运行不会增加次数；`--dry-run`、`--no-save` 和 `--no-history` 不写历史。
