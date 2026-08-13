<p align="center">
  <a href="./README.md">简体中文</a> | <strong>English</strong>
</p>

# AI Daily Briefing

A daily intelligence and topic-discovery system for AI/Web3 content creators. It collects candidate signals from first-party vendors, infrastructure providers, application products, capital markets, media outlets, developer communities, research papers, and open-source ecosystems, then turns them into a source-linked Markdown briefing. It also produces a structured editorial packet that Codex can refine into a polished final edition.

Every retained item is followed immediately by a concise Chinese explanation covering who did what and the most important result or impact, so readers can understand the event without opening the source link.

After Codex saves the briefing, a bundled Markdown validator rejects linked items that lack a Chinese explanation, contain only metadata, or use known generic filler.

> **Recommended workflow: enter `$daily-briefing Generate today's briefing` directly in Codex. No Hermes or Telegram required.**

## Use Directly in Codex (Recommended)

Clone the repository and install the bundled Codex Skill:

```bash
git clone https://github.com/Rion-Wu-tech/ai-daily-briefing.git
cd ai-daily-briefing
./scripts/install-codex-skill.sh
```

Open a new Codex task, then enter:

```text
$daily-briefing Generate today's briefing
```

You can also specify the scope:

```text
$daily-briefing Find the hottest AI topics from the past 48 hours
$daily-briefing Find model releases from the past 24 hours using official sources only
$daily-briefing Generate a full AI industry-chain briefing for the past 24 hours
$daily-briefing Find AI application adoption and funding from the past seven days
$daily-briefing Generate this week's briefing review
```

Codex fetches, normalizes, deduplicates, scores, and edits the source pool, then saves the final result to:

```text
outputs/briefing_YYYY-MM-DD.md
```

News titles and source links in the document are clickable. The Python layer handles reliable collection and deterministic fallback output, while the current Codex model performs final selection, explanations, section planning, and X draft generation.

If a Skill with the same name already exists, explicitly back it up and replace it:

```bash
./scripts/install-codex-skill.sh --force
```

## Features

- AI news from TechCrunch plus official OpenAI, Google DeepMind, and Hugging Face updates
- A dedicated latest-model section backed by vendor sites, official changelogs, official model cards, and first-party open-weight releases
- Product and tool updates covering new AI features, APIs, pricing, workflows, and major integrations even when no new model is involved
- A full industry-chain view covering upstream compute and infrastructure, midstream models and platforms, and downstream applications and services
- Application-layer signals covering customer adoption, user growth, industry deployment, pricing, revenue, and commercial traction
- AI funding coverage for financings, acquisitions, IPOs, and earnings, with explicit verification status for material figures
- Cross-layer connection cards that link shared themes without claiming an unsupported partnership or causal relationship
- Potentially viral AI stories selected from company announcements, open-source projects, research breakthroughs, funding, industry disputes, and fast-rising community discussions
- Tracking for 42 official Hugging Face organizations, focused on active US and China model teams
- 19 foundation-model release pages plus 38 official update pages for coding, agents, multimodal models, and model platforms
- An official-account radar for 62 model-company and AI-product X accounts; Codex can search them directly, while Python can use the optional X API integration
- Dedicated AI coding and agent coverage for Claude Code, Codex, Cursor, Copilot, Cognition/Devin, Replit, and Manus
- Dedicated multimodal coverage for Runway, Stability AI, FLUX, Midjourney, Luma, Pika, Kling, and Vidu
- Additional signals from Hacker News, arXiv, Hugging Face Trending, and AI HOT
- Automated industry feeds from NVIDIA, AWS, Google Cloud, Product Hunt, Crunchbase News, TechCrunch Venture, and Data Center Dynamics, with sources such as 机器之心 routed to Codex when no stable RSS feed is available
- China-first verification routes that include 36Kr, IT桔子, and HKEX disclosures; adoption and funding figures must still be confirmed with a primary source
- Official tracking through the Anthropic sitemap and releases from Codex, Claude Code, Gemini CLI, and Transformers
- Web3 news from CoinDesk
- Venture and economic signals from TechCrunch Venture
- High-quality open-source projects from GitHub Trending
- Daily topic ideas that turn news into publishable Chinese content angles
- Codex-friendly offline validation with `--dry-run`, unit tests, and stable output paths
- A concise Chinese explanation for every news item and project, without repetitive labels
- Opening sections for changes since yesterday, the AI industry chain, cross-layer connections, model releases, product updates, application trends, AI funding and commercialization, potentially viral stories, must-read items, X opportunities, B2B opportunities, and watchlist signals
- Ranking across content value, business value, personal relevance, timeliness, and credibility, with calibrated scores instead of inflated perfect ratings
- Confidence labels: `Officially confirmed`, `Corroborated by multiple sources`, and `Single-source signal`
- X drafts in three formats: single post, thread, and visual/video script
- SQLite history for first seen, last seen, repeat count, source count, and daily ranking; repeated runs on the same day do not double-count
- Feedback actions for opened, saved, drafted, published, or dismissed items, allowing future ranking to learn from real choices
- Source health tracking for success rate, item count, and latency, with a seven-day health report
- Weekly reviews covering persistent signals, content feedback, preferred categories, source health, and next-week actions
- `--editorial-packet` for a Codex-ready candidate package; the current Codex model handles final editorial judgment while Python remains the deterministic fallback
- A standard Codex Skill, UI metadata, and portable runner bundled in the repository
- Automatic filtering of off-topic AI stories and merging of duplicate links or similar headlines
- Alternating media and official sources, with graceful degradation when one source fails
- A concise bilingual Star invitation at the end of each briefing, using the single canonical repository link

### Two-Axis Intelligence Model

Every item answers two separate questions:

- `industry_layer`: whether the company or product sits upstream, midstream, or downstream
- `event_types`: whether the event is a model release, product update, adoption signal, funding, acquisition, earnings report, or policy change

Capital is not a fourth industry layer. A downstream AI workflow company remains downstream after a financing; it simply gains a `funding` event type. This keeps the industry map readable without letting capital news displace product and adoption signals.

## Current First-Party Coverage

| Region | Model organizations and release sources | Official X accounts |
| --- | --- | --- |
| United States | OpenAI, Anthropic/Claude, Google DeepMind, Meta AI/Llama, xAI/Grok, Microsoft AI/Phi, NVIDIA, Ai2, Amazon Nova, Perplexity, IBM Granite, Salesforce, Snowflake, Liquid AI, Nous Research, Cerebras, Prime Intellect, Inception, Stability AI, and Black Forest Labs | `@OpenAI`, `@AnthropicAI`, `@claudeai`, `@GoogleDeepMind`, `@AIatMeta`, `@SpaceXAI`, `@grok`, `@MicrosoftAI`, `@NVIDIAAI`, `@allen_ai`, `@AWSCloud`, `@perplexity_ai`, `@IBMResearch`, `@SalesforceDevs`, `@SnowflakeDB`, `@LiquidAI`, `@NousResearch`, `@Cerebras`, `@PrimeIntellect`, `@_inception_ai`, `@StabilityAI`, `@bfl_ai` |
| China | Qwen, DeepSeek, Z.ai/GLM, Kimi, MiniMax, Tencent Hunyuan, ByteDance Seed, StepFun, Baichuan, 01.AI, Xiaomi MiMo, InternLM, Baidu ERNIE, Huawei Pangu, iFLYTEK Spark, SenseNova, Meituan LongCat, Kuaishou Kolors, OpenBMB/MiniCPM, OpenGVLab/InternVL, BAAI, Ant Ling, Wan, and Skywork | `@Alibaba_Qwen`, `@deepseek_ai`, `@Zai_org`, `@Kimi_Moonshot`, `@MiniMax_AI`, `@StepFun_ai`, `@ByteDanceSeed`, `@TencentHunyuan`, `@Baidu_Inc`, `@01AI_Yi`, `@BaichuanAI`, `@HuaweiCloud1`, `@SenseTimeGroup`, `@Meituan_LongCat`, `@OpenBMB`, `@BAAIBeijing`, `@AntLingAGI`, `@Alibaba_Wan`, `@Skywork_ai` |
| Other | Mistral AI and Cohere Labs | `@MistralAI`, `@cohere` |

| Product group | Official release sources | Official X accounts |
| --- | --- | --- |
| AI coding and agents | Claude Code, OpenAI Codex, Cursor, GitHub Copilot, Cognition/Devin, Replit, and Manus | `@claudeai`, `@OpenAI`, `@cursor_ai`, `@GitHubCopilot`, `@cognition_labs`, `@Replit`, `@ManusAI` |
| Multimodal models | Runway, Stability AI, Black Forest Labs/FLUX, Midjourney, Ideogram, Luma, Pika, Adobe Firefly, Kling, Vidu, and Wan | `@runwayml`, `@StabilityAI`, `@bfl_ai`, `@midjourney`, `@ideogram_ai`, `@LumaLabsAI`, `@pika_labs`, `@AdobeFirefly`, `@Kling_ai`, `@ViduAI_official`, `@Alibaba_Wan` |
| Audio and music models | ElevenLabs and Suno | `@ElevenLabs`, `@suno_ai_` |
| Model platforms and ecosystem | Hugging Face, OpenRouter, Together AI, Snowflake Cortex, and Salesforce AI | `@huggingface`, `@OpenRouter`, `@togethercompute`, `@SnowflakeDB`, `@SalesforceDevs` |

Vendor pages, changelogs, and model cards confirm facts. X is the fast layer for launches, previews, API or pricing notices, and product updates. Without X API credentials, Codex searches the configured account watchlist during the editorial pass.

To let local Python fetch official-account posts automatically, optionally set:

```bash
export X_BEARER_TOKEN="your X API bearer token"
```

Never place the token in `config.yaml` or commit it to Git.

## Quick Start

```bash
git clone https://github.com/Rion-Wu-tech/ai-daily-briefing.git
cd ai-daily-briefing

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Run the offline validation first:

```bash
python briefing.py --dry-run --no-save
python -m unittest discover -s tests
```

Run a real fetch and save a Markdown briefing:

```bash
python briefing.py
```

The default output path is:

```text
outputs/briefing_YYYY-MM-DD.md
```

## Run with Local Python

The project also works without installing the Codex Skill:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python briefing.py --dry-run --no-save
python -m unittest discover -s tests
```

If the dry run and tests pass, run a live collection:

```bash
python briefing.py
```

See [CODEX.md](./CODEX.md) for the complete agent workflow.

## Common Commands

```bash
# Offline sample data; does not access external websites
python briefing.py --dry-run

# Plain-text output
python briefing.py --format text

# Print JSON without saving
python briefing.py --format json --no-save

# Generate a Codex-ready editorial packet
python briefing.py --editorial-packet --output-file outputs/editorial_packet.json

# Model launches and updates from the past 48 hours
python briefing.py --mode models --hours 48 --format markdown

# AI-video product and feature updates from the past seven days
python briefing.py --mode products --focus "AI video" --hours 168 --format markdown

# Application adoption and growth signals from the past 24 hours
python briefing.py --mode applications --hours 24 --format markdown

# AI financings, acquisitions, IPOs, and earnings from the past seven days
python briefing.py --mode funding --hours 168 --format markdown

# Full upstream/midstream/downstream industry view with cross-layer connections
python briefing.py --mode industry --hours 24 --format markdown

# Potentially viral Agent stories from the past 24 hours
python briefing.py --mode hotspots --focus "Agent" --hours 24 --format markdown

# Debug without reading or writing cross-day history
python briefing.py --no-save --no-history

# Record feedback by item key, full URL, or unique title
python briefing.py --feedback "https://example.com/item" --feedback-action saved
python briefing.py --feedback "Title" --feedback-action published --feedback-note "Published on X"
python briefing.py --feedback "Title" --feedback-action dismissed

# Generate a review for the latest seven days
python briefing.py --weekly-review

# Print the weekly review without saving
python briefing.py --weekly-review --no-save

# Specify an output file
python briefing.py --format markdown --output-file outputs/today.md
```

## Configuration

Edit [config.yaml](./config.yaml):

```yaml
sources:
  ai_news: "https://techcrunch.com/category/artificial-intelligence/"
  ai_official:
    - name: "OpenAI"
      url: "https://openai.com/news/rss.xml"
    - name: "Google DeepMind"
      url: "https://deepmind.google/blog/rss.xml"
    - name: "Hugging Face"
      url: "https://huggingface.co/blog/feed.xml"
  web3_news: "https://www.coindesk.com/"
  venture_news: "https://techcrunch.com/category/venture/"
  github_trending: "https://github.com/trending"
  hacker_news:
    url: "https://hn.algolia.com/api/v1/search"
    queries: ["AI agent", "LLM", "OpenAI", "Claude"]
  arxiv:
    url: "https://export.arxiv.org/api/query"
    query: "cat:cs.AI OR cat:cs.CL OR cat:cs.LG"
  huggingface_models: "https://huggingface.co/api/models"
  official_model_orgs:
    - name: "OpenAI"
      author: "openai"
    - name: "Meta Llama"
      author: "meta-llama"
    - name: "Qwen"
      author: "Qwen"
    - name: "DeepSeek"
      author: "deepseek-ai"
  model_changelogs:
    - name: "Mistral AI"
      url: "https://docs.mistral.ai/resources/changelogs"
      parser: "mistral"
    - name: "QwenCloud"
      url: "https://docs.qwencloud.com/changelog/models"
      parser: "qwen"
  industry_feeds:
    - name: "NVIDIA Blog"
      url: "https://blogs.nvidia.com/feed/"
      track: "infrastructure"
      layer_hint: "upstream"
      authority: "official"
    - name: "Product Hunt"
      url: "https://www.producthunt.com/feed"
      track: "applications"
      layer_hint: "downstream"
      authority: "community"
      discovery_only: true
    - name: "Crunchbase News"
      url: "https://news.crunchbase.com/feed/"
      track: "capital"
      layer_hint: "downstream"
      authority: "media"
      discovery_only: true
  aihot: "https://aihot.today/ai-news"

output:
  format: "markdown"
  language: "zh"
  output_dir: "outputs"

limits:
  ai_news: 10
  ai_official_per_source: 3
  official_model_releases_per_org: 2
  model_changelog_per_source: 3
  model_releases: 8
  industry_chain_per_layer: 3
  application_trends: 6
  ai_funding: 6
  cross_layer_connections: 3
  web3_news: 3
  venture_news: 5
  github_projects: 10
  topics: 5

quality:
  max_feed_age_days: 10
  model_release_max_age_days: 14
  funding_min_source_count: 2
  similarity_threshold: 0.76
  min_similarity_tokens: 4

history:
  enabled: true
  database: "data/briefing_history.sqlite3"
```

## Output Formats

Three formats are supported. Markdown is the default:

- `markdown`: clickable links; suitable for article drafts, newsletters, Feishu, and Obsidian
- `text`: suitable for Telegram, WeChat, and instant messaging
- `json`: suitable for downstream automation

Default Markdown structure:

```text
Changes Since Yesterday
AI Industry Chain
Cross-Layer Connections
Latest Model Releases and Updates
Product and Tool Updates
Application-Layer Trends
Potentially Viral AI News
AI Funding and Commercialization
Official Model-Company Accounts
Must Read
Suitable for X
B2B / Business Opportunities
Watchlist
X Drafts
AI News
Web3 News
Investment & Economy
GitHub Projects
Daily Topic Ideas
Support the Project
```

The generated document currently uses Chinese section labels because the default output language in `config.yaml` is `zh`.

## Project Structure

```text
briefing.py        # CLI and core collection logic
briefing_store.py  # SQLite history and ranking trajectories
config.yaml        # Sources, output format, and item limits
CODEX.md           # Codex and agent instructions
AGENTS.md          # Repository instructions for Codex
scripts/           # Codex Skill installation scripts
skills/daily-briefing/ # Installable Codex Skill
tests/             # Unit tests
outputs/           # Generated local output; not committed to Git
```

Feedback actions:

| Action | Meaning | Ranking impact |
| --- | --- | --- |
| `opened` | Opened and read | Small positive |
| `saved` | Saved | Positive |
| `drafted` | Turned into a draft | Strong positive |
| `published` | Published | Strongest positive |
| `dismissed` | Not useful | Negative |

Feedback adjustments are bounded. They affect the same item, source, and category without replacing the five-dimensional base score.

## Other Agents

The root [SKILL.md](./SKILL.md) remains available for compatibility with other agents. The standard Codex Skill lives at [skills/daily-briefing/SKILL.md](./skills/daily-briefing/SKILL.md). Every entry point uses the same Python core:

```bash
python briefing.py --format markdown
```

## Development Validation

After changing the code, run at least:

```bash
python -m compileall briefing.py briefing_store.py
python -m unittest discover -s tests
python briefing.py --dry-run --no-save
```

If collection logic changed, also run:

```bash
python briefing.py --no-save
```

## License

MIT
