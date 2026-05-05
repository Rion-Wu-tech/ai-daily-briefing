# AI Daily Briefing 🌅

为 AI/Web3 自媒体创作者打造的每日早报生成工具。自动抓取 AI 热点、Web3 动态、投资经济、GitHub 优质项目，并生成选题素材。

## ✨ 特性

- 🤖 **AI 热点**：自动抓取 TechCrunch AI 分类最新 10 条新闻
- 🔗 **Web3 热点**：CoinDesk 最新 3 条加密货币新闻（带情绪标签）
- 💰 **投资 & 经济**：TechCrunch Venture 分类最新 5 条融资新闻
- ⭐ **GitHub Trending**：今日 Trending 前 10 个项目（含语言、Stars、今日新增）
- 💡 **选题素材**：基于热点自动生成 5 个内容创作选题建议

## 🚀 快速开始

### 方式一：作为 Hermes Agent Skill 使用（推荐）

如果你使用 [Hermes Agent](https://github.com/NousResearch/hermes)：

```bash
# 安装 skill
cd ~/.hermes/skills/research
git clone https://github.com/Rion-Wu-tech/ai-daily-briefing.git daily-briefing

# 使用
# 在 Hermes 中直接说："给我今日早报"
```

### 方式二：独立 Python 脚本

```bash
# 克隆仓库
git clone https://github.com/Rion-Wu-tech/ai-daily-briefing.git
cd ai-daily-briefing

# 安装依赖
pip install -r requirements.txt

# 运行
python briefing.py
```

## 📋 输出示例

```
==== 🌅 Rion 每日早报 · 2026.05.05 周二 ====

━━━━━━━━━━━━━━━━━━
🤖 AI 热点（10条）
━━━━━━━━━━━━━━━━━━

1. Nvidia CEO 黄仁勋称 AI 正在"创造大量工作机会"
来源：TechCrunch | 3小时前
尽管工人们担心 AI 带来的就业威胁...

━━━━━━━━━━━━━━━━━━
🔗 Web3 热点（3条）
━━━━━━━━━━━━━━━━━━

1. 比特币曾经讨厌通胀，现在可能相反了
来源：CoinDesk | 4:45 PM（Positive）
比特币正在与通胀信号一起上涨...

━━━━━━━━━━━━━━━━━━
💰 投资 & 经济（5条）
━━━━━━━━━━━━━━━━━━

━━━━━━━━━━━━━━━━━━
⭐ GitHub 优质项目（10条）
━━━━━━━━━━━━━━━━━━

━━━━━━━━━━━━━━━━━━
💡 今日选题素材（5个）
━━━━━━━━━━━━━━━━━━

1. 「AI 智能体编排平台大爆发：ruflo 单日暴涨 2600 星背后的故事」
热点：ruflo 项目今日新增 2,598 stars → ...
```

## 🛠️ 配置

### Hermes Skill 配置

编辑 `SKILL.md` 中的 frontmatter：

```yaml
---
name: daily-briefing
description: 为 Rion 生成每日早报...
tags: [daily, briefing, news, ai, web3, github]
---
```

### 独立脚本配置

编辑 `config.yaml`：

```yaml
sources:
  ai_news: "https://techcrunch.com/category/artificial-intelligence/"
  web3_news: "https://www.coindesk.com/"
  venture_news: "https://techcrunch.com/category/venture/"
  github_trending: "https://github.com/trending"

output:
  format: "text"  # text, markdown, json
  language: "zh"  # zh, en
```

## 📅 定时任务

### Hermes Cron Job

```bash
# 在 Hermes 中设置定时任务
# 每天早上 8:00 (AEDT) 自动推送
```

### Linux Cron

```bash
# 编辑 crontab
crontab -e

# 添加定时任务（每天早上 8:00）
0 8 * * * cd ~/ai-daily-briefing && python briefing.py
```

## 🎯 适用人群

- AI/Web3 自媒体创作者
- 科技内容创作者
- 需要每日科技资讯的从业者
- 想要快速了解行业动态的开发者

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

### 开发计划

- [ ] 支持更多数据源（Hacker News, Product Hunt）
- [ ] 支持自定义模板
- [ ] 添加邮件推送功能
- [ ] Web 界面
- [ ] 多语言支持

## 📄 开源协议

MIT License

## 👤 作者

**Rion Wu**
- X/Twitter: [@rionaifantasy]
- GitHub: [@Rion-Wu-tech](https://github.com/Rion-Wu-tech)

## 🙏 致谢

- [Hermes Agent](https://github.com/NousResearch/hermes) - 强大的 AI Agent 框架
- [TechCrunch](https://techcrunch.com/) - AI 和科技新闻来源
- [CoinDesk](https://www.coindesk.com/) - 加密货币新闻来源
- [GitHub Trending](https://github.com/trending) - 优质开源项目发现

---

如果这个项目对你有帮助，请给个 ⭐️ Star！
