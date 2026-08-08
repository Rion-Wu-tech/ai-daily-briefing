---
name: daily-briefing
description: Generate a source-linked Chinese AI/Web3 daily briefing directly in Codex and save the final editorial result as Markdown. Use when the user asks for 今日早报, AI 简报, Web3 简报, daily briefing, recent AI hotspots, GitHub trends, content ideas, briefing feedback, or a weekly briefing review.
---

# Daily Briefing

Use this skill directly in Codex. Do not require Hermes, Telegram, or a separate chat bot.

## Generate Today's Briefing

1. Run the bundled helper to fetch, normalize, deduplicate, and score the source pool:

```bash
skills/daily-briefing/scripts/run-daily-briefing.sh \
  --editorial-packet \
  --output-file "outputs/editorial_packet_$(date +%F).json"
```

When invoked from an installed skill, use the absolute path to this skill's `scripts/run-daily-briefing.sh`.

2. Read `sections.editorial_queue` from the generated JSON. Use the current Codex model to select the strongest items, write concrete Chinese explanations, organize sections, and produce varied X drafts.

3. Save the final document as `outputs/briefing_YYYY-MM-DD.md` in the project directory. Return a clickable local file link.

4. Keep every factual claim within the candidate packet. Preserve original URLs and numbers. Do not invent missing dates, scores, funding amounts, benchmark results, or source agreement.

5. Use clickable Markdown titles. Do not add labels such as `中文总结`, `摘要`, or `一句话介绍` before explanations.

6. Use these sections in order when relevant:

```text
相比昨天的新变化
今日必须看
适合发 X
B端/商业机会
持续跟踪
X 草稿
来源明细
```

7. Distinguish source confidence as `官方确认`, `多源印证`, or `单源信号`. If a source fails, retain successful sections and name the failed source briefly.

8. Make X drafts structurally different: include at least a single post, a thread, and a visual or video script when the candidate pool supports them.

## Deterministic Fallback

If the Codex editorial pass cannot be completed, generate a complete linked Markdown file directly:

```bash
skills/daily-briefing/scripts/run-daily-briefing.sh \
  --format markdown \
  --output-file "outputs/briefing_$(date +%F).md"
```

## Validate The Workflow

For installation or regression checks, run:

```bash
skills/daily-briefing/scripts/run-daily-briefing.sh --dry-run --no-save
```

## Record Feedback

Resolve the item URL from the current Markdown or editorial packet, then run one action without asking the user to repeat the link:

```bash
skills/daily-briefing/scripts/run-daily-briefing.sh --feedback "<URL>" --feedback-action opened
skills/daily-briefing/scripts/run-daily-briefing.sh --feedback "<URL>" --feedback-action saved
skills/daily-briefing/scripts/run-daily-briefing.sh --feedback "<URL>" --feedback-action drafted
skills/daily-briefing/scripts/run-daily-briefing.sh --feedback "<URL>" --feedback-action published
skills/daily-briefing/scripts/run-daily-briefing.sh --feedback "<URL>" --feedback-action dismissed
```

## Generate A Weekly Review

```bash
skills/daily-briefing/scripts/run-daily-briefing.sh --weekly-review
```

The default file is `outputs/weekly_review_YYYY-MM-DD.md`.
