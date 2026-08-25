#!/usr/bin/env python3
"""Render a Daily Briefing Markdown document as a standalone interactive HTML file."""

from __future__ import annotations

import json
import re
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Optional

import markdown as markdown_lib
from bs4 import BeautifulSoup, Tag


SECTION_KINDS = {
    "相比昨天的新变化": "change",
    "AI 产业链全景": "industry",
    "产业链联动": "industry",
    "最新模型发布": "model",
    "最新模型发布与更新": "model",
    "产品与工具更新": "product",
    "产品更新": "product",
    "应用层趋势": "application",
    "可能爆火的 AI 新闻": "hotspot",
    "AI 投融资与商业化": "funding",
    "模型公司官方账号动态": "social",
    "今日必须看": "must-read",
    "适合发 X": "content",
    "适合发 X 的选题": "content",
    "B端/商业机会": "business",
    "持续跟踪": "watchlist",
    "X 草稿": "draft",
    "来源明细": "sources",
    "支持这个项目 / Support the Project": "support",
}


def _plain_heading(value: str) -> str:
    value = re.sub(r"\[([^]]+)]\([^)]+\)", r"\1", value)
    value = re.sub(r"[`*_#>]", "", value)
    return re.sub(r"\s+", " ", value).strip()


def _slug(value: str, used: set[str]) -> str:
    base = re.sub(r"[^a-z0-9\u3400-\u9fff]+", "-", value.lower()).strip("-")
    base = base or "section"
    candidate = base
    index = 2
    while candidate in used:
        candidate = f"{base}-{index}"
        index += 1
    used.add(candidate)
    return candidate


def _section_kind(title: str) -> str:
    for label, kind in SECTION_KINDS.items():
        if title.startswith(label):
            return kind
    return "detail"


def _confidence(text: str) -> str:
    if "官方确认" in text:
        return "official"
    if "多源印证" in text:
        return "multi"
    if "单源信号" in text or "待官方复核" in text or "待核验" in text:
        return "single"
    return "unspecified"


def _layer(text: str) -> str:
    if "上游" in text:
        return "upstream"
    if "中游" in text:
        return "midstream"
    if "下游" in text:
        return "downstream"
    return "unspecified"


def _estimate_reading_minutes(text: str) -> int:
    chinese = len(re.findall(r"[\u3400-\u9fff]", text))
    latin_words = len(re.findall(r"\b[A-Za-z][A-Za-z0-9'-]*\b", text))
    return max(1, round(chinese / 500 + latin_words / 250))


def _extract_title(markdown_text: str) -> str:
    match = re.search(r"^#\s+(.+)$", markdown_text, re.MULTILINE)
    return _plain_heading(match.group(1)) if match else "AI Daily Briefing"


def _extract_date(title: str) -> str:
    match = re.search(r"20\d{2}[-./]\d{1,2}[-./]\d{1,2}", title)
    return match.group(0).replace(".", "-").replace("/", "-") if match else ""


def _prepare_content(markdown_text: str) -> tuple[str, list[dict[str, str]], dict[str, int]]:
    # The project formatter uses GitHub-compatible three-space list continuations.
    # Python-Markdown expects four spaces to keep those paragraphs inside <li>.
    normalized_markdown = re.sub(r"(?m)^ {3}(?=\S)", "    ", markdown_text)
    rendered = markdown_lib.markdown(
        normalized_markdown,
        extensions=["extra", "sane_lists"],
        output_format="html5",
    )
    source = BeautifulSoup(rendered, "html.parser")
    first_h1 = source.find("h1")
    if first_h1:
        first_h1.decompose()

    for link in source.find_all("a", href=True):
        if str(link["href"]).startswith(("http://", "https://")):
            link["target"] = "_blank"
            link["rel"] = "noopener noreferrer"
            link["class"] = list(link.get("class", [])) + ["source-link"]

    container = source.new_tag("div", attrs={"class": "briefing-content"})
    intro = source.new_tag(
        "section",
        attrs={
            "class": "briefing-section briefing-intro",
            "data-kind": "intro",
            "data-title": "导读",
        },
    )
    container.append(intro)
    current = intro
    nav: list[dict[str, str]] = []
    used_ids: set[str] = set()

    for node in list(source.contents):
        if isinstance(node, Tag) and node.name == "h2":
            title = node.get_text(" ", strip=True)
            section_id = _slug(title, used_ids)
            node["id"] = section_id
            current = source.new_tag(
                "section",
                attrs={
                    "class": "briefing-section",
                    "data-kind": _section_kind(title),
                    "data-title": title,
                    "aria-labelledby": section_id,
                },
            )
            container.append(current)
            current.append(node.extract())
            nav.append({"id": section_id, "title": title, "kind": _section_kind(title)})
        else:
            current.append(node.extract() if hasattr(node, "extract") else node)

    if not intro.get_text(" ", strip=True):
        intro.decompose()

    card_count = 0
    for section in container.select(".briefing-section"):
        section_text = section.get_text(" ", strip=True)
        section["data-confidence"] = _confidence(section_text)
        section["data-layer"] = _layer(section_text)
        section["data-search"] = section_text.lower()
        for item in section.select("li"):
            card_count += 1
            text = item.get_text(" ", strip=True)
            item["class"] = list(item.get("class", [])) + ["briefing-card"]
            item["data-card-id"] = f"card-{card_count}"
            item["data-confidence"] = _confidence(text)
            item["data-layer"] = _layer(text)
            item["data-search"] = text.lower()

    for code_block in container.select("pre"):
        code_block["class"] = list(code_block.get("class", [])) + ["copyable-code"]

    external_urls = {
        str(link["href"])
        for link in container.select("a.source-link[href]")
        if "github.com/Rion-Wu-tech/ai-daily-briefing" not in str(link["href"])
    }
    metrics = {
        "sections": len(nav),
        "cards": card_count,
        "sources": len(external_urls),
        "official": markdown_text.count("官方确认"),
    }
    return str(container), nav, metrics


def render_markdown_html(
    markdown_text: str,
    *,
    source_filename: str = "briefing.md",
    page_title: Optional[str] = None,
) -> str:
    """Return a self-contained interactive HTML document."""
    title = page_title or _extract_title(markdown_text)
    date_label = _extract_date(title) or datetime.now().strftime("%Y-%m-%d")
    content_html, nav, metrics = _prepare_content(markdown_text)
    reading_minutes = _estimate_reading_minutes(markdown_text)
    markdown_json = json.dumps(markdown_text, ensure_ascii=False).replace("</", "<\\/")
    nav_html = "".join(
        f'<a href="#{escape(item["id"])}" data-nav-kind="{escape(item["kind"])}">'
        f'{escape(item["title"])}</a>'
        for item in nav
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <meta name="description" content="可搜索、筛选和收藏的 AI 每日简报">
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4f5f0;
      --surface: #ffffff;
      --surface-soft: #eceee8;
      --ink: #151714;
      --muted: #60665f;
      --line: #d5d9d1;
      --accent: #0b706b;
      --accent-strong: #07514d;
      --signal: #d84b3e;
      --marker: #d8f56b;
      --warning: #b96d00;
      --shadow: 0 10px 30px rgba(21, 23, 20, 0.08);
      --radius: 6px;
    }}
    html[data-theme="dark"] {{
      color-scheme: dark;
      --bg: #141714;
      --surface: #1d211d;
      --surface-soft: #272c27;
      --ink: #f0f2ec;
      --muted: #aeb5ad;
      --line: #3b423a;
      --accent: #58c9bf;
      --accent-strong: #89e1d8;
      --signal: #ff7a6d;
      --marker: #b9d84f;
      --warning: #f2b95f;
      --shadow: 0 14px 36px rgba(0, 0, 0, 0.28);
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; scroll-padding-top: 92px; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      font-size: 16px;
      line-height: 1.72;
      letter-spacing: 0;
    }}
    button, input, select {{ font: inherit; letter-spacing: 0; }}
    button, select {{ cursor: pointer; }}
    a {{ color: var(--accent); text-decoration-thickness: 1px; text-underline-offset: 3px; }}
    a:hover {{ color: var(--accent-strong); }}
    .reading-progress {{
      position: fixed;
      inset: 0 0 auto 0;
      z-index: 100;
      height: 3px;
      background: var(--surface-soft);
    }}
    .reading-progress span {{ display: block; width: 0; height: 100%; background: var(--signal); }}
    .topbar {{
      position: sticky;
      top: 0;
      z-index: 90;
      border-bottom: 1px solid var(--line);
      background: color-mix(in srgb, var(--bg) 92%, transparent);
      backdrop-filter: blur(16px);
    }}
    .topbar-inner {{
      max-width: 1440px;
      margin: 0 auto;
      min-height: 68px;
      padding: 10px 24px;
      display: flex;
      align-items: center;
      gap: 14px;
    }}
    .brand {{ display: flex; align-items: center; gap: 10px; min-width: 210px; font-weight: 760; }}
    .brand-mark {{
      width: 30px;
      height: 30px;
      display: grid;
      place-items: center;
      border: 2px solid var(--ink);
      background: var(--marker);
      color: #151714;
      border-radius: 4px;
      font-weight: 850;
    }}
    .top-search {{ position: relative; flex: 1; max-width: 620px; }}
    .top-search input {{
      width: 100%;
      height: 42px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--surface);
      color: var(--ink);
      padding: 0 42px 0 13px;
      outline: none;
    }}
    .top-search input:focus {{ border-color: var(--accent); box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 18%, transparent); }}
    .search-hint {{ position: absolute; right: 10px; top: 9px; color: var(--muted); font-size: 13px; }}
    .icon-button, .command-button {{
      min-height: 40px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--surface);
      color: var(--ink);
    }}
    .icon-button {{ width: 40px; padding: 0; font-size: 18px; }}
    .command-button {{ padding: 0 13px; font-weight: 650; }}
    .icon-button:hover, .command-button:hover {{ border-color: var(--accent); color: var(--accent-strong); }}
    .page-shell {{ max-width: 1440px; margin: 0 auto; padding: 0 24px 72px; }}
    .briefing-head {{
      padding: 48px 0 30px;
      border-bottom: 1px solid var(--line);
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 28px;
      align-items: end;
    }}
    .eyebrow {{ margin: 0 0 8px; color: var(--signal); font-size: 13px; font-weight: 760; text-transform: uppercase; }}
    .briefing-head h1 {{ margin: 0; max-width: 900px; font-size: 42px; line-height: 1.18; letter-spacing: 0; }}
    .briefing-head p {{ margin: 12px 0 0; max-width: 760px; color: var(--muted); }}
    .metric-grid {{ display: grid; grid-template-columns: repeat(2, 120px); gap: 8px; }}
    .metric {{ border-left: 3px solid var(--accent); padding: 7px 10px; background: var(--surface); }}
    .metric:nth-child(2) {{ border-color: var(--signal); }}
    .metric:nth-child(3) {{ border-color: var(--warning); }}
    .metric:nth-child(4) {{ border-color: var(--marker); }}
    .metric strong {{ display: block; font-size: 21px; line-height: 1.2; }}
    .metric span {{ color: var(--muted); font-size: 12px; }}
    .filterbar {{
      min-height: 66px;
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      border-bottom: 1px solid var(--line);
    }}
    .filterbar label {{ color: var(--muted); font-size: 13px; font-weight: 650; }}
    .filterbar select {{
      height: 38px;
      min-width: 132px;
      padding: 0 32px 0 10px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      color: var(--ink);
      background: var(--surface);
    }}
    .saved-toggle[aria-pressed="true"] {{ background: var(--marker); color: #151714; border-color: #7f941d; }}
    .filter-status {{ margin-left: auto; color: var(--muted); font-size: 13px; }}
    .content-grid {{ display: grid; grid-template-columns: 230px minmax(0, 820px); gap: 52px; align-items: start; justify-content: center; }}
    .section-nav {{ position: sticky; top: 94px; padding: 30px 0; max-height: calc(100vh - 110px); overflow: auto; }}
    .section-nav strong {{ display: block; margin-bottom: 10px; font-size: 13px; color: var(--muted); }}
    .section-nav a {{ display: block; padding: 7px 10px; margin: 2px 0; border-left: 2px solid transparent; color: var(--muted); text-decoration: none; font-size: 14px; line-height: 1.35; }}
    .section-nav a:hover, .section-nav a.active {{ color: var(--ink); border-color: var(--signal); background: var(--surface-soft); }}
    .briefing-content {{ min-width: 0; padding-top: 6px; }}
    .briefing-section {{ padding: 38px 0 26px; border-bottom: 1px solid var(--line); }}
    .briefing-section[hidden], .briefing-card[hidden] {{ display: none !important; }}
    .briefing-section > h2 {{ margin: 0 0 22px; font-size: 27px; line-height: 1.28; letter-spacing: 0; }}
    .briefing-section > h2::before {{ content: ""; display: inline-block; width: 10px; height: 10px; margin: 0 10px 2px 0; background: var(--accent); }}
    .briefing-section[data-kind="hotspot"] > h2::before,
    .briefing-section[data-kind="must-read"] > h2::before {{ background: var(--signal); }}
    .briefing-section[data-kind="funding"] > h2::before,
    .briefing-section[data-kind="business"] > h2::before {{ background: var(--warning); }}
    .briefing-section[data-kind="support"] > h2::before {{ background: var(--marker); }}
    .briefing-section h3 {{ margin: 26px 0 9px; font-size: 19px; line-height: 1.38; letter-spacing: 0; }}
    .briefing-section p {{ margin: 10px 0; }}
    .briefing-section blockquote {{ margin: 16px 0; padding: 13px 16px; border-left: 4px solid var(--accent); background: var(--surface-soft); color: var(--muted); }}
    .briefing-section blockquote p {{ margin: 0; }}
    .briefing-section ul, .briefing-section ol {{ margin: 15px 0; padding: 0; list-style: none; counter-reset: item; }}
    .briefing-card {{
      position: relative;
      margin: 10px 0;
      padding: 18px 54px 18px 18px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--surface);
      box-shadow: none;
    }}
    ol > .briefing-card {{ counter-increment: item; }}
    ol > .briefing-card::before {{
      content: counter(item, decimal-leading-zero);
      display: block;
      margin-bottom: 8px;
      color: var(--signal);
      font-size: 12px;
      font-weight: 800;
    }}
    .briefing-card:hover {{ border-color: color-mix(in srgb, var(--accent) 58%, var(--line)); box-shadow: var(--shadow); }}
    .briefing-card > :first-child {{ margin-top: 0; }}
    .briefing-card > :last-child {{ margin-bottom: 0; }}
    .briefing-card a:first-of-type {{ font-weight: 720; }}
    .save-card {{
      position: absolute;
      top: 12px;
      right: 12px;
      width: 32px;
      height: 32px;
      border: 1px solid var(--line);
      border-radius: 4px;
      background: var(--surface-soft);
      color: var(--muted);
      font-size: 19px;
      line-height: 1;
    }}
    .save-card[aria-pressed="true"] {{ color: #151714; background: var(--marker); border-color: #8da522; }}
    code {{ padding: 2px 5px; border-radius: 3px; background: var(--surface-soft); color: var(--signal); font-family: "SFMono-Regular", Consolas, monospace; font-size: 0.9em; }}
    pre {{ position: relative; overflow: auto; margin: 14px 0; padding: 18px; border: 1px solid var(--line); border-radius: var(--radius); background: #171a17; color: #eef0ea; }}
    pre code {{ padding: 0; background: transparent; color: inherit; }}
    .copy-code {{ position: absolute; top: 8px; right: 8px; min-width: 56px; height: 30px; border: 1px solid #545b53; border-radius: 4px; background: #252a25; color: #eef0ea; font-size: 12px; }}
    table {{ width: 100%; border-collapse: collapse; display: block; overflow-x: auto; }}
    th, td {{ padding: 10px 12px; border: 1px solid var(--line); text-align: left; white-space: nowrap; }}
    th {{ background: var(--surface-soft); }}
    hr {{ border: 0; border-top: 1px solid var(--line); }}
    .empty-state {{ display: none; padding: 64px 0; text-align: center; color: var(--muted); }}
    .empty-state.visible {{ display: block; }}
    .sr-only {{ position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }}
    @media (max-width: 980px) {{
      .topbar-inner {{ flex-wrap: wrap; }}
      .brand {{ min-width: 0; }}
      .top-search {{ order: 3; flex-basis: 100%; max-width: none; }}
      .briefing-head {{ grid-template-columns: 1fr; }}
      .metric-grid {{ grid-template-columns: repeat(4, minmax(92px, 1fr)); }}
      .content-grid {{ display: block; }}
      .section-nav {{ position: sticky; top: 121px; z-index: 70; display: flex; gap: 4px; max-height: none; overflow-x: auto; margin: 0 -24px; padding: 9px 24px; border-bottom: 1px solid var(--line); background: var(--bg); }}
      .section-nav strong {{ display: none; }}
      .section-nav a {{ flex: 0 0 auto; border-left: 0; border-bottom: 2px solid transparent; white-space: nowrap; }}
      .section-nav a.active {{ border-bottom-color: var(--signal); }}
    }}
    @media (max-width: 640px) {{
      body {{ font-size: 15px; }}
      .topbar-inner, .page-shell {{ padding-left: 16px; padding-right: 16px; }}
      .brand span:last-child {{ display: none; }}
      .command-button.secondary {{ display: none; }}
      .briefing-head {{ padding-top: 34px; }}
      .briefing-head h1 {{ font-size: 32px; }}
      .metric-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .filterbar {{ padding: 12px 0; align-items: end; }}
      .filterbar label {{ display: grid; gap: 4px; flex: 1 1 140px; }}
      .filterbar select {{ width: 100%; }}
      .filter-status {{ width: 100%; margin-left: 0; }}
      .section-nav {{ top: 121px; margin-left: -16px; margin-right: -16px; padding-left: 16px; padding-right: 16px; }}
      .briefing-section {{ padding-top: 30px; }}
      .briefing-section > h2 {{ font-size: 23px; }}
      .briefing-card {{ padding: 16px 48px 16px 14px; }}
    }}
    @media print {{
      .topbar, .reading-progress, .filterbar, .section-nav, .save-card, .copy-code {{ display: none !important; }}
      body {{ background: #fff; color: #111; }}
      .page-shell {{ max-width: 900px; padding: 0; }}
      .briefing-head {{ padding-top: 0; }}
      .content-grid {{ display: block; }}
      .briefing-card {{ break-inside: avoid; box-shadow: none; }}
      a {{ color: #111; }}
    }}
  </style>
</head>
<body>
  <div class="reading-progress" aria-hidden="true"><span id="reading-progress-bar"></span></div>
  <header class="topbar">
    <div class="topbar-inner">
      <div class="brand"><span class="brand-mark">AI</span><span>Daily Briefing</span></div>
      <div class="top-search">
        <label class="sr-only" for="briefing-search">搜索简报</label>
        <input id="briefing-search" type="search" placeholder="搜索模型、公司、产品或机会" autocomplete="off">
        <span class="search-hint">/</span>
      </div>
      <button class="command-button secondary" id="download-markdown" type="button" title="下载原始 Markdown">Markdown</button>
      <button class="icon-button" id="print-page" type="button" title="打印或导出 PDF" aria-label="打印或导出 PDF">&#9113;</button>
      <button class="icon-button" id="theme-toggle" type="button" title="切换深浅主题" aria-label="切换深浅主题">&#9680;</button>
    </div>
  </header>

  <div class="page-shell">
    <header class="briefing-head">
      <div>
        <p class="eyebrow">{escape(date_label)} / Intelligence Console</p>
        <h1>{escape(title)}</h1>
        <p>把模型、产品、应用、资本和基础设施放在同一张情报界面里。所有来源保留原始链接，筛选与收藏只存储在当前浏览器。</p>
      </div>
      <div class="metric-grid" aria-label="简报统计">
        <div class="metric"><strong>{metrics["sections"]}</strong><span>栏目</span></div>
        <div class="metric"><strong>{metrics["cards"]}</strong><span>条目</span></div>
        <div class="metric"><strong>{metrics["sources"]}</strong><span>外部来源</span></div>
        <div class="metric"><strong>{reading_minutes}</strong><span>分钟阅读</span></div>
      </div>
    </header>

    <div class="filterbar" aria-label="简报筛选器">
      <label>可信度
        <select id="confidence-filter">
          <option value="all">全部</option>
          <option value="official">官方确认</option>
          <option value="multi">多源印证</option>
          <option value="single">单源信号</option>
        </select>
      </label>
      <label>产业层
        <select id="layer-filter">
          <option value="all">全部</option>
          <option value="upstream">上游</option>
          <option value="midstream">中游</option>
          <option value="downstream">下游</option>
        </select>
      </label>
      <button class="command-button saved-toggle" id="saved-filter" type="button" aria-pressed="false">只看收藏</button>
      <button class="command-button" id="export-saved" type="button">导出收藏</button>
      <span class="filter-status" id="filter-status" aria-live="polite">显示全部内容</span>
    </div>

    <div class="content-grid">
      <nav class="section-nav" aria-label="文章目录"><strong>栏目导航</strong>{nav_html}</nav>
      <main id="briefing-main">{content_html}<div class="empty-state" id="empty-state">没有符合当前条件的内容，请调整搜索或筛选条件。</div></main>
    </div>
  </div>

  <script id="source-markdown" type="application/json">{markdown_json}</script>
  <script>
    (() => {{
      const root = document.documentElement;
      const search = document.getElementById('briefing-search');
      const confidence = document.getElementById('confidence-filter');
      const layer = document.getElementById('layer-filter');
      const savedFilter = document.getElementById('saved-filter');
      const filterStatus = document.getElementById('filter-status');
      const emptyState = document.getElementById('empty-state');
      const cards = [...document.querySelectorAll('.briefing-card')];
      const sections = [...document.querySelectorAll('.briefing-section')];
      const storageKey = 'daily-briefing:saved:' + location.pathname;
      const readSaved = () => {{
        try {{ return JSON.parse(localStorage.getItem(storageKey) || '[]'); }}
        catch (error) {{ return []; }}
      }};
      let saved = new Set(readSaved());

      const normalize = (value) => (value || '').trim().toLowerCase();
      const persist = () => {{
        try {{ localStorage.setItem(storageKey, JSON.stringify([...saved])); }}
        catch (error) {{ /* File URLs may disable storage; the page still works. */ }}
      }};
      const copyText = async (value) => {{
        if (navigator.clipboard?.writeText) {{
          try {{ await navigator.clipboard.writeText(value); return true; }}
          catch (error) {{ /* Fall through to the local textarea fallback. */ }}
        }}
        const textarea = document.createElement('textarea');
        textarea.value = value;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        const copied = document.execCommand('copy');
        textarea.remove();
        return copied;
      }};

      cards.forEach((card) => {{
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'save-card';
        button.innerHTML = '&#9734;';
        button.title = '收藏这条内容';
        button.setAttribute('aria-label', '收藏这条内容');
        const id = card.dataset.cardId;
        const refresh = () => {{
          const active = saved.has(id);
          button.setAttribute('aria-pressed', String(active));
          button.innerHTML = active ? '&#9733;' : '&#9734;';
        }};
        button.addEventListener('click', () => {{
          saved.has(id) ? saved.delete(id) : saved.add(id);
          persist();
          refresh();
          applyFilters();
        }});
        refresh();
        card.appendChild(button);
      }});

      document.querySelectorAll('pre.copyable-code').forEach((block) => {{
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'copy-code';
        button.textContent = '复制';
        button.addEventListener('click', async () => {{
          const copied = await copyText(block.innerText.replace(/^复制/, '').trim());
          button.textContent = copied ? '已复制' : '复制失败';
          setTimeout(() => button.textContent = '复制', 1200);
        }});
        block.appendChild(button);
      }});

      function applyFilters() {{
        const query = normalize(search.value);
        const confidenceValue = confidence.value;
        const layerValue = layer.value;
        const savedOnly = savedFilter.getAttribute('aria-pressed') === 'true';
        let visibleCards = 0;
        let visibleSections = 0;

        sections.forEach((section) => {{
          const sectionCards = [...section.querySelectorAll('.briefing-card')];
          const sectionMatchesQuery = !query || normalize(section.dataset.search).includes(query);
          let sectionCardMatches = 0;

          sectionCards.forEach((card) => {{
            const queryMatch = !query || normalize(card.dataset.search).includes(query) || normalize(section.dataset.title).includes(query);
            const confidenceMatch = confidenceValue === 'all' || card.dataset.confidence === confidenceValue;
            const layerMatch = layerValue === 'all' || card.dataset.layer === layerValue;
            const savedMatch = !savedOnly || saved.has(card.dataset.cardId);
            const show = queryMatch && confidenceMatch && layerMatch && savedMatch;
            card.hidden = !show;
            if (show) {{ sectionCardMatches += 1; visibleCards += 1; }}
          }});

          const filtersAreOpen = confidenceValue === 'all' && layerValue === 'all' && !savedOnly;
          const showSection = sectionCards.length
            ? sectionCardMatches > 0
            : filtersAreOpen && sectionMatchesQuery;
          section.hidden = !showSection;
          if (showSection) visibleSections += 1;
        }});

        document.querySelectorAll('.section-nav a').forEach((link) => {{
          const target = document.getElementById(decodeURIComponent(link.hash.slice(1)));
          link.hidden = !target || Boolean(target.closest('.briefing-section')?.hidden);
        }});

        emptyState.classList.toggle('visible', visibleSections === 0);
        filterStatus.textContent = `显示 ${{visibleSections}} 个栏目 / ${{visibleCards}} 条卡片`;
      }}

      search.addEventListener('input', applyFilters);
      confidence.addEventListener('change', applyFilters);
      layer.addEventListener('change', applyFilters);
      savedFilter.addEventListener('click', () => {{
        const next = savedFilter.getAttribute('aria-pressed') !== 'true';
        savedFilter.setAttribute('aria-pressed', String(next));
        applyFilters();
      }});
      document.addEventListener('keydown', (event) => {{
        if (event.key === '/' && document.activeElement !== search) {{
          event.preventDefault();
          search.focus();
        }}
        if (event.key === 'Escape' && document.activeElement === search) {{
          search.value = '';
          search.blur();
          applyFilters();
        }}
      }});

      let storedTheme = '';
      try {{ storedTheme = localStorage.getItem('daily-briefing:theme') || ''; }}
      catch (error) {{ /* Use the system preference when storage is unavailable. */ }}
      const preferredTheme = storedTheme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
      root.dataset.theme = preferredTheme;
      document.getElementById('theme-toggle').addEventListener('click', () => {{
        root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
        try {{ localStorage.setItem('daily-briefing:theme', root.dataset.theme); }}
        catch (error) {{ /* Theme switching still works for the current page. */ }}
      }});

      document.getElementById('print-page').addEventListener('click', () => window.print());
      document.getElementById('download-markdown').addEventListener('click', () => {{
        const source = JSON.parse(document.getElementById('source-markdown').textContent);
        const blob = new Blob([source], {{ type: 'text/markdown;charset=utf-8' }});
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = {json.dumps(source_filename, ensure_ascii=False)};
        anchor.click();
        URL.revokeObjectURL(url);
      }});
      document.getElementById('export-saved').addEventListener('click', () => {{
        const selected = cards.filter((card) => saved.has(card.dataset.cardId));
        if (!selected.length) {{
          filterStatus.textContent = '还没有收藏内容';
          return;
        }}
        const lines = ['# AI 简报收藏', ''];
        selected.forEach((card) => {{
          const link = card.querySelector('a[href]');
          const title = link ? link.textContent.trim() : card.innerText.trim().split('\\n')[0];
          const url = link ? link.href : '';
          lines.push(`- ${{url ? `[${{title}}](${{url}})` : title}}`);
          lines.push(`  ${{card.innerText.replace(/\\s+/g, ' ').replace(/^\\d+\\s*/, '').trim()}}`, '');
        }});
        const blob = new Blob([lines.join('\\n')], {{ type: 'text/markdown;charset=utf-8' }});
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = 'daily-briefing-saved.md';
        anchor.click();
        URL.revokeObjectURL(url);
      }});

      const progress = document.getElementById('reading-progress-bar');
      addEventListener('scroll', () => {{
        const max = document.documentElement.scrollHeight - innerHeight;
        progress.style.width = `${{max > 0 ? Math.min(100, scrollY / max * 100) : 0}}%`;
      }}, {{ passive: true }});

      const navLinks = [...document.querySelectorAll('.section-nav a')];
      const observer = new IntersectionObserver((entries) => {{
        entries.filter((entry) => entry.isIntersecting).forEach((entry) => {{
          navLinks.forEach((link) => link.classList.toggle('active', link.hash === '#' + entry.target.id));
        }});
      }}, {{ rootMargin: '-20% 0px -70% 0px' }});
      document.querySelectorAll('.briefing-section > h2').forEach((heading) => observer.observe(heading));

      applyFilters();
    }})();
  </script>
</body>
</html>
"""


def render_markdown_file(
    input_path: Path,
    output_path: Optional[Path] = None,
    *,
    page_title: Optional[str] = None,
) -> Path:
    """Render one Markdown file and return the HTML output path."""
    input_path = input_path.expanduser().resolve()
    target = output_path.expanduser().resolve() if output_path else input_path.with_suffix(".html")
    target.parent.mkdir(parents=True, exist_ok=True)
    html = render_markdown_html(
        input_path.read_text(encoding="utf-8"),
        source_filename=input_path.name,
        page_title=page_title,
    )
    target.write_text(html, encoding="utf-8")
    return target
