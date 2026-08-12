<p align="center">
  <a href="./README.md">简体中文</a> | <strong>English</strong>
</p>

# AI Daily Briefing

A daily intelligence and topic-discovery system for AI/Web3 content creators. It collects candidate signals from media outlets, official sources, developer communities, research papers, model rankings, and open-source ecosystems, then turns them into a source-linked Markdown briefing. It also produces a structured editorial packet that Codex can refine into a polished final edition.

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
- Additional signals from Hacker News, arXiv, Hugging Face Trending, and AI HOT
- Official tracking through the Anthropic sitemap and releases from Codex, Claude Code, Gemini CLI, and Transformers
- Web3 news from CoinDesk
- Venture and economic signals from TechCrunch Venture
- High-quality open-source projects from GitHub Trending
- Daily topic ideas that turn news into publishable Chinese content angles
- Codex-friendly offline validation with `--dry-run`, unit tests, and stable output paths
- A concise Chinese explanation for every news item and project, without repetitive labels
- Opening sections for changes since yesterday, must-read items, X opportunities, B2B opportunities, and watchlist signals
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
  aihot: "https://aihot.today/ai-news"

output:
  format: "markdown"
  language: "zh"
  output_dir: "outputs"

limits:
  ai_news: 10
  ai_official_per_source: 3
  web3_news: 3
  venture_news: 5
  github_projects: 10
  topics: 5

quality:
  max_feed_age_days: 10
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
