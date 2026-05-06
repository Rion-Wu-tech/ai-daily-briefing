# 每日简报运行方案

本文档说明如何使用不同的 AI agent 运行每日简报。

## 方案概览

| 方案 | Agent | 优势 | 适用场景 |
|------|-------|------|---------|
| 方案 1 | Hermes | 灵活、可混合调用 | 需要多工具协作 |
| 方案 2 | Claude Code | 代码和技术分析强 | 技术内容为主 |
| 方案 3 | Codex | OpenAI 代码模型 | 代码生成和分析 |

## 前置要求

1. 已安装 Hermes Agent
2. 已配置 Telegram bot（可选，用于接收简报）
3. 已安装 Claude Code CLI 或 Codex CLI（根据选择的方案）

### 安装 Claude Code
```bash
# 通过 npm 安装
npm install -g @anthropic-ai/claude-code

# 或通过 pip 安装
pip install claude-code
```

### 安装 Codex
```bash
# 通过 npm 安装
npm install -g @openai/codex-cli

# 或通过 pip 安装
pip install openai-codex
```

## 方案 1：使用 Hermes（推荐）

### 手动运行
```bash
hermes run "Load daily-briefing skill and generate today's briefing"
```

### 定时任务（每天早上 8:30）
```bash
hermes cron create \
  --schedule "30 8 * * *" \
  --prompt "Load daily-briefing skill and generate today's briefing for Rion" \
  --deliver telegram \
  --name "每日AI简报"
```

### 使用 Hermes API（Python 脚本）
```python
#!/usr/bin/env python3
import subprocess
import json

def generate_briefing():
    """使用 Hermes 生成每日简报"""
    result = subprocess.run(
        ['hermes', 'run', 'Load daily-briefing skill and generate today\'s briefing'],
        capture_output=True,
        text=True
    )
    return result.stdout

if __name__ == '__main__':
    briefing = generate_briefing()
    print(briefing)
```

## 方案 2：使用 Claude Code

### 手动运行
```bash
claude --acp --stdio << 'EOF'
Load the daily-briefing skill and generate today's briefing for Rion.
Include: AI热点, Web3动态, 投资经济, GitHub项目, 选题素材
EOF
```

### 定时任务（通过 Hermes cron）
```bash
hermes cron create \
  --schedule "30 8 * * *" \
  --prompt "Load daily-briefing skill and generate today's briefing for Rion" \
  --acp-command claude \
  --acp-args "--acp,--stdio" \
  --deliver telegram \
  --name "每日AI简报-Claude"
```

### Python 脚本调用
```python
#!/usr/bin/env python3
import subprocess
import json

def generate_briefing_with_claude():
    """使用 Claude Code 生成每日简报"""
    prompt = """Load the daily-briefing skill and generate today's briefing for Rion.
    
    Include these sections:
    1. AI热点 - Latest AI news and developments
    2. Web3动态 - Web3 and crypto updates
    3. 投资经济 - Investment and economic news
    4. GitHub优质项目 - Trending GitHub projects
    5. 选题素材 - Content ideas for social media
    """
    
    result = subprocess.run(
        ['claude', '--acp', '--stdio'],
        input=prompt,
        capture_output=True,
        text=True
    )
    return result.stdout

if __name__ == '__main__':
    briefing = generate_briefing_with_claude()
    print(briefing)
```

## 方案 3：使用 Codex

### 手动运行
```bash
codex --acp --stdio << 'EOF'
Load the daily-briefing skill and generate today's briefing for Rion.
Include: AI热点, Web3动态, 投资经济, GitHub项目, 选题素材
EOF
```

### 定时任务（通过 Hermes cron）
```bash
hermes cron create \
  --schedule "30 8 * * *" \
  --prompt "Load daily-briefing skill and generate today's briefing for Rion" \
  --acp-command codex \
  --acp-args "--acp,--stdio" \
  --deliver telegram \
  --name "每日AI简报-Codex"
```

### Python 脚本调用
```python
#!/usr/bin/env python3
import subprocess
import json

def generate_briefing_with_codex():
    """使用 Codex 生成每日简报"""
    prompt = """Load the daily-briefing skill and generate today's briefing for Rion.
    
    Include these sections:
    1. AI热点 - Latest AI news and developments
    2. Web3动态 - Web3 and crypto updates
    3. 投资经济 - Investment and economic news
    4. GitHub优质项目 - Trending GitHub projects
    5. 选题素材 - Content ideas for social media
    """
    
    result = subprocess.run(
        ['codex', '--acp', '--stdio'],
        input=prompt,
        capture_output=True,
        text=True
    )
    return result.stdout

if __name__ == '__main__':
    briefing = generate_briefing_with_codex()
    print(briefing)
```

## 方案 4：混合方案（最灵活）

让 Hermes 作为主控，根据需要委托给 Claude Code 或 Codex：

```bash
hermes cron create \
  --schedule "30 8 * * *" \
  --prompt "Generate daily briefing: delegate data collection to claude-code for technical content, use web_search for news, then format and deliver" \
  --toolsets delegation,web,file \
  --deliver telegram \
  --name "每日AI简报-混合"
```

## 系统 Cron 方案（不依赖 Hermes cron）

如果你想用系统的 crontab：

### 1. 创建 Python 脚本
```bash
# 保存为 ~/daily_briefing.py
chmod +x ~/daily_briefing.py
```

### 2. 编辑 crontab
```bash
crontab -e
```

### 3. 添加定时任务
```cron
# 每天早上 8:30 运行（使用 Hermes）
30 8 * * * /usr/bin/python3 ~/daily_briefing.py >> ~/briefing.log 2>&1

# 或使用 Claude Code
30 8 * * * echo "Load daily-briefing skill" | claude --acp --stdio >> ~/briefing.log 2>&1

# 或使用 Codex
30 8 * * * echo "Load daily-briefing skill" | codex --acp --stdio >> ~/briefing.log 2>&1
```

## 发送到 Telegram

如果想把简报发送到 Telegram，可以在脚本中添加：

```python
import requests

def send_to_telegram(message):
    """发送消息到 Telegram"""
    bot_token = "YOUR_BOT_TOKEN"
    chat_id = "YOUR_CHAT_ID"
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    response = requests.post(url, json=data)
    return response.json()

# 在主函数中调用
if __name__ == '__main__':
    briefing = generate_briefing()
    send_to_telegram(briefing)
```

## 查看和管理定时任务

### 查看 Hermes cron 任务
```bash
hermes cron list
```

### 暂停任务
```bash
hermes cron pause <job_id>
```

### 恢复任务
```bash
hermes cron resume <job_id>
```

### 删除任务
```bash
hermes cron remove <job_id>
```

### 立即运行一次
```bash
hermes cron run <job_id>
```

## 故障排查

### 检查 Hermes 日志
```bash
tail -f ~/.hermes/logs/gateway.log
```

### 检查 cron 日志
```bash
# 系统 cron 日志
grep CRON /var/log/syslog

# Hermes cron 输出
ls -la ~/.hermes/cron/output/
```

### 测试脚本
```bash
# 手动运行测试
python3 ~/daily_briefing.py

# 测试 Claude Code
echo "test" | claude --acp --stdio

# 测试 Codex
echo "test" | codex --acp --stdio
```

## 推荐配置

根据你的需求，推荐使用：

- **日常使用**：方案 1（Hermes）- 最灵活，支持多工具
- **技术内容为主**：方案 2（Claude Code）- 代码分析强
- **需要最大灵活性**：方案 4（混合）- 按需调用不同 agent

## 下一步

1. 选择一个方案
2. 配置定时任务
3. 测试运行
4. 根据效果调整

有问题随时问我！
