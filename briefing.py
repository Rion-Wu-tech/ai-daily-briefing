#!/usr/bin/env python3
"""
AI Daily Briefing Generator
为 AI/Web3 自媒体创作者生成每日早报。

默认会联网抓取数据；在 Codex、CI 或新机器上验证环境时，可以用
`--dry-run` 走内置样例数据，不依赖外部网站。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from pathlib import Path
from time import monotonic
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import parse_qsl, quote, unquote, urlencode, urljoin, urlsplit, urlunsplit
from xml.etree import ElementTree

import requests
import yaml
from bs4 import BeautifulSoup

from briefing_store import BriefingStore


REPOSITORY_URL = "https://github.com/Rion-Wu-tech/ai-daily-briefing"


DEFAULT_CONFIG: Dict[str, Any] = {
    "sources": {
        "ai_news": "https://techcrunch.com/category/artificial-intelligence/",
        "ai_official": [
            {
                "name": "OpenAI",
                "url": "https://openai.com/news/rss.xml",
            },
            {
                "name": "Google DeepMind",
                "url": "https://deepmind.google/blog/rss.xml",
            },
            {
                "name": "Hugging Face",
                "url": "https://huggingface.co/blog/feed.xml",
            },
        ],
        "web3_news": "https://www.coindesk.com/",
        "venture_news": "https://techcrunch.com/category/venture/",
        "github_trending": "https://github.com/trending",
        "hacker_news": {
            "url": "https://hn.algolia.com/api/v1/search",
            "queries": ["AI agent", "LLM", "OpenAI", "Claude"],
            "lookback_hours": 96,
            "min_points": 20,
        },
        "arxiv": {
            "url": "https://export.arxiv.org/api/query",
            "query": "cat:cs.AI OR cat:cs.CL OR cat:cs.LG",
        },
        "huggingface_models": "https://huggingface.co/api/models",
        "aihot": "https://aihot.today/ai-news",
        "official_sitemaps": [
            {
                "name": "Anthropic",
                "url": "https://www.anthropic.com/sitemap.xml",
                "include": ["/news/", "/research/", "/engineering/"],
            }
        ],
        "github_releases": [
            "openai/codex",
            "anthropics/claude-code",
            "google-gemini/gemini-cli",
            "huggingface/transformers",
        ],
    },
    "output": {
        "format": "markdown",
        "language": "zh",
        "output_dir": "outputs",
    },
    "limits": {
        "ai_news": 10,
        "ai_official_per_source": 3,
        "web3_news": 3,
        "venture_news": 5,
        "github_projects": 10,
        "topics": 5,
        "highlights": 5,
        "x_topics": 5,
        "x_drafts": 3,
        "hacker_news": 5,
        "arxiv": 4,
        "huggingface_models": 4,
        "aihot": 5,
        "official_sitemaps_per_source": 3,
        "github_releases_per_repo": 1,
        "ecosystem_signals": 18,
        "changes": 5,
        "business_opportunities": 5,
        "watchlist": 5,
        "editorial_queue": 20,
    },
    "request": {
        "timeout": 25,
        "user_agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0 Safari/537.36"
        ),
    },
    "quality": {
        "max_feed_age_days": 10,
        "similarity_threshold": 0.76,
        "min_similarity_tokens": 4,
    },
    "history": {
        "enabled": True,
        "database": "data/briefing_history.sqlite3",
    },
    "personalization": {
        "enabled": True,
        "baseline": 36,
        "section_boosts": {
            "ai": 6,
            "web3": 5,
            "venture": 5,
            "github": 8,
        },
        "signals": [
            {
                "label": "Agent / AI 编码",
                "weight": 28,
                "keywords": [
                    "agent",
                    "agents",
                    "agentic",
                    "codex",
                    "claude code",
                    "mcp",
                    "devtools",
                    "swe-bench",
                    "智能体",
                    "多智能体",
                ],
                "reason": "贴合你正在用的 Codex、Claude Code 和 Agent 工作流，适合做工具测评或效率流内容。",
            },
            {
                "label": "B 端 AI 工作流",
                "weight": 24,
                "keywords": [
                    "automation",
                    "workflow",
                    "enterprise",
                    "deployment",
                    "productivity",
                    "office",
                    "meeting",
                    "transcription",
                    "support",
                    "sales",
                    "saas",
                    "b2b",
                    "自动化",
                    "工作流",
                    "办公",
                    "企业",
                ],
                "reason": "能连接到 B 端服务、企业提效或工作流改造，适合发展成案例、咨询或产品 demo。",
            },
            {
                "label": "模型竞争格局",
                "weight": 18,
                "keywords": [
                    "openai",
                    "anthropic",
                    "claude",
                    "google",
                    "gemini",
                    "deepmind",
                    "mistral",
                    "meta",
                    "llama",
                    "microsoft",
                    "copilot",
                    "xai",
                    "grok",
                ],
                "reason": "适合判断模型公司格局、生态路线和未来内容叙事，不只盯单个产品更新。",
            },
            {
                "label": "AI 自媒体信息差",
                "weight": 20,
                "keywords": [
                    "browser",
                    "search",
                    "platform",
                    "creator",
                    "social",
                    "prompt",
                    "system prompt",
                    "system_prompts",
                    "glossary",
                    "open source",
                    "github",
                    "vibe-coded",
                    "浏览器",
                    "搜索",
                    "提示词",
                    "开源",
                ],
                "reason": "适合拆成 X 选题、工具清单、观点单帖或信息差内容。",
            },
            {
                "label": "AI 视频/图像/多模态",
                "weight": 20,
                "keywords": [
                    "video",
                    "image",
                    "vision",
                    "multimodal",
                    "sora",
                    "runway",
                    "midjourney",
                    "stable diffusion",
                    "视频",
                    "图像",
                    "多模态",
                ],
                "reason": "贴近你的 AI 视频和 AI 图像能力，适合做视觉内容、工具测评或多平台素材。",
            },
            {
                "label": "Web3 信息差",
                "weight": 22,
                "keywords": [
                    "web3",
                    "crypto",
                    "bitcoin",
                    "btc",
                    "xrp",
                    "solana",
                    "blockchain",
                    "on-chain",
                    "prediction market",
                    "regulation",
                    "tokenized",
                    "etf",
                    "rwa",
                    "链上",
                    "监管",
                ],
                "reason": "适合做 Web3 信息差、监管变化、市场情绪或链上基础设施解读。",
            },
            {
                "label": "商业化/资本信号",
                "weight": 18,
                "keywords": [
                    "funding",
                    "fund",
                    "venture",
                    "vc",
                    "ipo",
                    "acquisition",
                    "revenue",
                    "valuation",
                    "spending",
                    "capital",
                    "融资",
                    "资本",
                    "上市",
                ],
                "reason": "能辅助判断 AI 商业化、融资风向和潜在变现赛道。",
            },
            {
                "label": "学习/知识库",
                "weight": 12,
                "keywords": [
                    "paper",
                    "research",
                    "benchmark",
                    "course",
                    "book",
                    "learning",
                    "study",
                    "论文",
                    "研究",
                    "教程",
                ],
                "reason": "适合沉淀到知识库，后续可以转成科普、课程或学习路线内容。",
            },
        ],
    },
}

SAMPLE_DATA: Dict[str, List[Dict[str, str]]] = {
    "ai_news": [
        {
            "title": "OpenAI 发布新的开发者工具，降低多智能体应用搭建门槛",
            "url": "https://example.com/openai-agent-tools",
            "time": "示例数据",
            "source": "Sample",
            "summary": "AI 工具链门槛继续下降，开发者可以更快搭建多智能体应用。",
        },
        {
            "title": "芯片公司推出面向端侧 AI 的新一代推理方案",
            "url": "https://example.com/edge-ai-chip",
            "time": "示例数据",
            "source": "Sample",
            "summary": "端侧推理能力继续提升，硬件、应用和本地 AI 会一起受益。",
        },
    ],
    "web3_news": [
        {
            "title": "主流交易平台上线新的链上资产分析功能",
            "url": "https://example.com/web3-analytics",
            "time": "示例数据",
            "source": "Sample",
            "sentiment": "Neutral",
            "summary": "链上数据工具正在变成交易基础设施，安全和透明度会更受关注。",
        }
    ],
    "venture_news": [
        {
            "title": "AI 自动化初创公司完成新一轮融资",
            "url": "https://example.com/ai-startup-funding",
            "time": "示例数据",
            "source": "Sample",
            "summary": "资本继续押注 AI 自动化，B 端工作流仍是商业化主线之一。",
        }
    ],
    "github_projects": [
        {
            "name": "sample/agent-workflow",
            "description": "A practical workflow toolkit for AI agents.",
            "language": "Python",
            "stars": "12,345",
            "today_stars": "321 stars today",
            "url": "https://github.com/sample/agent-workflow",
        },
        {
            "name": "sample/web3-indexer",
            "description": "Simple Web3 data indexer for builders.",
            "language": "TypeScript",
            "stars": "8,888",
            "today_stars": "188 stars today",
            "url": "https://github.com/sample/web3-indexer",
        },
    ],
    "ecosystem_signals": [
        {
            "title": "开发者讨论如何把 AI agent 接进真实工作流",
            "url": "https://news.ycombinator.com/item?id=sample-agent",
            "time": "示例数据",
            "source": "Hacker News",
            "summary": "社区讨论重点从 demo 转向可靠性、权限和任务交付。",
            "popularity": 240,
        },
        {
            "title": "新论文提出更可靠的多智能体协作评测方法",
            "url": "https://arxiv.org/abs/2607.00001",
            "time": "示例数据",
            "source": "arXiv",
            "summary": "研究关注多智能体协作在真实任务里的稳定性和可复现性。",
        },
        {
            "title": "sample-org/creator-video-model",
            "url": "https://huggingface.co/sample-org/creator-video-model",
            "time": "示例数据",
            "source": "Hugging Face Trending",
            "summary": "近期热度上升的多模态模型，适合关注视频内容生产工作流。",
            "popularity": 180,
        },
    ],
}


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge config dictionaries."""
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def contains_chinese(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", value or ""))


def short_title(value: str, max_chars: int = 28) -> str:
    value = clean_text(value)
    if len(value) <= max_chars:
        return value
    return value[:max_chars].rstrip() + "..."


def item_title(item: Dict[str, str]) -> str:
    return clean_text(item.get("title") or item.get("name") or "")


def keyword_in_text(text: str, keyword: str) -> bool:
    text = text.lower()
    keyword = clean_text(keyword.lower())
    if not keyword:
        return False
    if contains_chinese(keyword):
        return keyword in text

    if keyword.endswith("*"):
        stem = re.escape(keyword[:-1])
        return bool(re.search(rf"(?<![a-z0-9]){stem}", text))

    pattern = rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])"
    return bool(re.search(pattern, text))


def has_any_keyword(text: str, keywords: Iterable[str]) -> bool:
    return any(keyword_in_text(text, keyword) for keyword in keywords)


TITLE_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "into",
    "is",
    "it",
    "its",
    "new",
    "of",
    "on",
    "our",
    "that",
    "the",
    "their",
    "this",
    "to",
    "with",
}


def canonical_url(value: str) -> str:
    """Normalize URLs so tracking parameters do not create duplicate stories."""
    value = clean_text(value)
    if not value:
        return ""

    parts = urlsplit(value)
    query = [
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
        and key.lower() not in {"ref", "source", "campaign", "fbclid", "gclid"}
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            path,
            urlencode(sorted(query)),
            "",
        )
    )


def normalized_title_tokens(value: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", clean_text(value).lower())
    tokens: set[str] = set()
    for word in words:
        if word in TITLE_STOPWORDS:
            continue
        if contains_chinese(word) and len(word) > 3:
            tokens.update(word[index : index + 2] for index in range(len(word) - 1))
        else:
            tokens.add(word)
    return tokens


def title_similarity(left: str, right: str) -> float:
    left_clean = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", clean_text(left).lower()).strip()
    right_clean = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", clean_text(right).lower()).strip()
    if not left_clean or not right_clean:
        return 0.0
    if left_clean == right_clean:
        return 1.0

    left_tokens = normalized_title_tokens(left_clean)
    right_tokens = normalized_title_tokens(right_clean)
    union = left_tokens | right_tokens
    intersection = left_tokens & right_tokens
    token_score = len(intersection) / len(union) if union else 0.0
    shorter_size = min(len(left_tokens), len(right_tokens))
    containment_score = (
        len(intersection) / shorter_size if shorter_size >= 6 else 0.0
    )
    sequence_score = SequenceMatcher(None, left_clean, right_clean).ratio()
    return max(token_score, containment_score, sequence_score)


def strip_html(value: str) -> str:
    if not value:
        return ""
    return clean_text(BeautifulSoup(value, "html.parser").get_text(" ", strip=True))


def chinese_weekday(value: datetime) -> str:
    weekday_map = {
        "Monday": "周一",
        "Tuesday": "周二",
        "Wednesday": "周三",
        "Thursday": "周四",
        "Friday": "周五",
        "Saturday": "周六",
        "Sunday": "周日",
    }
    return weekday_map[value.strftime("%A")]


class DailyBriefing:
    """每日早报生成器。"""

    def __init__(
        self,
        config_path: str = "config.yaml",
        dry_run: bool = False,
        history_enabled: Optional[bool] = None,
    ):
        self.config_path = Path(config_path)
        self.config = self._load_config(self.config_path)
        self.dry_run = dry_run
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": self.config["request"]["user_agent"]}
        )
        self.source_health: List[Dict[str, Any]] = []
        history_config = self.config.get("history", {})
        configured_history = bool(history_config.get("enabled", True)) and not dry_run
        self.history_enabled = (
            configured_history if history_enabled is None else bool(history_enabled)
        )
        self.history_store: Optional[BriefingStore] = None
        if self.history_enabled:
            database = Path(
                history_config.get("database", "data/briefing_history.sqlite3")
            )
            if not database.is_absolute():
                database = self.config_path.parent / database
            self.history_store = BriefingStore(str(database))

    def _load_config(self, config_path: Path) -> Dict[str, Any]:
        config = deepcopy(DEFAULT_CONFIG)
        if not config_path.exists():
            return config

        with config_path.open("r", encoding="utf-8") as file:
            loaded = yaml.safe_load(file) or {}

        if not isinstance(loaded, dict):
            raise ValueError(f"配置文件格式不正确: {config_path}")

        return deep_merge(config, loaded)

    def _limit(self, key: str) -> int:
        return int(self.config.get("limits", {}).get(key, DEFAULT_CONFIG["limits"][key]))

    def _get_soup(self, url: str) -> BeautifulSoup:
        response = self.session.get(
            url,
            timeout=int(self.config.get("request", {}).get("timeout", 25)),
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        return BeautifulSoup(response.text, "html.parser")

    def _get_content(self, url: str) -> bytes:
        response = self.session.get(
            url,
            timeout=int(self.config.get("request", {}).get("timeout", 25)),
        )
        response.raise_for_status()
        return response.content

    def _get_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        response = self.session.get(
            url,
            params=params,
            timeout=int(self.config.get("request", {}).get("timeout", 25)),
        )
        response.raise_for_status()
        return response.json()

    def _record_source_health(
        self,
        source: str,
        started_at: float,
        item_count: int,
        error: str = "",
    ) -> None:
        self.source_health.append(
            {
                "source": source,
                "status": "error" if error else "ok",
                "item_count": item_count,
                "error": clean_text(error),
                "latency_ms": round((monotonic() - started_at) * 1000),
            }
        )

    def _parse_feed_articles(
        self,
        content: Any,
        source: str,
        limit: int,
    ) -> List[Dict[str, str]]:
        root = ElementTree.fromstring(content)
        entries = [
            element
            for element in root.iter()
            if element.tag.rsplit("}", 1)[-1].lower() in {"item", "entry"}
        ]
        max_age_days = int(
            self.config.get("quality", {}).get("max_feed_age_days", 10)
        )
        articles: List[Dict[str, str]] = []

        for entry in entries:
            children = list(entry)

            def child_text(*names: str) -> str:
                wanted = set(names)
                for child in children:
                    tag = child.tag.rsplit("}", 1)[-1].lower()
                    if tag in wanted and child.text:
                        return clean_text(child.text)
                return ""

            title = child_text("title")
            if not title:
                continue

            link = ""
            for child in children:
                if child.tag.rsplit("}", 1)[-1].lower() != "link":
                    continue
                relation = child.attrib.get("rel", "alternate")
                if relation not in {"", "alternate"}:
                    continue
                link = clean_text(child.attrib.get("href", "") or child.text or "")
                if link:
                    break
            if not link:
                link = child_text("guid", "id")
            if not link.startswith(("http://", "https://")):
                continue

            published_raw = child_text("pubdate", "published", "updated", "date")
            published_at = self._parse_feed_datetime(published_raw)
            if published_at and max_age_days > 0:
                age_seconds = (
                    datetime.now(timezone.utc) - published_at.astimezone(timezone.utc)
                ).total_seconds()
                if age_seconds > max_age_days * 86400:
                    continue

            summary = strip_html(child_text("description", "summary", "content", "encoded"))
            articles.append(
                {
                    "title": strip_html(title),
                    "url": link,
                    "time": published_at.strftime("%Y-%m-%d")
                    if published_at
                    else (published_raw or "N/A"),
                    "published_at": published_at.isoformat() if published_at else "",
                    "source": source,
                    "summary": summary,
                }
            )
            if len(articles) >= limit:
                break

        return articles

    def _parse_feed_datetime(self, value: str) -> Optional[datetime]:
        value = clean_text(value)
        if not value:
            return None
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    def _fetch_feed_articles(
        self,
        source_config: Dict[str, str],
        limit: int,
    ) -> List[Dict[str, str]]:
        source = clean_text(source_config.get("name", "官方源"))
        url = clean_text(source_config.get("url", ""))
        if not url:
            return []
        started_at = monotonic()
        try:
            articles = self._parse_feed_articles(
                self._get_content(url),
                source,
                limit,
            )
            self._log(f"获取到 {len(articles)} 条 {source} 官方更新")
            self._record_source_health(source, started_at, len(articles))
            return articles
        except Exception as exc:
            self._log(f"抓取 {source} 官方更新失败: {exc}")
            self._record_source_health(source, started_at, 0, str(exc))
            return []

    def _official_ai_source_names(self) -> set[str]:
        sources = self.config.get("sources", {}).get("ai_official", [])
        if not isinstance(sources, list):
            return set()
        return {
            clean_text(source.get("name", ""))
            for source in sources
            if isinstance(source, dict) and source.get("name")
        }

    def _is_ai_relevant(self, item: Dict[str, str]) -> bool:
        if clean_text(item.get("source", "")) in self._official_ai_source_names():
            return True
        text = " ".join(
            [
                item_title(item),
                clean_text(item.get("summary", "")),
            ]
        ).lower()
        ai_keywords = (
            "ai",
            "artificial intelligence",
            "agent",
            "chatbot",
            "machine learning",
            "llm",
            "model",
            "openai",
            "chatgpt",
            "anthropic",
            "claude",
            "google deepmind",
            "gemini",
            "mistral",
            "xai",
            "grok",
            "ollama",
            "lovable",
            "nvidia",
            "robot",
            "deepfake",
            "copilot",
            "sora",
            "生成式",
            "人工智能",
            "大模型",
            "智能体",
        )
        return has_any_keyword(text, ai_keywords)

    def _round_robin(
        self,
        groups: List[List[Dict[str, str]]],
        limit: int,
    ) -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        positions = [0 for _ in groups]
        while len(rows) < limit:
            added = False
            for index, group in enumerate(groups):
                position = positions[index]
                if position >= len(group):
                    continue
                rows.append(group[position])
                positions[index] += 1
                added = True
                if len(rows) >= limit:
                    break
            if not added:
                break
        return rows

    def _items_duplicate(
        self,
        left: Dict[str, Any],
        right: Dict[str, Any],
    ) -> bool:
        left_url = canonical_url(left.get("url", ""))
        right_url = canonical_url(right.get("url", ""))
        if left_url and left_url == right_url:
            return True

        left_tokens = normalized_title_tokens(item_title(left))
        right_tokens = normalized_title_tokens(item_title(right))
        min_tokens = int(
            self.config.get("quality", {}).get("min_similarity_tokens", 4)
        )
        if min(len(left_tokens), len(right_tokens)) < min_tokens:
            return False
        threshold = float(
            self.config.get("quality", {}).get("similarity_threshold", 0.76)
        )
        return title_similarity(item_title(left), item_title(right)) >= threshold

    def _merge_news_items(
        self,
        primary: Dict[str, Any],
        duplicate: Dict[str, Any],
    ) -> Dict[str, Any]:
        merged = dict(primary)
        sources: List[str] = []
        for value in (primary.get("source", ""), duplicate.get("source", "")):
            for source in clean_text(value).split(" / "):
                if source and source not in sources:
                    sources.append(source)
        merged["source"] = " / ".join(sources)
        if not clean_text(merged.get("summary", "")):
            merged["summary"] = clean_text(duplicate.get("summary", ""))

        related_links = list(primary.get("related_links", []))
        duplicate_url = clean_text(duplicate.get("url", ""))
        if duplicate_url and canonical_url(duplicate_url) != canonical_url(primary.get("url", "")):
            related = {
                "source": clean_text(duplicate.get("source", "")),
                "url": duplicate_url,
            }
            if related not in related_links:
                related_links.append(related)
        if related_links:
            merged["related_links"] = related_links
        return merged

    def _dedupe_items(self, rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
        deduped: List[Dict[str, Any]] = []
        for row in rows:
            match_index = next(
                (
                    index
                    for index, existing in enumerate(deduped)
                    if self._items_duplicate(existing, row)
                ),
                None,
            )
            if match_index is None:
                deduped.append(dict(row))
            else:
                deduped[match_index] = self._merge_news_items(
                    deduped[match_index],
                    row,
                )
        return deduped

    def _section_fit_score(self, item: Dict[str, Any], section: str) -> int:
        text = " ".join(
            [
                item_title(item),
                clean_text(item.get("summary", "")),
                clean_text(item.get("source", "")),
            ]
        ).lower()
        keywords = {
            "ai": (
                "ai",
                "artificial intelligence",
                "agent",
                "llm",
                "model",
                "openai",
                "anthropic",
                "claude",
                "gemini",
                "grok",
                "ollama",
                "robot",
                "deepfake",
            ),
            "web3": (
                "web3",
                "crypto",
                "bitcoin",
                "ethereum",
                "blockchain",
                "token",
                "defi",
                "aave",
                "solana",
                "xrp",
                "on-chain",
            ),
            "venture": (
                "funding",
                "raises",
                "raised",
                "fund",
                "venture",
                "valuation",
                "investor",
                "investment",
                "acquisition",
                "revenue",
                "ipo",
            ),
        }
        score = sum(2 for keyword in keywords.get(section, ()) if keyword_in_text(text, keyword))
        source = clean_text(item.get("source", "")).lower()
        if section == "web3" and "coindesk" in source:
            score += 3
        if section == "ai" and any(
            name.lower() in source for name in self._official_ai_source_names()
        ):
            score += 3
        return score

    def _dedupe_news_sections(
        self,
        ai_news: List[Dict[str, str]],
        web3_news: List[Dict[str, str]],
        venture_news: List[Dict[str, str]],
    ) -> Dict[str, List[Dict[str, str]]]:
        entries: List[Dict[str, Any]] = []
        for section, rows in (
            ("ai", ai_news),
            ("web3", web3_news),
            ("venture", venture_news),
        ):
            for row in rows:
                match_index = next(
                    (
                        index
                        for index, existing in enumerate(entries)
                        if self._items_duplicate(existing["item"], row)
                    ),
                    None,
                )
                if match_index is None:
                    entries.append({"section": section, "item": dict(row)})
                    continue

                existing = entries[match_index]
                existing_score = self._section_fit_score(
                    existing["item"], existing["section"]
                )
                candidate_score = self._section_fit_score(row, section)
                if candidate_score > existing_score:
                    entries[match_index] = {
                        "section": section,
                        "item": self._merge_news_items(row, existing["item"]),
                    }
                else:
                    existing["item"] = self._merge_news_items(existing["item"], row)

        result: Dict[str, List[Dict[str, str]]] = {
            "ai": [],
            "web3": [],
            "venture": [],
        }
        for entry in entries:
            result[entry["section"]].append(entry["item"])
        return result

    def _log(self, message: str) -> None:
        print(message, file=sys.stderr)

    def _sample(self, key: str, limit: int) -> List[Dict[str, str]]:
        return deepcopy(SAMPLE_DATA[key][:limit])

    def _collect_articles(
        self,
        soup: BeautifulSoup,
        base_url: str,
        source: str,
        limit: int,
        link_selectors: List[str],
    ) -> List[Dict[str, str]]:
        articles: List[Dict[str, str]] = []
        seen_titles = set()
        cards = soup.select("article")
        if not cards:
            cards = soup.select("div[class*='post'], div[class*='card'], div[class*='story']")

        for card in cards:
            link = None
            for selector in link_selectors:
                link = card.select_one(selector)
                if link and link.get("href"):
                    break

            if not link or not link.get("href"):
                continue

            title = clean_text(link.get_text(" ", strip=True))
            if len(title) < 12:
                continue

            key = title.lower()
            if key in seen_titles:
                continue

            time_elem = card.select_one("time")
            summary_elem = card.select_one("p")
            articles.append(
                {
                    "title": title,
                    "url": urljoin(base_url, link.get("href", "")),
                    "time": clean_text(time_elem.get_text(" ", strip=True))
                    if time_elem
                    else "N/A",
                    "source": source,
                    "summary": clean_text(summary_elem.get_text(" ", strip=True))
                    if summary_elem
                    else "",
                }
            )
            seen_titles.add(key)
            if len(articles) >= limit:
                return articles

        return self._fallback_article_links(soup, base_url, source, limit, seen_titles, articles)

    def _fallback_article_links(
        self,
        soup: BeautifulSoup,
        base_url: str,
        source: str,
        limit: int,
        seen_titles: set,
        articles: List[Dict[str, str]],
    ) -> List[Dict[str, str]]:
        blocked_fragments = (
            "/author/",
            "/category/",
            "/tag/",
            "/about",
            "/contact",
            "/privacy",
            "/terms",
            "#",
        )
        for link in soup.select("a[href]"):
            href = link.get("href", "")
            if any(fragment in href for fragment in blocked_fragments):
                continue

            title = clean_text(link.get_text(" ", strip=True))
            if len(title) < 18:
                continue

            key = title.lower()
            if key in seen_titles:
                continue

            articles.append(
                {
                    "title": title,
                    "url": urljoin(base_url, href),
                    "time": "N/A",
                    "source": source,
                    "summary": "",
                }
            )
            seen_titles.add(key)
            if len(articles) >= limit:
                break

        return articles

    def fetch_ai_news(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """抓取 AI 热点新闻。"""
        limit = limit or self._limit("ai_news")
        self._log("正在抓取 AI 热点...")
        if self.dry_run:
            return self._sample("ai_news", limit)

        url = self.config["sources"]["ai_news"]
        media_articles: List[Dict[str, str]] = []
        started_at = monotonic()
        try:
            soup = self._get_soup(url)
            candidates = self._collect_articles(
                soup,
                url,
                "TechCrunch",
                max(limit * 2, limit),
                ["h2 a", "h3 a", "a.loop-card__title-link", "a.post-block__title__link"],
            )
            relevant_candidates = [
                article for article in candidates if self._is_ai_relevant(article)
            ]
            media_articles = relevant_candidates[:limit]
            filtered_count = len(candidates) - len(relevant_candidates)
            if filtered_count > 0:
                self._log(f"已过滤 {filtered_count} 条非 AI 内容")
            self._log(f"获取到 {len(media_articles)} 条 TechCrunch AI 新闻")
            self._record_source_health(
                "TechCrunch AI", started_at, len(media_articles)
            )
        except Exception as exc:
            self._log(f"抓取 AI 新闻失败: {exc}")
            self._record_source_health("TechCrunch AI", started_at, 0, str(exc))

        official_groups: List[List[Dict[str, str]]] = []
        official_sources = self.config.get("sources", {}).get("ai_official", [])
        official_limit = self._limit("ai_official_per_source")
        if isinstance(official_sources, list) and official_limit > 0:
            for source_config in official_sources:
                if not isinstance(source_config, dict):
                    continue
                official_groups.append(
                    self._fetch_feed_articles(source_config, official_limit)
                )

        official_articles = self._round_robin(
            official_groups,
            sum(len(group) for group in official_groups),
        )
        combined = self._round_robin(
            [media_articles, official_articles],
            limit * 2,
        )
        articles = self._dedupe_items(combined)[:limit]
        source_names = {
            source
            for item in articles
            for source in clean_text(item.get("source", "")).split(" / ")
            if source
        }
        self._log(
            f"AI 板块最终保留 {len(articles)} 条，覆盖 "
            f"{len(source_names)} 个来源"
        )
        return articles

    def _within_max_age(self, value: str) -> bool:
        published_at = self._parse_feed_datetime(value)
        max_age_days = int(
            self.config.get("quality", {}).get("max_feed_age_days", 10)
        )
        if published_at is None or max_age_days <= 0:
            return True
        age = datetime.now(timezone.utc) - published_at.astimezone(timezone.utc)
        return age.total_seconds() <= max_age_days * 86400

    def fetch_hacker_news(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch fresh AI discussions through the official HN Algolia API."""
        limit = limit or self._limit("hacker_news")
        if limit <= 0:
            return []
        source_config = self.config.get("sources", {}).get("hacker_news", {})
        if not isinstance(source_config, dict):
            return []
        url = clean_text(source_config.get("url", ""))
        queries = source_config.get("queries", ["AI agent", "LLM"])
        lookback_hours = int(source_config.get("lookback_hours", 96))
        min_points = int(source_config.get("min_points", 20))
        created_after = int(
            (datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).timestamp()
        )
        rows: List[Dict[str, Any]] = []
        started_at = monotonic()
        try:
            for query in queries:
                payload = self._get_json(
                    url,
                    {
                        "query": query,
                        "tags": "story",
                        "hitsPerPage": max(limit * 2, 10),
                        "numericFilters": (
                            f"created_at_i>{created_after},points>{min_points}"
                        ),
                    },
                )
                for hit in payload.get("hits", []):
                    title = clean_text(hit.get("title", ""))
                    object_id = clean_text(str(hit.get("objectID", "")))
                    if not title or not object_id:
                        continue
                    rows.append(
                        {
                            "title": title,
                            "url": clean_text(hit.get("url", ""))
                            or f"https://news.ycombinator.com/item?id={object_id}",
                            "time": clean_text(hit.get("created_at", ""))[:10]
                            or "N/A",
                            "published_at": clean_text(hit.get("created_at", "")),
                            "source": "Hacker News",
                            "summary": (
                                f"HN 社区热度 {int(hit.get('points') or 0)} points，"
                                f"{int(hit.get('num_comments') or 0)} 条讨论。"
                            ),
                            "popularity": int(hit.get("points") or 0),
                        }
                    )
            rows = self._dedupe_items(rows)
            rows.sort(key=lambda row: int(row.get("popularity", 0)), reverse=True)
            self._log(f"获取到 {min(len(rows), limit)} 条 Hacker News 信号")
            self._record_source_health(
                "Hacker News", started_at, min(len(rows), limit)
            )
            return rows[:limit]
        except Exception as exc:
            self._log(f"抓取 Hacker News 失败: {exc}")
            self._record_source_health("Hacker News", started_at, 0, str(exc))
            return []

    def fetch_arxiv(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch recent papers from arXiv's public Atom API."""
        limit = limit or self._limit("arxiv")
        if limit <= 0:
            return []
        source_config = self.config.get("sources", {}).get("arxiv", {})
        if not isinstance(source_config, dict):
            return []
        url = clean_text(source_config.get("url", ""))
        query = clean_text(
            source_config.get("query", "cat:cs.AI OR cat:cs.CL OR cat:cs.LG")
        )
        started_at = monotonic()
        try:
            response = self.session.get(
                url,
                params={
                    "search_query": query,
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                    "max_results": limit,
                },
                timeout=int(self.config.get("request", {}).get("timeout", 25)),
            )
            response.raise_for_status()
            rows = self._parse_feed_articles(response.content, "arXiv", limit)
            for row in rows:
                row["summary"] = short_title(row.get("summary", ""), 420)
            self._log(f"获取到 {len(rows)} 篇 arXiv 论文")
            self._record_source_health("arXiv", started_at, len(rows))
            return rows
        except Exception as exc:
            self._log(f"抓取 arXiv 失败: {exc}")
            self._record_source_health("arXiv", started_at, 0, str(exc))
            return []

    def fetch_huggingface_models(
        self,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch models ranked by Hugging Face's current trending score."""
        limit = limit or self._limit("huggingface_models")
        if limit <= 0:
            return []
        url = clean_text(
            self.config.get("sources", {}).get("huggingface_models", "")
        )
        started_at = monotonic()
        try:
            payload = self._get_json(
                url,
                {"sort": "trendingScore", "direction": -1, "limit": limit},
            )
            rows: List[Dict[str, Any]] = []
            for model in payload:
                model_id = clean_text(model.get("id", ""))
                if not model_id:
                    continue
                pipeline = clean_text(model.get("pipeline_tag", "")) or "未标注任务"
                rows.append(
                    {
                        "title": model_id,
                        "url": f"https://huggingface.co/{model_id}",
                        "time": clean_text(model.get("createdAt", ""))[:10] or "N/A",
                        "published_at": clean_text(model.get("createdAt", "")),
                        "source": "Hugging Face Trending",
                        "summary": (
                            f"Hugging Face 热门模型，任务类型 {pipeline}，"
                            f"当前 {int(model.get('likes') or 0)} likes。"
                        ),
                        "popularity": int(model.get("trendingScore") or 0),
                    }
                )
            self._log(f"获取到 {len(rows)} 个 Hugging Face 热门模型")
            self._record_source_health(
                "Hugging Face Trending", started_at, len(rows)
            )
            return rows
        except Exception as exc:
            self._log(f"抓取 Hugging Face 热门模型失败: {exc}")
            self._record_source_health(
                "Hugging Face Trending", started_at, 0, str(exc)
            )
            return []

    def fetch_aihot(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Read AI HOT's server-rendered selected feed; its old public API is gone."""
        limit = limit or self._limit("aihot")
        if limit <= 0:
            return []
        url = clean_text(self.config.get("sources", {}).get("aihot", ""))
        started_at = monotonic()
        try:
            soup = self._get_soup(url)
            rows: List[Dict[str, Any]] = []
            for card in soup.select("article"):
                heading = card.select_one("h3")
                if heading is None:
                    continue
                title = clean_text(heading.get_text(" ", strip=True))
                if len(title) < 8:
                    continue
                summary_element = card.select_one("p")
                image = card.select_one("img[alt]")
                origin = clean_text(image.get("alt", "")) if image else "精选源"
                summary = (
                    clean_text(summary_element.get_text(" ", strip=True))
                    if summary_element
                    else ""
                )
                rows.append(
                    {
                        "title": title,
                        "url": f"{url}?item={quote(title)}",
                        "time": "今日",
                        "source": f"AI HOT · {origin}",
                        "origin_source": origin,
                        "summary": summary,
                    }
                )
                if len(rows) >= limit:
                    break
            self._log(f"获取到 {len(rows)} 条 AI HOT 精选")
            self._record_source_health("AI HOT", started_at, len(rows))
            return rows
        except Exception as exc:
            self._log(f"抓取 AI HOT 失败: {exc}")
            self._record_source_health("AI HOT", started_at, 0, str(exc))
            return []

    def fetch_official_sitemaps(
        self,
        limit_per_source: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Use official sitemaps as a fallback for companies without a stable feed."""
        limit_per_source = limit_per_source or self._limit(
            "official_sitemaps_per_source"
        )
        groups: List[List[Dict[str, Any]]] = []
        for source_config in self.config.get("sources", {}).get(
            "official_sitemaps", []
        ):
            if not isinstance(source_config, dict):
                continue
            name = clean_text(source_config.get("name", "官方站点"))
            url = clean_text(source_config.get("url", ""))
            include = source_config.get("include", [])
            rows: List[Dict[str, Any]] = []
            started_at = monotonic()
            try:
                root = ElementTree.fromstring(self._get_content(url))
                for entry in root.iter():
                    if entry.tag.rsplit("}", 1)[-1].lower() != "url":
                        continue
                    fields = {
                        child.tag.rsplit("}", 1)[-1].lower(): clean_text(
                            child.text or ""
                        )
                        for child in list(entry)
                    }
                    link = fields.get("loc", "")
                    lastmod = fields.get("lastmod", "")
                    if not link or (include and not any(part in link for part in include)):
                        continue
                    if lastmod and not self._within_max_age(lastmod):
                        continue
                    slug = unquote(urlsplit(link).path.rstrip("/").split("/")[-1])
                    title = clean_text(slug.replace("-", " "))
                    if not title:
                        continue
                    published = self._parse_feed_datetime(lastmod)
                    rows.append(
                        {
                            "title": title,
                            "url": link,
                            "time": published.strftime("%Y-%m-%d")
                            if published
                            else "N/A",
                            "published_at": published.isoformat() if published else "",
                            "source": name,
                            "summary": f"{name} 官方网站近期更新。",
                            "official": True,
                        }
                    )
                    if len(rows) >= limit_per_source:
                        break
                self._log(f"获取到 {len(rows)} 条 {name} sitemap 更新")
                self._record_source_health(
                    f"{name} Sitemap", started_at, len(rows)
                )
            except Exception as exc:
                self._log(f"抓取 {name} sitemap 失败: {exc}")
                self._record_source_health(
                    f"{name} Sitemap", started_at, 0, str(exc)
                )
            groups.append(rows)
        return self._round_robin(groups, sum(len(group) for group in groups))

    def fetch_github_releases(self) -> List[Dict[str, Any]]:
        """Track releases from the AI tools Rion actually uses."""
        per_repo = self._limit("github_releases_per_repo")
        rows: List[Dict[str, Any]] = []
        for repo in self.config.get("sources", {}).get("github_releases", []):
            repo = clean_text(str(repo))
            if not repo:
                continue
            started_at = monotonic()
            repo_count = 0
            try:
                payload = self._get_json(
                    f"https://api.github.com/repos/{repo}/releases",
                    {"per_page": max(per_repo * 3, 3)},
                )
                kept = 0
                for release in payload:
                    if release.get("draft") or release.get("prerelease"):
                        continue
                    published_at = clean_text(release.get("published_at", ""))
                    if published_at and not self._within_max_age(published_at):
                        continue
                    name = clean_text(
                        release.get("name", "") or release.get("tag_name", "")
                    )
                    rows.append(
                        {
                            "title": f"{repo} 发布 {name}",
                            "url": clean_text(release.get("html_url", "")),
                            "time": published_at[:10] or "N/A",
                            "published_at": published_at,
                            "source": f"GitHub Release · {repo}",
                            "summary": short_title(
                                clean_text(release.get("body", "")), 420
                            ),
                            "official": True,
                        }
                    )
                    kept += 1
                    repo_count += 1
                    if kept >= per_repo:
                        break
                self._record_source_health(
                    f"GitHub Release · {repo}", started_at, repo_count
                )
            except Exception as exc:
                self._log(f"抓取 {repo} Release 失败: {exc}")
                self._record_source_health(
                    f"GitHub Release · {repo}", started_at, 0, str(exc)
                )
        self._log(f"获取到 {len(rows)} 条 GitHub Release 更新")
        return rows

    def fetch_ecosystem_signals(self) -> List[Dict[str, Any]]:
        """Build a diverse candidate pool from community, research and official sources."""
        limit = self._limit("ecosystem_signals")
        if self.dry_run:
            return self._sample("ecosystem_signals", limit)
        groups = [
            self.fetch_hacker_news(),
            self.fetch_arxiv(),
            self.fetch_huggingface_models(),
            self.fetch_aihot(),
            self.fetch_official_sitemaps(),
            self.fetch_github_releases(),
        ]
        rows = self._round_robin(groups, sum(len(group) for group in groups))
        return self._dedupe_items(rows)[:limit]

    def fetch_web3_news(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """抓取 Web3 热点新闻。"""
        limit = limit or self._limit("web3_news")
        self._log("正在抓取 Web3 热点...")
        if self.dry_run:
            return self._sample("web3_news", limit)

        url = self.config["sources"]["web3_news"]
        started_at = monotonic()
        try:
            soup = self._get_soup(url)
            articles = self._collect_coindesk_articles(soup, url, limit)
            for article in articles:
                article.setdefault("sentiment", "Neutral")
            self._log(f"获取到 {len(articles)} 条 Web3 新闻")
            self._record_source_health("CoinDesk", started_at, len(articles))
            return articles
        except Exception as exc:
            self._log(f"抓取 Web3 新闻失败: {exc}")
            self._record_source_health("CoinDesk", started_at, 0, str(exc))
            return []

    def _collect_coindesk_articles(
        self,
        soup: BeautifulSoup,
        base_url: str,
        limit: int,
    ) -> List[Dict[str, str]]:
        article_path = re.compile(
            r"/(business|markets|policy|tech|daybook-us)/\d{4}/\d{2}/\d{2}/"
        )
        blocked_fragments = ("/press-release/", "/sponsored-content/")
        candidates: Dict[str, Dict[str, str]] = {}
        order: List[str] = []

        for link in soup.select("a[href]"):
            href = link.get("href", "")
            if any(fragment in href for fragment in blocked_fragments):
                continue
            if not article_path.search(href):
                continue

            title = clean_text(link.get_text(" ", strip=True))
            if len(title) < 20:
                continue

            full_url = urljoin(base_url, href)
            item = {
                "title": title,
                "url": full_url,
                "time": "N/A",
                "source": "CoinDesk",
                "summary": "",
            }

            if full_url not in candidates:
                order.append(full_url)
                candidates[full_url] = item
            elif len(title) < len(candidates[full_url]["title"]):
                candidates[full_url] = item

        return [candidates[url] for url in order][:limit]

    def fetch_venture_news(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """抓取投资和融资新闻。"""
        limit = limit or self._limit("venture_news")
        self._log("正在抓取投资经济新闻...")
        if self.dry_run:
            return self._sample("venture_news", limit)

        url = self.config["sources"]["venture_news"]
        started_at = monotonic()
        try:
            soup = self._get_soup(url)
            articles = self._collect_articles(
                soup,
                url,
                "TechCrunch",
                limit,
                ["h2 a", "h3 a", "a.loop-card__title-link", "a.post-block__title__link"],
            )
            self._log(f"获取到 {len(articles)} 条投资新闻")
            self._record_source_health(
                "TechCrunch Venture", started_at, len(articles)
            )
            return articles
        except Exception as exc:
            self._log(f"抓取投资新闻失败: {exc}")
            self._record_source_health(
                "TechCrunch Venture", started_at, 0, str(exc)
            )
            return []

    def fetch_github_trending(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """抓取 GitHub Trending 项目。"""
        limit = limit or self._limit("github_projects")
        self._log("正在抓取 GitHub Trending...")
        if self.dry_run:
            return self._sample("github_projects", limit)

        url = self.config["sources"]["github_trending"]
        started_at = monotonic()
        try:
            soup = self._get_soup(url)
            projects: List[Dict[str, str]] = []
            items = soup.select("article.Box-row")[:limit]

            for item in items:
                repo_elem = item.select_one("h2 a")
                if not repo_elem:
                    continue

                repo_name = clean_text(repo_elem.get_text(" ", strip=True))
                repo_name = repo_name.replace(" / ", "/").replace(" ", "")
                desc_elem = item.select_one("p")
                lang_elem = item.select_one('[itemprop="programmingLanguage"]')
                stars_elem = item.select_one('a[href*="/stargazers"]')
                today_elem = item.select_one("span.d-inline-block.float-sm-right")

                projects.append(
                    {
                        "name": repo_name,
                        "description": clean_text(desc_elem.get_text(" ", strip=True))
                        if desc_elem
                        else "",
                        "language": clean_text(lang_elem.get_text(" ", strip=True))
                        if lang_elem
                        else "Unknown",
                        "stars": clean_text(stars_elem.get_text(" ", strip=True))
                        if stars_elem
                        else "0",
                        "today_stars": clean_text(today_elem.get_text(" ", strip=True))
                        if today_elem
                        else "",
                        "url": f"https://github.com/{repo_name}",
                    }
                )

            self._log(f"获取到 {len(projects)} 个 GitHub 项目")
            self._record_source_health(
                "GitHub Trending", started_at, len(projects)
            )
            return projects
        except Exception as exc:
            self._log(f"抓取 GitHub Trending 失败: {exc}")
            self._record_source_health(
                "GitHub Trending", started_at, 0, str(exc)
            )
            return []

    def generate_topics(
        self,
        ai_news: List[Dict[str, str]],
        web3_news: List[Dict[str, str]],
        venture_news: List[Dict[str, str]],
        github_projects: List[Dict[str, str]],
    ) -> List[str]:
        """生成适合中文 AI/Web3 自媒体的选题素材。"""
        topics: List[str] = []

        if ai_news:
            topics.append(
                f"「{short_title(ai_news[0]['title'])}」：适合拆成 AI 工具链/行业趋势解读"
            )
        if github_projects:
            topics.append(
                f"「开源项目观察」{github_projects[0]['name']} 为什么今天值得看"
            )
        if web3_news:
            topics.append(
                f"「Web3 情绪温度计」从 {short_title(web3_news[0]['title'], 24)} 看市场叙事"
            )
        if venture_news:
            topics.append(
                f"「融资风向」{short_title(venture_news[0]['title'], 24)} 背后的 B 端机会"
            )

        topics.extend(
            [
                "「今日 AI/Web3 信息差」把新闻整理成 3 个普通人能用的机会",
                "「工具测评选题」从 GitHub Trending 挑一个项目做上手体验",
                "「商业化观察」今天哪些热点能转成商单、咨询或产品 demo",
            ]
        )
        return topics[: self._limit("topics")]

    def enrich_items(
        self,
        ai_news: List[Dict[str, str]],
        web3_news: List[Dict[str, str]],
        venture_news: List[Dict[str, str]],
        github_projects: List[Dict[str, str]],
    ) -> None:
        for item in ai_news:
            self._enrich_news_item(item, "ai")
        for item in web3_news:
            self._enrich_news_item(item, "web3")
        for item in venture_news:
            self._enrich_news_item(item, "venture")
        for item in github_projects:
            self._enrich_project_item(item)

    def _enrich_news_item(self, item: Dict[str, str], section: str) -> None:
        item["summary_cn"] = self._summarize_news_cn(item, section)
        item["category"] = self._classify_news_item(item, section)
        item["tags"] = self._tag_item(item, section)
        item["score"] = self._score_item(item, section)
        self._apply_personalization(item, section)
        self._apply_dimension_scores(item, section)
        item["item_key"] = canonical_url(item.get("url", "")) or (
            f"{section}:{item_title(item).lower()}"
        )

    def _enrich_project_item(self, project: Dict[str, str]) -> None:
        project["summary_cn"] = self._summarize_project_cn(project)
        project["category"] = self._classify_project_item(project)
        project["tags"] = self._tag_item(project, "github")
        project["score"] = self._score_item(project, "github")
        self._apply_personalization(project, "github")
        self._apply_dimension_scores(project, "github")
        project["item_key"] = canonical_url(project.get("url", "")) or (
            f"github:{item_title(project).lower()}"
        )

    def _classify_news_item(self, item: Dict[str, str], section: str) -> str:
        title = item_title(item).lower()
        summary = clean_text(item.get("summary", "")).lower()
        text = f"{title} {summary}"

        if section == "web3":
            if has_any_keyword(text, ("regulation", "rules", "eu", "uk", "mica", "treasury", "sanction")):
                return "政策监管"
            if has_any_keyword(text, ("bitcoin", "btc", "xrp", "ether", "solana", "token", "market")):
                return "市场动态"
            return "Web3 叙事"

        if section == "venture":
            if has_any_keyword(text, ("ipo", "trading", "public", "上市")):
                return "资本市场"
            if has_any_keyword(text, ("fund", "funding", "vc", "venture", "backs", "stake", "融资", "资本")):
                return "融资并购"
            return "商业化"

        rules = [
            (("agent", "agents", "agentic", "codex", "claude code", "智能体", "多智能体"), "Agent / AI 编码"),
            (("browser", "browsers", "chrome", "safari", "search", "搜索"), "产品发布/更新"),
            (("chip", "chips", "gpu", "gpus", "nvidia", "samsung", "inference", "on-device", "edge ai", "edge-ai", "芯片", "端侧", "推理"), "算力与硬件"),
            (("openai", "anthropic", "microsoft", "google", "meta"), "公司与模型"),
            (("paper", "research", "study", "benchmark", "glossary", "研究", "论文"), "论文研究/知识"),
            (("ipo", "funding", "series", "unicorn", "venture", "融资"), "行业动态"),
            (("game", "gaming", "video", "office", "productivity", "办公", "视频"), "产品发布/更新"),
        ]
        for keywords, category in rules:
            if has_any_keyword(text, keywords):
                return category
        return "AI 行业动态"

    def _classify_project_item(self, project: Dict[str, str]) -> str:
        text = f"{item_title(project)} {project.get('description', '')}".lower()
        rules = [
            (("codex", "claude", "agent", "agents", "mcp", "智能体"), "Agent / AI 编码"),
            (("browser", "devtools", "page", "gui", "浏览器"), "产品发布/更新"),
            (("security", "pentest", "penetration", "vulnerability", "vulnerabilities", "vulnerab*", "安全"), "AI 安全"),
            (("meeting", "transcription", "whisper", "ollama", "会议", "转写"), "办公自动化"),
            (("prompt", "system prompt", "system_prompts", "提示词"), "技巧与观点"),
            (("book", "course", "learning", "machine learning", "学习", "教程"), "学习资源"),
            (("web3", "crypto", "blockchain", "on-chain", "chain", "indexer", "链上"), "Web3 工具"),
        ]
        for keywords, category in rules:
            if has_any_keyword(text, keywords):
                return category
        return "开源生态"

    def _tag_item(self, item: Dict[str, str], section: str) -> List[str]:
        text = f"{item_title(item)} {item.get('summary', '')} {item.get('description', '')}".lower()
        rules = [
            ("Mistral", ("mistral",)),
            ("OpenAI", ("openai", "chatgpt", "sora", "codex")),
            ("Anthropic", ("anthropic", "claude")),
            ("Google", ("google", "gemini", "deepmind")),
            ("Meta", ("meta", "llama", "zuckerberg")),
            ("Microsoft", ("microsoft", "copilot")),
            ("Agent", ("agent", "agents", "agentic", "mcp", "智能体", "多智能体")),
            ("AI 编码", ("codex", "claude code", "coding", "devtools", "swe-bench")),
            ("浏览器", ("browser", "chrome", "safari", "浏览器")),
            ("开源生态", ("github", "open-source", "open source", "repo")),
            ("安全", ("security", "vulnerability", "vulnerabilities", "vulnerab*", "pentest", "attack", "ransom", "安全")),
            ("视频/多模态", ("video", "multimodal", "image", "vision", "视频", "多模态")),
            ("端侧/硬件", ("chip", "chips", "gpu", "gpus", "nvidia", "samsung", "on-device", "edge ai", "edge-ai", "芯片", "端侧")),
            ("办公效率", ("office", "productivity", "meeting", "transcription", "办公", "会议")),
            ("融资/IPO", ("fund", "funding", "ipo", "venture", "unicorn", "vc", "融资", "资本")),
            ("监管", ("regulation", "regulatory", "mica", "treasury", "sanction", "compliance", "监管")),
            ("Web3", ("web3", "crypto", "bitcoin", "btc", "xrp", "solana", "blockchain", "on-chain", "链上")),
            ("RWA", ("tokenized", "blackrock", "etf", "stock")),
        ]
        tags = [label for label, keywords in rules if has_any_keyword(text, keywords)]
        if section == "web3" and "Web3" not in tags:
            tags.insert(0, "Web3")
        if section == "github" and "开源生态" not in tags:
            tags.insert(0, "开源生态")
        if section == "venture" and "融资/IPO" not in tags:
            tags.insert(0, "融资/IPO")
        if not tags:
            tags.append("AI")
        return tags[:4]

    def _score_item(self, item: Dict[str, str], section: str) -> int:
        text = f"{item_title(item)} {item.get('summary', '')} {item.get('description', '')}".lower()
        score = 50
        score += {
            "ai": 8,
            "github": 10,
            "web3": 6,
            "venture": 5,
        }.get(section, 0)
        high_signal = [
            "openai",
            "anthropic",
            "microsoft",
            "google",
            "meta",
            "agent",
            "codex",
            "claude",
            "browser",
            "security",
            "regulation",
            "ipo",
            "fund",
            "chip",
            "nvidia",
            "web3",
            "bitcoin",
            "xrp",
            "智能体",
            "多智能体",
            "链上",
            "融资",
            "芯片",
        ]
        score += sum(5 for keyword in high_signal if keyword_in_text(text, keyword))
        if item.get("summary_cn"):
            score += 4
        if section == "github":
            today = item.get("today_stars", "")
            match = re.search(r"([\d,]+)", today)
            if match:
                stars_today = int(match.group(1).replace(",", ""))
                if stars_today >= 1000:
                    score += 16
                elif stars_today >= 500:
                    score += 10
                elif stars_today >= 100:
                    score += 5
        return min(score, 100)

    def _apply_personalization(self, item: Dict[str, Any], section: str) -> None:
        personalization = self.config.get("personalization", {})
        if not personalization.get("enabled", True):
            item["personal_relevance"] = min(int(item.get("score", 0)), 94)
            item["rion_score"] = item["personal_relevance"]
            item["rion_reason"] = "按通用热度排序。"
            item["content_value"] = self._content_value_label(int(item["rion_score"]))
            item["matched_signals"] = []
            return

        text = " ".join(
            [
                item_title(item),
                clean_text(item.get("summary", "")),
                clean_text(item.get("description", "")),
                clean_text(item.get("category", "")),
                " ".join(item.get("tags", [])),
            ]
        ).lower()
        baseline = int(personalization.get("baseline", 36))
        section_boosts = personalization.get("section_boosts", {})
        score = baseline + int(section_boosts.get(section, 0))
        score += int(item.get("score", 0)) // 6

        matched: List[Dict[str, Any]] = []
        for signal in personalization.get("signals", []):
            keywords = signal.get("keywords", [])
            if has_any_keyword(text, keywords):
                weight = int(signal.get("weight", 0))
                matched.append(
                    {
                        "label": signal.get("label", "相关信号"),
                        "weight": weight,
                        "reason": signal.get("reason", ""),
                    }
                )

        matched.sort(key=lambda row: int(row.get("weight", 0)), reverse=True)
        signal_bonus = 0
        for index, signal in enumerate(matched[:3]):
            weight = int(signal.get("weight", 0))
            if index == 0:
                signal_bonus += min(weight, 20)
            elif index == 1:
                signal_bonus += min(weight // 2, 9)
            else:
                signal_bonus += min(weight // 3, 5)
        score += min(signal_bonus, 34)
        item["personal_relevance"] = min(score, 96)
        item["rion_score"] = item["personal_relevance"]
        item["matched_signals"] = [row["label"] for row in matched[:3]]
        item["rion_reason"] = self._personalization_reason(matched, section)
        item["content_value"] = self._content_value_label(int(item["rion_score"]))

    def _source_profile(self, item: Dict[str, Any]) -> Dict[str, Any]:
        source = clean_text(item.get("source", ""))
        source_names = {
            name
            for name in source.split(" / ")
            if clean_text(name)
        }
        for related in item.get("related_links", []):
            related_source = clean_text(related.get("source", ""))
            if related_source:
                source_names.add(related_source)
        source_count = max(1, len(source_names))
        official_names = self._official_ai_source_names() | {
            clean_text(row.get("name", ""))
            for row in self.config.get("sources", {}).get("official_sitemaps", [])
            if isinstance(row, dict)
        }
        is_official = bool(item.get("official")) or source == "arXiv"
        is_official = is_official or source.startswith("GitHub Release ·")
        is_official = is_official or any(
            name and name in source_names for name in official_names
        )

        if is_official:
            tier = "官方源"
            verification = "官方确认"
            credibility = 94
        elif source_count >= 2:
            tier = "多源印证"
            verification = "多源印证"
            credibility = min(92, 82 + source_count * 3)
        else:
            tier = "单一来源"
            verification = "单源信号"
            lowered = source.lower()
            if "hacker news" in lowered:
                credibility = 62
            elif "ai hot" in lowered:
                credibility = 66
            elif "hugging face trending" in lowered:
                credibility = 76
            elif any(name in lowered for name in ("techcrunch", "coindesk")):
                credibility = 78
            else:
                credibility = 70
        return {
            "source_count": source_count,
            "source_tier": tier,
            "verification": verification,
            "credibility_score": credibility,
        }

    def _timeliness_score(self, item: Dict[str, Any]) -> int:
        published_at = self._parse_feed_datetime(
            clean_text(item.get("published_at", ""))
        )
        if published_at is None:
            published_at = self._parse_feed_datetime(clean_text(item.get("time", "")))
        if published_at is None:
            if clean_text(item.get("time", "")) in {"今日", "刚刚"}:
                return 91
            return 72 if self.dry_run else 60
        age_days = max(
            0.0,
            (
                datetime.now(timezone.utc) - published_at.astimezone(timezone.utc)
            ).total_seconds()
            / 86400,
        )
        if age_days <= 1:
            return 96
        if age_days <= 2:
            return 90
        if age_days <= 4:
            return 82
        if age_days <= 7:
            return 74
        if age_days <= 10:
            return 66
        return 48

    def _business_score(self, item: Dict[str, Any], section: str) -> int:
        text = " ".join(
            [
                item_title(item),
                clean_text(item.get("summary", "")),
                clean_text(item.get("description", "")),
                clean_text(item.get("category", "")),
                " ".join(item.get("tags", [])),
            ]
        ).lower()
        score = 38 + (8 if section == "venture" else 0)
        strong_signals = (
            "enterprise",
            "b2b",
            "workflow",
            "automation",
            "saas",
            "revenue",
            "customer",
            "sales",
            "funding",
            "acquisition",
            "creator",
            "deployment",
            "企业",
            "工作流",
            "自动化",
            "商业化",
            "融资",
        )
        creator_signals = (
            "video",
            "image",
            "social",
            "browser",
            "codex",
            "agent",
            "视频",
            "图像",
            "浏览器",
            "智能体",
        )
        score += min(35, sum(7 for keyword in strong_signals if keyword_in_text(text, keyword)))
        score += min(15, sum(4 for keyword in creator_signals if keyword_in_text(text, keyword)))
        return min(score, 96)

    def _apply_dimension_scores(self, item: Dict[str, Any], section: str) -> None:
        item.update(self._source_profile(item))
        generic_score = int(item.get("score", 0))
        content_score = 42 + int(generic_score * 0.38)
        content_score += min(10, len(item.get("tags", [])) * 2)
        if clean_text(item.get("summary_cn", "")):
            content_score += 4
        if int(item.get("source_count", 1)) >= 2:
            content_score += 5
        item["content_score"] = min(content_score, 96)
        item["business_score"] = self._business_score(item, section)
        item["timeliness_score"] = self._timeliness_score(item)
        personal = int(item.get("personal_relevance", item.get("rion_score", 0)))
        credibility = int(item.get("credibility_score", 0))
        overall = round(
            item["content_score"] * 0.26
            + item["business_score"] * 0.16
            + personal * 0.28
            + item["timeliness_score"] * 0.15
            + credibility * 0.15
        )
        item["overall_score"] = min(overall, 96)
        item["rion_score"] = item["overall_score"]
        item["content_value"] = self._content_value_label(item["overall_score"])

    def _personalization_reason(
        self,
        matched: List[Dict[str, Any]],
        section: str,
    ) -> str:
        if matched:
            reason = clean_text(matched[0].get("reason", ""))
            if reason:
                return reason

        fallback = {
            "ai": "可作为 AI 行业观察素材，优先看是否能转成 X 观点或工具测评。",
            "web3": "可作为 Web3 市场或监管观察素材，适合判断是否存在信息差。",
            "venture": "可作为商业化和资本风向素材，重点看是否能连接 B 端机会。",
            "github": "可作为开源工具观察素材，重点看是否值得上手测评或做工作流 demo。",
        }
        return fallback.get(section, "可作为今日 AI/Web3 内容素材继续跟进。")

    def _content_value_label(self, score: int) -> str:
        if score >= 88:
            return "优先跟进"
        if score >= 76:
            return "适合发 X"
        if score >= 64:
            return "可看"
        return "存档"

    def all_content_items(
        self,
        ai_news: List[Dict[str, str]],
        web3_news: List[Dict[str, str]],
        venture_news: List[Dict[str, str]],
        github_projects: List[Dict[str, str]],
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        source_sections = [
            ("ai", "AI 热点", ai_news),
            ("web3", "Web3 热点", web3_news),
            ("venture", "投资 & 经济", venture_news),
            ("github", "GitHub 优质项目", github_projects),
        ]
        for section_key, section_name, rows in source_sections:
            for row in rows:
                item = dict(row)
                item["section"] = section_key
                item["section_name"] = section_name
                item["display_title"] = item_title(item)
                item["source"] = item.get("source") or (
                    "GitHub Trending" if section_key == "github" else ""
                )
                item["item_key"] = canonical_url(item.get("url", "")) or (
                    f"{section_key}:{item['display_title'].lower()}"
                )
                items.append(item)
        return items

    def _ranked_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return sorted(
            items,
            key=lambda item: (
                int(item.get("overall_score", item.get("rion_score", 0))),
                int(item.get("credibility_score", 0)),
                int(item.get("timeliness_score", 0)),
                int(item.get("score", 0)),
            ),
            reverse=True,
        )

    def _briefing_entry(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "item_key": item.get("item_key", ""),
            "title": item.get("display_title", item_title(item)),
            "url": item.get("url", ""),
            "source": item.get("source", ""),
            "category": item.get("category", "AI 行业动态"),
            "section": item.get("section_name", ""),
            "section_key": item.get("section", ""),
            "tags": item.get("tags", []),
            "summary": item.get("summary_cn", ""),
            "score": item.get("score", 0),
            "overall_score": item.get("overall_score", item.get("rion_score", 0)),
            "rion_score": item.get("rion_score", item.get("score", 0)),
            "content_score": item.get("content_score", 0),
            "business_score": item.get("business_score", 0),
            "personal_relevance": item.get("personal_relevance", 0),
            "timeliness_score": item.get("timeliness_score", 0),
            "credibility_score": item.get("credibility_score", 0),
            "source_count": item.get("source_count", 1),
            "source_tier": item.get("source_tier", "单一来源"),
            "verification": item.get("verification", "单源信号"),
            "rion_reason": item.get("rion_reason", ""),
            "content_value": item.get("content_value", ""),
            "matched_signals": item.get("matched_signals", []),
            "base_overall_score": item.get(
                "base_overall_score", item.get("overall_score", 0)
            ),
            "feedback_score": item.get("feedback_score", 0),
            "feedback_reason": item.get("feedback_reason", ""),
            "first_seen": item.get("first_seen", ""),
            "last_seen": item.get("last_seen", ""),
            "repeat_count": item.get("repeat_count", 0),
            "score_delta": item.get("score_delta", 0),
            "rank_delta": item.get("rank_delta", 0),
            "history_status": item.get("history_status", "首次出现"),
        }

    def generate_highlights(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        limit = self._limit("highlights")
        if limit <= 0:
            return []

        ranked = self._ranked_items(items)
        highlights: List[Dict[str, Any]] = []
        seen_keys = set()
        seen_categories = set()
        section_counts: Dict[str, int] = {}
        section_caps = {
            "ai": min(3, limit),
            "web3": min(2, limit),
            "venture": min(2, limit),
            "github": min(2, limit),
        }

        def add_item(item: Dict[str, Any], *, enforce_cap: bool = True) -> bool:
            section = item.get("section", "")
            if enforce_cap and section_counts.get(section, 0) >= section_caps.get(section, limit):
                return False
            dedupe_key = item.get("url") or item.get("display_title", "")
            if dedupe_key in seen_keys:
                return False
            category = item.get("category", "AI 行业动态")
            if category in seen_categories and len(highlights) < min(3, limit):
                return False
            highlights.append(self._briefing_entry(item))
            seen_keys.add(dedupe_key)
            seen_categories.add(category)
            section_counts[section] = section_counts.get(section, 0) + 1
            return True

        for section in ("ai", "web3", "venture"):
            top_item = next((item for item in ranked if item.get("section") == section), None)
            if top_item:
                add_item(top_item)
            if len(highlights) >= limit:
                return highlights

        for item in ranked:
            add_item(item)
            if len(highlights) >= limit:
                return highlights

        for item in ranked:
            add_item(item, enforce_cap=False)
            if len(highlights) >= limit:
                break
        return highlights

    def generate_changes(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        limit = self._limit("changes")
        changed = [
            item
            for item in items
            if item.get("history_status") in {"首次出现", "持续升温"}
        ]
        changed.sort(
            key=lambda item: (
                item.get("history_status") == "持续升温",
                int(item.get("score_delta", 0)),
                int(item.get("overall_score", 0)),
            ),
            reverse=True,
        )
        return [self._briefing_entry(item) for item in changed[:limit]]

    def generate_business_opportunities(
        self,
        items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        limit = self._limit("business_opportunities")
        ranked = sorted(
            items,
            key=lambda item: (
                int(item.get("business_score", 0)),
                int(item.get("overall_score", 0)),
                int(item.get("credibility_score", 0)),
            ),
            reverse=True,
        )
        useful = [item for item in ranked if int(item.get("business_score", 0)) >= 55]
        return [self._briefing_entry(item) for item in useful[:limit]]

    def generate_watchlist(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        limit = self._limit("watchlist")
        repeated = [item for item in items if int(item.get("repeat_count", 0)) > 0]
        repeated.sort(
            key=lambda item: (
                item.get("history_status") == "持续升温",
                int(item.get("repeat_count", 0)),
                int(item.get("overall_score", 0)),
            ),
            reverse=True,
        )
        return [self._briefing_entry(item) for item in repeated[:limit]]

    def generate_editorial_queue(
        self,
        items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        limit = self._limit("editorial_queue")
        ranked = self._ranked_items(items)
        selected: List[Dict[str, Any]] = []
        seen_keys = set()
        source_counts: Dict[str, int] = {}

        def source_family(item: Dict[str, Any]) -> str:
            source = clean_text(item.get("source", "未知来源"))
            if source.startswith("AI HOT ·"):
                return "AI HOT"
            return source.split(" / ")[0]

        def add_item(item: Dict[str, Any], enforce_source_cap: bool = True) -> bool:
            key = item.get("item_key") or item.get("url") or item_title(item)
            if key in seen_keys:
                return False
            family = source_family(item)
            if enforce_source_cap and source_counts.get(family, 0) >= 3:
                return False
            selected.append(item)
            seen_keys.add(key)
            source_counts[family] = source_counts.get(family, 0) + 1
            return True

        for section in ("ai", "web3", "venture", "github"):
            top = next((item for item in ranked if item.get("section") == section), None)
            if top is not None:
                add_item(top)
        for item in ranked:
            add_item(item)
            if len(selected) >= limit:
                break
        if len(selected) < limit:
            for item in ranked:
                add_item(item, enforce_source_cap=False)
                if len(selected) >= limit:
                    break

        queue: List[Dict[str, Any]] = []
        for item in selected[:limit]:
            entry = self._briefing_entry(item)
            entry["raw_summary"] = clean_text(
                item.get("summary", "") or item.get("description", "")
            )
            entry["editorial_hint"] = self._make_x_angle(item)
            queue.append(entry)
        return queue

    def generate_x_topics(self, items: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        limit = self._limit("x_topics")
        if limit <= 0:
            return []

        ranked = self._ranked_items(items)
        topics: List[Dict[str, str]] = []
        seen_keys = set()
        section_counts: Dict[str, int] = {}
        section_caps = {
            "ai": min(3, limit),
            "web3": min(2, limit),
            "venture": min(2, limit),
            "github": min(2, limit),
        }

        def add_topic(item: Dict[str, Any], *, enforce_cap: bool = True) -> bool:
            section = item.get("section", "")
            if enforce_cap and section_counts.get(section, 0) >= section_caps.get(section, limit):
                return False
            dedupe_key = item.get("url") or item.get("display_title", "")
            if dedupe_key in seen_keys:
                return False
            title = item.get("display_title", "")
            category = item.get("category", "AI 行业动态")
            tags = item.get("tags", [])
            hook = self._make_x_hook(item)
            angle = self._make_x_angle(item)
            format_hint = ("单帖", "thread", "视觉/视频脚本")[len(topics) % 3]
            topics.append(
                {
                    "hook": hook,
                    "angle": angle,
                    "format": format_hint,
                    "source": title,
                    "url": item.get("url", ""),
                    "category": category,
                    "tags": " / ".join(tags),
                    "rion_score": str(item.get("rion_score", item.get("score", 0))),
                    "rion_reason": item.get("rion_reason", ""),
                    "content_value": item.get("content_value", ""),
                    "overall_score": str(item.get("overall_score", 0)),
                    "content_score": str(item.get("content_score", 0)),
                    "business_score": str(item.get("business_score", 0)),
                    "personal_relevance": str(item.get("personal_relevance", 0)),
                    "timeliness_score": str(item.get("timeliness_score", 0)),
                    "credibility_score": str(item.get("credibility_score", 0)),
                    "verification": item.get("verification", "单源信号"),
                }
            )
            seen_keys.add(dedupe_key)
            section_counts[section] = section_counts.get(section, 0) + 1
            return True

        for section in ("ai", "web3", "venture"):
            top_item = next((item for item in ranked if item.get("section") == section), None)
            if top_item:
                add_topic(top_item)
            if len(topics) >= limit:
                return topics

        for item in ranked:
            add_topic(item)
            if len(topics) >= limit:
                return topics

        for item in ranked:
            add_topic(item, enforce_cap=False)
            if len(topics) >= limit:
                break
        return topics

    def generate_x_drafts(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        limit = self._limit("x_drafts")
        if limit <= 0:
            return []

        ranked = self._ranked_items(items)
        drafts: List[Dict[str, Any]] = []
        seen_keys = set()

        def add_draft(item: Dict[str, Any]) -> bool:
            dedupe_key = item.get("url") or item.get("display_title", "")
            if dedupe_key in seen_keys:
                return False

            topic = {
                "hook": self._make_x_hook(item),
                "angle": self._make_x_angle(item),
                "format": ("单帖", "thread", "视觉/视频脚本")[len(drafts) % 3],
                "source": item.get("display_title", ""),
                "url": item.get("url", ""),
                "category": item.get("category", ""),
                "tags": " / ".join(item.get("tags", [])),
                "rion_score": str(item.get("rion_score", item.get("score", 0))),
                "rion_reason": item.get("rion_reason", ""),
                "content_value": item.get("content_value", ""),
            }
            draft = self._make_x_draft(item, topic)
            drafts.append(draft)
            seen_keys.add(dedupe_key)
            return True

        for section in ("ai", "web3", "github", "venture"):
            top_item = next((item for item in ranked if item.get("section") == section), None)
            if top_item:
                add_draft(top_item)
            if len(drafts) >= limit:
                return drafts

        for item in ranked:
            add_draft(item)
            if len(drafts) >= limit:
                break

        return drafts

    def _make_x_draft(
        self,
        item: Dict[str, Any],
        topic: Dict[str, str],
    ) -> Dict[str, Any]:
        title = item.get("display_title", "")
        summary = item.get("summary_cn", "")
        tags = item.get("tags", [])
        category = item.get("category", "")
        format_hint = topic.get("format", "单帖")
        is_thread = format_hint == "thread"

        if is_thread:
            body = self._make_thread_draft(title, summary, tags, category)
        elif format_hint == "视觉/视频脚本":
            body = self._make_visual_draft(title, summary, tags)
        else:
            body = self._make_single_post_draft(title, summary, tags, category)

        return {
            "title": topic.get("hook", ""),
            "format": format_hint,
            "body": body,
            "source": topic.get("source", ""),
            "url": topic.get("url", ""),
            "category": topic.get("category", ""),
            "tags": topic.get("tags", ""),
            "rion_score": topic.get("rion_score", ""),
            "rion_reason": topic.get("rion_reason", ""),
            "content_value": topic.get("content_value", ""),
            "overall_score": item.get("overall_score", 0),
            "content_score": item.get("content_score", 0),
            "business_score": item.get("business_score", 0),
            "personal_relevance": item.get("personal_relevance", 0),
            "timeliness_score": item.get("timeliness_score", 0),
            "credibility_score": item.get("credibility_score", 0),
            "verification": item.get("verification", "单源信号"),
        }

    def _make_visual_draft(
        self,
        title: str,
        summary: str,
        tags: List[str],
    ) -> str:
        visual = "模型页面或产品演示" if "Web3" not in tags else "价格、监管或链上数据截图"
        return (
            f"开场画面：{short_title(title, 34)}\n\n"
            f"旁白：{summary}\n\n"
            f"画面 2：展示{visual}，标出最关键的一处变化。\n\n"
            "收尾：它真正值得关注的，不是热度本身，而是接下来会改变谁的工作流、成本或分发入口。"
        )

    def _make_single_post_draft(
        self,
        title: str,
        summary: str,
        tags: List[str],
        category: str,
    ) -> str:
        short = short_title(title, 34)
        if "Web3" in tags:
            return (
                f"今天这条 Web3 动态值得注意：{short}\n\n"
                f"{summary}\n\n"
                "我会重点看两件事：\n"
                "1. 这是不是短期市场情绪变化\n"
                "2. 这背后有没有普通人容易忽略的监管/链上信息差"
            )
        if "融资/IPO" in tags or category in {"融资并购", "资本市场", "商业化"}:
            return (
                f"AI 商业化现在越来越像一道筛选题：{short}\n\n"
                f"{summary}\n\n"
                "我更关心的不是融资数字本身，而是资本到底在买哪类确定性：收入、客户、工作流，还是更强的分发入口。"
            )
        if "AI 编码" in tags or "Agent" in tags or category == "Agent / AI 编码":
            return (
                f"AI Agent 这条线，今天最值得看的一个信号是：{short}\n\n"
                f"{summary}\n\n"
                "真正有价值的不是“又来了一个 agent”，而是它有没有接进真实工作流：写代码、审代码、跑浏览器、处理任务，或者直接替人省时间。"
            )
        if "视频/多模态" in tags:
            return (
                f"AI 视频/多模态还在加速：{short}\n\n"
                f"{summary}\n\n"
                "这类东西对内容创作者的意义很直接：生产成本继续下降，但审美、选题和分发会变得更重要。"
            )
        return (
            f"今天看到一个 AI 动态：{short}\n\n"
            f"{summary}\n\n"
            "如果要做成内容，我会从“它改变了谁的工作流”这个角度切，而不是只复述新闻。"
        )

    def _make_thread_draft(
        self,
        title: str,
        summary: str,
        tags: List[str],
        category: str,
    ) -> str:
        short = short_title(title, 34)
        if "Web3" in tags:
            return (
                f"1/ 这条 Web3 动态值得拆一下：{short}\n\n"
                f"2/ {summary}\n\n"
                "3/ 我会把它放在三个维度看：监管、市场情绪、链上数据。\n\n"
                "4/ 真正的信息差通常不在标题里，而在它会改变哪些人的行为：交易者、机构、项目方，还是普通用户。"
            )
        if "AI 编码" in tags or "Agent" in tags or category == "Agent / AI 编码":
            return (
                f"1/ AI Agent 的下一波机会，可能藏在这个信号里：{short}\n\n"
                f"2/ {summary}\n\n"
                "3/ 我现在判断 agent 项目，会优先看它有没有接进真实工作流，而不是 demo 看起来酷不酷。\n\n"
                "4/ 能落地的方向大概有三类：开发者效率、浏览器自动化、企业内部流程。真正能省时间的，才有商业化机会。"
            )
        return (
            f"1/ 今天这条 AI 动态值得看：{short}\n\n"
            f"2/ {summary}\n\n"
            "3/ 我会重点看它是否带来新的入口、新的工作流，或者新的商业化信号。\n\n"
            "4/ 对内容创作者来说，这类新闻最好的写法不是复述，而是翻译成普通人能理解的机会和风险。"
        )

    def _make_x_hook(self, item: Dict[str, Any]) -> str:
        title = item.get("display_title", "")
        tags = item.get("tags", [])
        category = item.get("category", "")
        is_agent_topic = "AI 编码" in tags or "Agent" in tags or category == "Agent / AI 编码"
        if is_agent_topic:
            return f"AI Agent 的下一波机会，可能藏在「{short_title(title, 22)}」里"
        if "Mistral" in tags:
            return f"别只盯着 OpenAI，{short_title(title, 22)} 这类模型公司也在改写牌桌"
        if "监管" in tags:
            return f"监管开始下场后，{short_title(title, 22)} 这类 Web3 叙事要重新估值"
        if "Web3" in tags:
            return f"Web3 的下一条信息差，可能藏在「{short_title(title, 22)}」里"
        if "浏览器" in tags:
            return f"浏览器不只是搜索入口了，{short_title(title, 22)} 说明入口战争变了"
        if "融资/IPO" in tags:
            return f"资本还在押注什么？从「{short_title(title, 22)}」看 AI 商业化信号"
        if "安全" in tags:
            return f"AI 安全不是远方问题，{short_title(title, 22)} 已经把风险摆到台面上"
        if category == "学习资源":
            return f"这份资料值得收藏：{short_title(title, 28)}"
        return f"今天这条 AI/Web3 动态值得看：{short_title(title, 28)}"

    def _make_x_angle(self, item: Dict[str, Any]) -> str:
        tags = item.get("tags", [])
        category = item.get("category", "")
        summary = item.get("summary_cn", "")
        is_agent_topic = "AI 编码" in tags or "Agent" in tags or category == "Agent / AI 编码"
        if is_agent_topic:
            return "从开发者效率、任务分发和真实工作流落地切入，别只讲模型参数。"
        if "Mistral" in tags:
            return "从模型公司差异化、开源生态和欧洲 AI 叙事切入，适合做 OpenAI 之外的格局解读。"
        if "Web3" in tags:
            return "从监管、市场情绪和普通用户风险切入，适合做信息差解读。"
        if "融资/IPO" in tags:
            return "从资本为什么买单切入，顺手连接 B 端 AI 服务和商业化机会。"
        if "办公效率" in tags:
            return "从真实使用场景切入，讲它能替代哪个旧流程、节省什么成本。"
        if "安全" in tags:
            return "从风险和防御清单切入，适合做开发者/企业提醒。"
        return summary or "从它对普通用户、开发者或自媒体选题的影响切入。"

    def _format_hint(self, item: Dict[str, Any]) -> str:
        tags = item.get("tags", [])
        category = item.get("category", "")
        if "AI 编码" in tags or "Agent" in tags or "Web3" in tags or category == "Agent / AI 编码":
            return "thread"
        if "融资/IPO" in tags or "监管" in tags:
            return "单帖 + 数据截图"
        return "单帖"

    def add_chinese_summaries(
        self,
        ai_news: List[Dict[str, str]],
        web3_news: List[Dict[str, str]],
        venture_news: List[Dict[str, str]],
        github_projects: List[Dict[str, str]],
    ) -> None:
        for item in ai_news:
            item["summary_cn"] = self._summarize_news_cn(item, "ai")
        for item in web3_news:
            item["summary_cn"] = self._summarize_news_cn(item, "web3")
        for item in venture_news:
            item["summary_cn"] = self._summarize_news_cn(item, "venture")
        for item in github_projects:
            item["summary_cn"] = self._summarize_project_cn(item)

    def _summarize_news_cn(self, item: Dict[str, str], section: str) -> str:
        existing = clean_text(item.get("summary", ""))
        if contains_chinese(existing):
            return existing

        title = clean_text(item.get("title", ""))
        haystack = f"{title} {existing}".lower()

        if section == "ai":
            rules = [
                (("glossary", "definition", "term", "hallucination"), "这是一篇 AI 概念科普，适合拆成术语卡片或新手入门内容。"),
                (("browser", "browsers", "chrome", "safari", "search"), "浏览器正在从搜索入口变成 AI 工作入口，值得关注新的流量分发位置。"),
                (("agent", "agents", "agentic"), "AI agent 的落地速度和瓶颈被重新讨论，核心看点是工具链还没完全成熟。"),
                (("mistral",), "Mistral 代表 OpenAI 之外的模型竞争路线，适合观察欧洲 AI、开源生态和企业落地差异。"),
                (("openai",), "OpenAI 的资本、产品或政策动作继续牵动行业预期，是判断 AI 风向的重要信号。"),
                (("office", "productivity"), "AI 办公套件竞争升温，生产力工具正在出现新的替代和重做机会。"),
                (("microsoft",), "微软继续押注企业级 AI 部署，重点在 B 端落地和销售体系扩张。"),
                (("chip", "chips", "gpu", "gpus", "samsung", "nvidia"), "AI 公司开始向芯片和算力基础设施延伸，说明底层成本和供应链越来越关键。"),
                (("anthropic", "claude"), "Anthropic 和 Claude 的产品动作适合观察模型公司竞争、订阅转化和企业级 AI 落地。"),
                (("ipo", "unicorn", "series", "funding", "venture"), "资本市场仍在给 AI 故事重新定价，融资、IPO 和估值变化值得跟踪。"),
                (("game", "gaming", "date", "vibe-coded", "openclaw"), "AI 应用进入娱乐、社交和生活场景，可以做成产品体验或争议性选题。"),
            ]
            fallback = f"这条围绕「{short_title(title, 24)}」展开，可作为 AI 行业动态或工具趋势素材。"
        elif section == "web3":
            rules = [
                (("prediction market", "prediction markets"), "预测市场进入监管视野，Web3 的高增长叙事开始面对合规约束。"),
                (("rule", "rules", "regulation", "regulatory", "eu", "uk", "mica"), "加密监管规则继续细化，机构入场和散户参与门槛可能被重新划分。"),
                (("xrp", "bitcoin", "btc", "ether", "solana", "token"), "主流资产价格和链上指标出现变化，反映市场风险偏好正在调整。"),
                (("sanction", "treasury", "isis", "compliance"), "链上地址被纳入制裁和执法场景，合规能力正成为加密基础设施的硬门槛。"),
                (("mining", "hashrate", "miner"), "矿池或算力侧出现变化，会影响比特币网络供给侧和矿工格局。"),
                (("tokenized", "blackrock", "etf", "stock"), "RWA 和代币化证券继续推进，传统金融资产上链的路径更清晰了。"),
            ]
            fallback = f"这条围绕「{short_title(title, 24)}」展开，可作为 Web3 市场、监管或叙事观察。"
        else:
            rules = [
                (("fund", "fund ii", "backs", "stake", "stakes", "vc", "venture", "capital"), "创投资金仍在寻找确定性增长标的，资本偏好正在向更可验证的赛道集中。"),
                (("ipo", "trading", "public"), "上市和二级市场表现提供了新的估值锚点，也反映退出窗口和市场情绪。"),
                (("ai", "spending", "worth"), "企业开始追问 AI 投入回报，商业化效率比单纯讲概念更重要。"),
                (("acquisition", "acquire", "buys", "merger"), "并购和整合动作增多，说明行业集中度和退出机会正在变化。"),
            ]
            fallback = f"这条围绕「{short_title(title, 24)}」展开，可作为投资、融资或商业化观察。"

        for keywords, summary in rules:
            if has_any_keyword(haystack, keywords):
                return summary
        return fallback

    def _summarize_project_cn(self, project: Dict[str, str]) -> str:
        name = clean_text(project.get("name", ""))
        description = clean_text(project.get("description", ""))
        haystack = f"{name} {description}".lower()

        rules = [
            (("security", "penetration", "vulnerability", "vulnerabilities", "vulnerab*", "pentest"), "AI 安全和渗透测试工具，可以用来讲开发者安全工作流。"),
            (("browser", "devtools", "gui", "page"), "浏览器或网页自动化工具，核心价值是把自然语言操作接进真实界面。"),
            (("meeting", "transcription", "whisper", "ollama"), "本地 AI 会议助手，亮点是隐私、本地转写和办公自动化。"),
            (("book", "course", "learning", "machine learning"), "机器学习或工程学习资料，适合收藏成系统化学习素材。"),
            (("prompt", "prompts", "system prompt", "system prompts", "system_prompt", "system_prompts"), "系统提示词和模型行为资料库，适合做 prompt engineering 研究。"),
            (("terminal", "multiplexer", "cli"), "终端里的 agent 调度工具，适合做效率流和开发环境升级选题。"),
            (("web3", "crypto", "blockchain", "on-chain", "chain", "indexer"), "Web3 数据或链上基础设施项目，适合观察开发者工具机会。"),
            (("codex", "claude", "agent", "agents", "mcp"), "Coding agent 相关项目，重点是多 agent 协作、审代码或任务分发。"),
        ]

        for keywords, summary in rules:
            if has_any_keyword(haystack, keywords):
                return summary

        if description:
            return f"{project.get('language', 'Unknown')} 项目，可先看 README 判断是否值得做工具测评。"
        return "GitHub Trending 热门项目，可先快速浏览 demo、README 和 issue 活跃度。"

    def _select_ai_candidates(
        self,
        items: List[Dict[str, Any]],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Keep ranking quality while preventing one feed from taking the page."""
        ranked = self._ranked_items(items)
        selected: List[Dict[str, Any]] = []
        source_counts: Dict[str, int] = {}
        selected_keys = set()
        for item in ranked:
            source = clean_text(item.get("source", "未知来源")).split(" / ")[0]
            if source_counts.get(source, 0) >= 2:
                continue
            key = canonical_url(item.get("url", "")) or item_title(item).lower()
            if key in selected_keys:
                continue
            selected.append(item)
            selected_keys.add(key)
            source_counts[source] = source_counts.get(source, 0) + 1
            if len(selected) >= limit:
                return selected
        for item in ranked:
            key = canonical_url(item.get("url", "")) or item_title(item).lower()
            if key in selected_keys:
                continue
            selected.append(item)
            selected_keys.add(key)
            if len(selected) >= limit:
                break
        return selected

    def generate_data(self) -> Dict[str, Any]:
        """生成结构化早报数据。"""
        self._log("开始生成每日早报...\n")

        now = datetime.now()
        run_date = now.strftime("%Y-%m-%d")
        base_ai_news = self.fetch_ai_news()
        ecosystem_signals = self.fetch_ecosystem_signals()
        ai_news = self._dedupe_items(
            self._round_robin(
                [base_ai_news, ecosystem_signals],
                len(base_ai_news) + len(ecosystem_signals),
            )
        )
        web3_news = self.fetch_web3_news()
        venture_news = self.fetch_venture_news()
        news_sections = self._dedupe_news_sections(
            ai_news,
            web3_news,
            venture_news,
        )
        ai_news = news_sections["ai"]
        web3_news = news_sections["web3"]
        venture_news = news_sections["venture"]
        github_projects = self.fetch_github_trending()
        self.enrich_items(ai_news, web3_news, venture_news, github_projects)
        raw_items = ai_news + web3_news + venture_news + github_projects
        if self.history_store is not None:
            self.history_store.apply_feedback(raw_items)
            for item in raw_items:
                item["content_value"] = self._content_value_label(
                    int(item.get("overall_score", 0))
                )
        else:
            for item in raw_items:
                item["base_overall_score"] = item.get("overall_score", 0)
                item["feedback_score"] = 0
                item["feedback_reason"] = ""
        candidate_items = self.all_content_items(
            ai_news,
            web3_news,
            venture_news,
            github_projects,
        )
        ranked_candidates = self._ranked_items(candidate_items)
        if self.history_store is not None:
            self.history_store.annotate_items(ranked_candidates, run_date)
        else:
            for rank, item in enumerate(ranked_candidates, 1):
                item.update(
                    {
                        "current_rank": rank,
                        "first_seen": run_date,
                        "last_seen": run_date,
                        "seen_count": 0,
                        "repeat_count": 0,
                        "score_delta": 0,
                        "rank_delta": 0,
                        "history_status": "首次出现",
                    }
                )

        ai_news = self._select_ai_candidates(ai_news, self._limit("ai_news"))
        all_items = self.all_content_items(ai_news, web3_news, venture_news, github_projects)
        history_by_key = {
            item.get("item_key", ""): item
            for item in ranked_candidates
            if item.get("item_key")
        }
        history_fields = (
            "current_rank",
            "first_seen",
            "last_seen",
            "seen_count",
            "repeat_count",
            "score_delta",
            "rank_delta",
            "history_status",
        )
        for item in all_items:
            history_item = history_by_key.get(item.get("item_key", ""), {})
            for field in history_fields:
                if field in history_item:
                    item[field] = history_item[field]
        ranked_items = self._ranked_items(all_items)

        highlights = self.generate_highlights(ranked_items)
        changes = self.generate_changes(ranked_items)
        business_opportunities = self.generate_business_opportunities(ranked_items)
        watchlist = self.generate_watchlist(ranked_items)
        x_topics = self.generate_x_topics(all_items)
        x_drafts = self.generate_x_drafts(all_items)
        topics = self.generate_topics(ai_news, web3_news, venture_news, github_projects)
        editorial_queue = self.generate_editorial_queue(ranked_candidates)

        if self.history_store is not None:
            selected_keys = {
                item.get("item_key", "") for item in highlights if item.get("item_key")
            }
            self.history_store.record_items(ranked_candidates, run_date, selected_keys)
            self.history_store.record_source_runs(run_date, self.source_health)

        return {
            "metadata": {
                "title": "Rion 每日早报",
                "generated_at": now.isoformat(timespec="seconds"),
                "date": now.strftime("%Y.%m.%d"),
                "weekday": chinese_weekday(now),
                "dry_run": self.dry_run,
                "history_enabled": self.history_store is not None,
                "editorial_mode": "codex-ready",
                "candidate_count": len(ranked_candidates),
                "editorial_instructions": [
                    "只保留能核验的事实和原始链接，不补写来源中没有的数字。",
                    "优先选择新变化、多源印证、官方更新和可转成内容或商业动作的信号。",
                    "中文解释要具体，X 草稿按单帖、thread、视觉或视频脚本区分。",
                ],
            },
            "sections": {
                "highlights": highlights,
                "must_read": highlights,
                "changes": changes,
                "business_opportunities": business_opportunities,
                "watchlist": watchlist,
                "x_topics": x_topics,
                "x_drafts": x_drafts,
                "ai_news": ai_news,
                "web3_news": web3_news,
                "venture_news": venture_news,
                "github_projects": github_projects,
                "topics": topics,
                "editorial_queue": editorial_queue,
            },
        }

    def format_output(self, data: Dict[str, Any], output_format: str = "text") -> str:
        """按指定格式输出。"""
        output_format = output_format.lower()
        if output_format == "json":
            return json.dumps(data, ensure_ascii=False, indent=2)
        if output_format == "markdown":
            return self._format_markdown(data)
        return self._format_text(data)

    def record_feedback(
        self,
        target: str,
        action: str,
        note: str = "",
    ) -> Dict[str, Any]:
        if self.history_store is None:
            raise ValueError("反馈功能需要启用历史数据库")
        return self.history_store.record_feedback(target, action, note)

    def generate_weekly_review(self, days: int = 7) -> Dict[str, Any]:
        if self.history_store is None:
            raise ValueError("周复盘需要启用历史数据库")
        summary = self.history_store.weekly_summary(days=days)
        return {
            "metadata": {
                "title": "Rion AI 简报周复盘",
                "generated_at": datetime.now().isoformat(timespec="seconds"),
            },
            **summary,
        }

    def format_weekly_review(
        self,
        data: Dict[str, Any],
        output_format: str = "markdown",
    ) -> str:
        if output_format == "json":
            return json.dumps(data, ensure_ascii=False, indent=2)

        period = data["period"]
        lines = [
            f"# Rion AI 简报周复盘 · {period['start']} 至 {period['end']}",
            "",
            "## 本周持续信号",
            "",
        ]
        top_items = data.get("top_items", [])
        if not top_items:
            lines.append("- 暂无历史数据，先正常生成几天早报后再复盘。")
        for index, item in enumerate(top_items, 1):
            title = item.get("title", "")
            url = item.get("url", "")
            title_text = f"[{title}]({url})" if url else title
            lines.append(f"{index}. {title_text}")
            lines.append(
                f"   出现 {item.get('days_seen', 0)} 天 · "
                f"平均综合分 {item.get('avg_score', 0)} · "
                f"最佳排名 {item.get('best_rank', 0)} · "
                f"入选必看 {item.get('selected_days', 0)} 天"
            )

        lines.extend(["", "## 你的反馈", ""])
        action_labels = {
            "opened": "打开阅读",
            "saved": "收藏",
            "drafted": "写成草稿",
            "published": "已经发布",
            "dismissed": "没价值",
        }
        feedback = data.get("feedback", {})
        if not feedback:
            lines.append("- 本周还没有反馈。对几条内容标记后，排序才会开始学习。")
        else:
            for action, count in feedback.items():
                lines.append(f"- {action_labels.get(action, action)}：{count} 条")

        preferences = data.get("preferences", {})
        positive_categories = [
            (name, score)
            for name, score in preferences.get("categories", [])
            if score > 0
        ][:5]
        positive_sources = [
            (name, score)
            for name, score in preferences.get("sources", [])
            if score > 0
        ][:5]
        if positive_categories:
            lines.append(
                "- 当前偏好类别："
                + " / ".join(f"{name}（{score:+d}）" for name, score in positive_categories)
            )
        if positive_sources:
            lines.append(
                "- 当前偏好来源："
                + " / ".join(f"{name}（{score:+d}）" for name, score in positive_sources)
            )

        lines.extend(["", "## 来源健康度", ""])
        health = data.get("source_health", [])
        if not health:
            lines.append("- 暂无来源健康记录。")
        else:
            lines.extend(
                [
                    "| 来源 | 成功率 | 条目数 | 平均耗时 |",
                    "| --- | ---: | ---: | ---: |",
                ]
            )
            for source in health:
                lines.append(
                    f"| {source.get('source', '')} | "
                    f"{source.get('success_rate', 0)}% | "
                    f"{source.get('item_count', 0)} | "
                    f"{int(source.get('avg_latency_ms') or 0)} ms |"
                )

        lines.extend(["", "## 下周动作", ""])
        unhealthy = [
            row for row in health if int(row.get("success_rate", 0)) < 80
        ]
        if unhealthy:
            names = "、".join(row.get("source", "") for row in unhealthy[:4])
            lines.append(f"- 检查不稳定来源：{names}。")
        if not feedback:
            lines.append("- 至少标记 3 条内容：一条收藏、一条写稿、一条没价值。")
        if positive_categories:
            lines.append(f"- 下周优先追踪：{positive_categories[0][0]}。")
        if health and not unhealthy and feedback:
            lines.append("- 来源运行稳定，继续积累反馈，不需要扩充信源。")
        lines.extend(["", f"> 生成时间：{data['metadata']['generated_at']}"])
        return "\n".join(lines)

    def _dimension_meta(self, item: Dict[str, Any]) -> str:
        labels = (
            ("综合", "overall_score", "rion_score"),
            ("内容", "content_score", None),
            ("商业", "business_score", None),
            ("匹配", "personal_relevance", None),
            ("时效", "timeliness_score", None),
            ("可信", "credibility_score", None),
        )
        parts: List[str] = []
        if item.get("content_value"):
            parts.append(str(item["content_value"]))
        for label, key, fallback in labels:
            value = item.get(key)
            if value in {None, ""} and fallback:
                value = item.get(fallback)
            if value not in {None, ""}:
                parts.append(f"{label} {value}")
        feedback_score = int(item.get("feedback_score", 0) or 0)
        if feedback_score:
            parts.append(f"反馈 {feedback_score:+d}")
        if item.get("verification"):
            parts.append(str(item["verification"]))
        return " · ".join(parts)

    def generate(self, output_format: Optional[str] = None) -> str:
        """保留旧用法：DailyBriefing().generate() 返回纯文本早报。"""
        data = self.generate_data()
        fmt = output_format or self.config.get("output", {}).get("format", "text")
        return self.format_output(data, fmt)

    def _format_text(self, data: Dict[str, Any]) -> str:
        meta = data["metadata"]
        sections = data["sections"]
        lines = [
            f"==== Rion 每日早报 · {meta['date']} {meta['weekday']} ====",
            "",
        ]

        self._append_text_highlights(lines, sections.get("changes", []), "相比昨天的新变化")
        self._append_text_highlights(lines, sections.get("must_read", []), "今日必须看")
        self._append_text_x_topics(lines, sections.get("x_topics", []))
        self._append_text_highlights(
            lines,
            sections.get("business_opportunities", []),
            "B端/商业机会",
        )
        self._append_text_highlights(lines, sections.get("watchlist", []), "持续跟踪")
        self._append_text_x_drafts(lines, sections.get("x_drafts", []))
        self._append_news_section(lines, "AI 热点", sections["ai_news"])
        self._append_news_section(lines, "Web3 热点", sections["web3_news"])
        self._append_news_section(lines, "投资 & 经济", sections["venture_news"])
        self._append_project_section(lines, sections["github_projects"])
        self._append_topic_section(lines, sections["topics"])

        lines.extend(
            [
                "━━━━━━━━━━━━━━━━━━",
                f"{meta['date']} 早报完毕",
                "━━━━━━━━━━━━━━━━━━",
                "",
                "支持这个项目 / Support the Project",
                "如果这份早报帮你节省了筛选 AI 信息的时间，欢迎给项目点个 Star。你的支持会让它继续更新、继续变得更好。",
                "If this briefing saves you time finding useful AI signals, please consider giving the project a Star. Your support helps it keep improving.",
                f"项目地址 / Repository: {REPOSITORY_URL}",
            ]
        )
        return "\n".join(lines)

    def _format_markdown(self, data: Dict[str, Any]) -> str:
        meta = data["metadata"]
        sections = data["sections"]
        lines = [f"# Rion 每日早报 · {meta['date']} {meta['weekday']}", ""]

        self._append_markdown_highlights(
            lines,
            sections.get("changes", []),
            "相比昨天的新变化",
        )
        self._append_markdown_highlights(
            lines,
            sections.get("must_read", []),
            "今日必须看",
        )
        self._append_markdown_x_topics(lines, sections.get("x_topics", []))
        self._append_markdown_highlights(
            lines,
            sections.get("business_opportunities", []),
            "B端/商业机会",
        )
        self._append_markdown_highlights(
            lines,
            sections.get("watchlist", []),
            "持续跟踪",
        )
        self._append_markdown_x_drafts(lines, sections.get("x_drafts", []))
        self._append_markdown_news(lines, "AI 热点", sections["ai_news"])
        self._append_markdown_news(lines, "Web3 热点", sections["web3_news"])
        self._append_markdown_news(lines, "投资 & 经济", sections["venture_news"])

        lines.extend(["## GitHub 优质项目", ""])
        if sections["github_projects"]:
            for index, project in enumerate(sections["github_projects"], 1):
                today = f" | 今日新增 {project['today_stars']}" if project.get("today_stars") else ""
                lines.append(
                    f"{index}. [{project['name']}]({project.get('url', '')})"
                    f" - {project.get('language', 'Unknown')} | {project.get('stars', '0')} stars{today}"
                )
                meta_parts = []
                if project.get("category"):
                    meta_parts.append(project["category"])
                if project.get("tags"):
                    meta_parts.append(" / ".join(project["tags"]))
                score_meta = self._dimension_meta(project)
                if score_meta:
                    meta_parts.append(score_meta)
                if meta_parts:
                    lines.append(f"   {' · '.join(meta_parts)}")
                if project.get("rion_reason"):
                    lines.append(f"   {project['rion_reason']}")
                if project.get("description"):
                    lines.append(f"   {project['description']}")
                if project.get("summary_cn"):
                    lines.append(f"   {project['summary_cn']}")
        else:
            lines.append("- 暂未抓到 GitHub Trending 内容。")

        lines.extend(["", "## 今日选题素材", ""])
        for index, topic in enumerate(sections["topics"], 1):
            lines.append(f"{index}. {topic}")

        lines.extend(
            [
                "",
                f"> 生成时间：{meta['generated_at']}",
                "",
                "---",
                "",
                "## 支持这个项目 / Support the Project",
                "",
                "如果这份早报帮你节省了筛选 AI 信息的时间，欢迎给项目点个 Star。你的支持会让它继续更新、继续变得更好。",
                "",
                "If this briefing saves you time finding useful AI signals, please consider giving the project a Star. Your support helps it keep improving.",
                "",
                f"项目地址 / Repository: [Rion-Wu-tech/ai-daily-briefing]({REPOSITORY_URL})",
            ]
        )
        return "\n".join(lines)

    def _append_markdown_highlights(
        self,
        lines: List[str],
        highlights: List[Dict[str, Any]],
        title: str = "今日必须看",
    ) -> None:
        lines.extend([f"## {title}", ""])
        if not highlights:
            lines.extend(["- 今天没有符合条件的条目。", ""])
            return

        for index, item in enumerate(highlights, 1):
            title = item.get("title", "")
            url = item.get("url", "")
            title_text = f"[{title}]({url})" if url else title
            tags = " / ".join(item.get("tags", []))
            meta = item.get("category", "")
            if tags:
                meta = f"{meta} · {tags}" if meta else tags
            score_meta = self._dimension_meta(item)
            if score_meta:
                meta = f"{meta} · {score_meta}" if meta else score_meta
            lines.append(f"{index}. {title_text}")
            if meta:
                lines.append(f"   {meta}")
            if item.get("history_status"):
                history = item["history_status"]
                if int(item.get("score_delta", 0)):
                    history += f" · 综合分变化 {int(item['score_delta']):+d}"
                lines.append(f"   {history} · {item.get('verification', '单源信号')}")
            if item.get("rion_reason"):
                lines.append(f"   {item['rion_reason']}")
            if item.get("feedback_reason"):
                lines.append(f"   {item['feedback_reason']}")
            if item.get("summary"):
                lines.append(f"   {item['summary']}")
        lines.append("")

    def _append_markdown_x_topics(
        self, lines: List[str], x_topics: List[Dict[str, str]]
    ) -> None:
        lines.extend(["## 适合发 X 的选题", ""])
        if not x_topics:
            lines.extend(["- 暂未生成选题。", ""])
            return

        for index, topic in enumerate(x_topics, 1):
            source = topic.get("source", "")
            url = topic.get("url", "")
            source_text = f"[{source}]({url})" if url else source
            lines.append(f"{index}. {topic.get('hook', '')}")
            score_line = self._dimension_meta(topic)
            if score_line:
                lines.append(f"   {score_line}")
            lines.append(f"   角度：{topic.get('angle', '')}")
            if topic.get("rion_reason"):
                lines.append(f"   {topic['rion_reason']}")
            lines.append(f"   形式：{topic.get('format', '')} · 来源：{source_text}")
            if topic.get("tags"):
                lines.append(f"   标签：{topic['tags']}")
        lines.append("")

    def _append_markdown_x_drafts(
        self, lines: List[str], x_drafts: List[Dict[str, Any]]
    ) -> None:
        lines.extend(["## X 草稿", ""])
        if not x_drafts:
            lines.extend(["- 暂未生成 X 草稿。", ""])
            return

        for index, draft in enumerate(x_drafts, 1):
            source = draft.get("source", "")
            url = draft.get("url", "")
            source_text = f"[{source}]({url})" if url else source
            lines.append(f"### {index}. {draft.get('title', '')}")
            meta_parts = []
            if draft.get("format"):
                meta_parts.append(draft["format"])
            score_meta = self._dimension_meta(draft)
            if score_meta:
                meta_parts.append(score_meta)
            if meta_parts:
                lines.append(f"{' · '.join(meta_parts)}  ")
            if draft.get("rion_reason"):
                lines.append(f"{draft['rion_reason']}  ")
            if source_text:
                lines.append(f"来源：{source_text}")
            lines.extend(["", "```text", draft.get("body", ""), "```", ""])

    def _append_text_highlights(
        self,
        lines: List[str],
        highlights: List[Dict[str, Any]],
        title: str = "今日必须看",
    ) -> None:
        lines.extend(["━━━━━━━━━━━━━━━━━━", f"{title}（{len(highlights)}条）", "━━━━━━━━━━━━━━━━━━", ""])
        if not highlights:
            lines.extend(["今天没有符合条件的条目。", ""])
            return

        for index, item in enumerate(highlights, 1):
            lines.append(f"{index}. {item.get('title', '')}")
            meta = item.get("category", "")
            tags = " / ".join(item.get("tags", []))
            if tags:
                meta = f"{meta} · {tags}" if meta else tags
            score_meta = self._dimension_meta(item)
            if score_meta:
                meta = f"{meta} · {score_meta}" if meta else score_meta
            if meta:
                lines.append(meta)
            if item.get("history_status"):
                lines.append(
                    f"{item['history_status']} · {item.get('verification', '单源信号')}"
                )
            if item.get("rion_reason"):
                lines.append(item["rion_reason"])
            if item.get("feedback_reason"):
                lines.append(item["feedback_reason"])
            if item.get("summary"):
                lines.append(item["summary"])
            if item.get("url"):
                lines.append(item["url"])
            lines.append("")

    def _append_text_x_topics(
        self, lines: List[str], x_topics: List[Dict[str, str]]
    ) -> None:
        lines.extend(["━━━━━━━━━━━━━━━━━━", f"适合发 X 的选题（{len(x_topics)}条）", "━━━━━━━━━━━━━━━━━━", ""])
        if not x_topics:
            lines.extend(["暂未生成选题。", ""])
            return

        for index, topic in enumerate(x_topics, 1):
            lines.append(f"{index}. {topic.get('hook', '')}")
            score_line = self._dimension_meta(topic)
            if score_line:
                lines.append(score_line)
            lines.append(f"角度：{topic.get('angle', '')}")
            if topic.get("rion_reason"):
                lines.append(topic["rion_reason"])
            lines.append(f"形式：{topic.get('format', '')}")
            if topic.get("source"):
                lines.append(f"来源：{topic['source']}")
            if topic.get("url"):
                lines.append(topic["url"])
            lines.append("")

    def _append_text_x_drafts(
        self, lines: List[str], x_drafts: List[Dict[str, Any]]
    ) -> None:
        lines.extend(["━━━━━━━━━━━━━━━━━━", f"X 草稿（{len(x_drafts)}条）", "━━━━━━━━━━━━━━━━━━", ""])
        if not x_drafts:
            lines.extend(["暂未生成 X 草稿。", ""])
            return

        for index, draft in enumerate(x_drafts, 1):
            lines.append(f"{index}. {draft.get('title', '')}")
            meta_parts = []
            if draft.get("format"):
                meta_parts.append(draft["format"])
            score_meta = self._dimension_meta(draft)
            if score_meta:
                meta_parts.append(score_meta)
            if meta_parts:
                lines.append(" · ".join(meta_parts))
            if draft.get("rion_reason"):
                lines.append(draft["rion_reason"])
            if draft.get("source"):
                lines.append(f"来源：{draft['source']}")
            if draft.get("url"):
                lines.append(draft["url"])
            lines.append("")
            lines.append(draft.get("body", ""))
            lines.append("")

    def _append_news_section(
        self, lines: List[str], title: str, items: List[Dict[str, str]]
    ) -> None:
        lines.extend(["━━━━━━━━━━━━━━━━━━", f"{title}（{len(items)}条）", "━━━━━━━━━━━━━━━━━━", ""])
        if not items:
            lines.extend(["暂未抓到可用内容。可以稍后重试，或用 --dry-run 验证本地环境。", ""])
            return

        for index, item in enumerate(items, 1):
            lines.append(f"{index}. {item['title']}")
            source_line = f"来源：{item.get('source', 'N/A')} | {item.get('time', 'N/A')}"
            if item.get("sentiment"):
                source_line += f" | {item['sentiment']}"
            lines.append(source_line)
            for related in item.get("related_links", []):
                if related.get("url"):
                    lines.append(
                        f"相关来源：{related.get('source', '其他来源')} | {related['url']}"
                    )
            meta_parts = []
            if item.get("category"):
                meta_parts.append(item["category"])
            if item.get("tags"):
                meta_parts.append(" / ".join(item["tags"]))
            score_meta = self._dimension_meta(item)
            if score_meta:
                meta_parts.append(score_meta)
            if meta_parts:
                lines.append(" · ".join(meta_parts))
            if item.get("rion_reason"):
                lines.append(item["rion_reason"])
            if item.get("summary_cn"):
                lines.append(item["summary_cn"])
            if item.get("url"):
                lines.append(item["url"])
            lines.append("")

    def _append_project_section(
        self, lines: List[str], projects: List[Dict[str, str]]
    ) -> None:
        lines.extend(["━━━━━━━━━━━━━━━━━━", f"GitHub 优质项目（{len(projects)}条）", "━━━━━━━━━━━━━━━━━━", ""])
        if not projects:
            lines.extend(["暂未抓到 GitHub Trending 内容。可以稍后重试。", ""])
            return

        for index, project in enumerate(projects, 1):
            today = f" | 今日新增 {project['today_stars']}" if project.get("today_stars") else ""
            lines.append(f"{index}. {project['name']}")
            lines.append(
                f"语言：{project.get('language', 'Unknown')} | Stars：{project.get('stars', '0')}{today}"
            )
            meta_parts = []
            if project.get("category"):
                meta_parts.append(project["category"])
            if project.get("tags"):
                meta_parts.append(" / ".join(project["tags"]))
            score_meta = self._dimension_meta(project)
            if score_meta:
                meta_parts.append(score_meta)
            if meta_parts:
                lines.append(" · ".join(meta_parts))
            if project.get("rion_reason"):
                lines.append(project["rion_reason"])
            if project.get("description"):
                lines.append(project["description"])
            if project.get("summary_cn"):
                lines.append(project["summary_cn"])
            if project.get("url"):
                lines.append(project["url"])
            lines.append("")

    def _append_topic_section(self, lines: List[str], topics: List[str]) -> None:
        lines.extend(["━━━━━━━━━━━━━━━━━━", f"今日选题素材（{len(topics)}个）", "━━━━━━━━━━━━━━━━━━", ""])
        for index, topic in enumerate(topics, 1):
            lines.append(f"{index}. {topic}")
            lines.append("")

    def _append_markdown_news(
        self, lines: List[str], title: str, items: List[Dict[str, str]]
    ) -> None:
        lines.extend([f"## {title}", ""])
        if not items:
            lines.extend(["- 暂未抓到可用内容。", ""])
            return

        for index, item in enumerate(items, 1):
            if item.get("url"):
                lines.append(f"{index}. [{item['title']}]({item['url']})")
            else:
                lines.append(f"{index}. {item['title']}")
            source_line = f"   来源：{item.get('source', 'N/A')} | {item.get('time', 'N/A')}"
            if item.get("sentiment"):
                source_line += f" | {item['sentiment']}"
            lines.append(source_line)
            related_links = [
                f"[{related.get('source', '其他来源')}]({related['url']})"
                for related in item.get("related_links", [])
                if related.get("url")
            ]
            if related_links:
                lines.append(f"   相关来源：{' / '.join(related_links)}")
            meta_parts = []
            if item.get("category"):
                meta_parts.append(item["category"])
            if item.get("tags"):
                meta_parts.append(" / ".join(item["tags"]))
            score_meta = self._dimension_meta(item)
            if score_meta:
                meta_parts.append(score_meta)
            if meta_parts:
                lines.append(f"   {' · '.join(meta_parts)}")
            if item.get("rion_reason"):
                lines.append(f"   {item['rion_reason']}")
            if item.get("summary_cn"):
                lines.append(f"   {item['summary_cn']}")
        lines.append("")


def save_output(
    output: str,
    output_format: str,
    output_dir: str,
    output_file: Optional[str] = None,
) -> Path:
    extension = {"text": "txt", "markdown": "md", "json": "json"}.get(
        output_format,
        "txt",
    )
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = (
        Path(output_file)
        if output_file
        else target_dir / f"briefing_{datetime.now():%Y-%m-%d}.{extension}"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(output, encoding="utf-8")
    return path


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Rion's daily AI/Web3 briefing.")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    parser.add_argument(
        "--format",
        choices=["text", "markdown", "json"],
        help="覆盖 config.yaml 中的输出格式",
    )
    parser.add_argument("--output-dir", help="输出目录，默认读取 config.yaml")
    parser.add_argument("--output-file", help="指定完整输出文件路径")
    parser.add_argument("--no-save", action="store_true", help="只打印，不保存文件")
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="不读写跨日 SQLite 历史，适合临时调试",
    )
    parser.add_argument(
        "--editorial-packet",
        action="store_true",
        help="输出供当前 Codex 模型二次精编的 JSON 候选包",
    )
    parser.add_argument(
        "--feedback",
        metavar="ITEM",
        help="按 item_key、链接或标题记录一条内容反馈",
    )
    parser.add_argument(
        "--feedback-action",
        choices=["opened", "saved", "drafted", "published", "dismissed"],
        help="反馈动作：阅读、收藏、写稿、发布或忽略",
    )
    parser.add_argument("--feedback-note", default="", help="可选反馈备注")
    parser.add_argument(
        "--weekly-review",
        action="store_true",
        help="根据历史、反馈和来源健康度生成周复盘",
    )
    parser.add_argument(
        "--weekly-days",
        type=int,
        default=7,
        help="周复盘覆盖天数，默认 7，最多 31",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="使用内置样例数据，不访问外部网站，适合 Codex/CI 验证",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if args.feedback and not args.feedback_action:
        print("--feedback 必须同时指定 --feedback-action", file=sys.stderr)
        return 2
    if args.feedback_action and not args.feedback:
        print("--feedback-action 必须同时指定 --feedback", file=sys.stderr)
        return 2
    if (args.feedback or args.weekly_review) and (args.no_history or args.dry_run):
        print("反馈和周复盘需要启用真实历史数据库", file=sys.stderr)
        return 2

    history_operation = bool(args.feedback or args.weekly_review)
    history_enabled = not (args.no_history or args.dry_run) and (
        history_operation or not args.no_save
    )
    briefing = DailyBriefing(
        config_path=args.config,
        dry_run=args.dry_run,
        history_enabled=history_enabled,
    )
    output_dir = args.output_dir or briefing.config.get("output", {}).get(
        "output_dir", "."
    )

    if args.feedback:
        try:
            result = briefing.record_feedback(
                args.feedback,
                args.feedback_action,
                args.feedback_note,
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            action_labels = {
                "opened": "打开阅读",
                "saved": "收藏",
                "drafted": "写成草稿",
                "published": "已经发布",
                "dismissed": "没价值",
            }
            print(
                f"已记录：{result['title']} → "
                f"{action_labels.get(result['action'], result['action'])}"
            )
        return 0

    if args.weekly_review:
        try:
            data = briefing.generate_weekly_review(args.weekly_days)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        output_format = args.format or "markdown"
        output = briefing.format_weekly_review(data, output_format)
        print(output)
        if not args.no_save:
            extension = "json" if output_format == "json" else "md"
            output_file = args.output_file or str(
                Path(output_dir) / f"weekly_review_{datetime.now():%Y-%m-%d}.{extension}"
            )
            output_path = save_output(
                output,
                output_format,
                output_dir,
                output_file,
            )
            print(f"\n周复盘已保存到: {output_path}", file=sys.stderr)
        return 0

    output_format = (
        "json"
        if args.editorial_packet
        else args.format or briefing.config.get("output", {}).get("format", "text")
    )

    data = briefing.generate_data()
    output = briefing.format_output(data, output_format)
    print(output)

    if not args.no_save:
        output_path = save_output(output, output_format, output_dir, args.output_file)
        print(f"\n早报已保存到: {output_path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
