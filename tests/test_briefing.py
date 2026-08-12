import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup

from briefing import DailyBriefing, save_output
from briefing_store import BriefingStore


class DailyBriefingTests(unittest.TestCase):
    def generate_quietly(self, briefing):
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            return briefing.generate_data()

    def test_dry_run_text_contains_core_sections(self):
        briefing = DailyBriefing(dry_run=True)
        data = self.generate_quietly(briefing)
        output = briefing.format_output(data, "text")

        self.assertIn("Rion 每日早报", output)
        self.assertIn("AI 热点", output)
        self.assertIn("Web3 热点", output)
        self.assertIn("GitHub 优质项目", output)
        self.assertIn("相比昨天的新变化", output)
        self.assertIn("今日必须看", output)
        self.assertIn("B端/商业机会", output)
        self.assertIn("持续跟踪", output)
        self.assertIn("适合发 X 的选题", output)
        self.assertIn("今日选题素材", output)

    def test_json_output_is_valid(self):
        briefing = DailyBriefing(dry_run=True)
        data = self.generate_quietly(briefing)
        output = briefing.format_output(data, "json")
        parsed = json.loads(output)

        self.assertEqual(parsed["metadata"]["title"], "Rion 每日早报")
        self.assertTrue(parsed["metadata"]["dry_run"])
        self.assertIn("ai_news", parsed["sections"])
        self.assertIn("highlights", parsed["sections"])
        self.assertIn("must_read", parsed["sections"])
        self.assertIn("changes", parsed["sections"])
        self.assertIn("business_opportunities", parsed["sections"])
        self.assertIn("watchlist", parsed["sections"])
        self.assertIn("model_releases", parsed["sections"])
        self.assertIn("official_social_updates", parsed["sections"])
        self.assertIn("official_x_watchlist", parsed["sections"])
        self.assertIn("official_model_watchlist", parsed["sections"])
        self.assertIn("official_product_watchlist", parsed["sections"])
        self.assertIn("editorial_queue", parsed["sections"])
        self.assertIn("x_topics", parsed["sections"])
        self.assertIn("x_drafts", parsed["sections"])
        self.assertIn("summary_cn", parsed["sections"]["ai_news"][0])
        self.assertIn("category", parsed["sections"]["ai_news"][0])
        self.assertIn("tags", parsed["sections"]["ai_news"][0])
        self.assertIn("rion_score", parsed["sections"]["ai_news"][0])
        self.assertIn("rion_reason", parsed["sections"]["ai_news"][0])
        self.assertIn("content_value", parsed["sections"]["ai_news"][0])
        self.assertIn("matched_signals", parsed["sections"]["ai_news"][0])
        self.assertIn("overall_score", parsed["sections"]["ai_news"][0])
        self.assertIn("business_score", parsed["sections"]["ai_news"][0])
        self.assertIn("personal_relevance", parsed["sections"]["ai_news"][0])
        self.assertIn("timeliness_score", parsed["sections"]["ai_news"][0])
        self.assertIn("credibility_score", parsed["sections"]["ai_news"][0])
        self.assertEqual(parsed["metadata"]["editorial_mode"], "codex-ready")
        self.assertTrue(
            all(
                item.get("signal_type") != "model_release"
                for item in parsed["sections"]["ai_news"]
            )
        )

    def test_markdown_has_highlights_and_x_topics(self):
        briefing = DailyBriefing(dry_run=True)
        data = self.generate_quietly(briefing)
        markdown = briefing.format_output(data, "markdown")

        self.assertIn("## 相比昨天的新变化", markdown)
        self.assertIn("## 最新模型发布", markdown)
        self.assertIn("## 模型公司官方账号动态", markdown)
        self.assertIn("## 今日必须看", markdown)
        self.assertIn("## 适合发 X 的选题", markdown)
        self.assertIn("## B端/商业机会", markdown)
        self.assertIn("## 持续跟踪", markdown)
        self.assertIn("## X 草稿", markdown)
        self.assertIn("角度：", markdown)
        self.assertIn("形式：", markdown)
        self.assertIn("标签：", markdown)
        self.assertIn("综合 ", markdown)
        self.assertIn("可信 ", markdown)
        self.assertNotIn("Rion 相关度", markdown)
        self.assertIn("## 支持这个项目 / Support the Project", markdown)
        self.assertIn("please consider giving the project a Star", markdown)
        self.assertEqual(
            markdown.count("https://github.com/Rion-Wu-tech/ai-daily-briefing"),
            1,
        )
        self.assertGreaterEqual(len(data["sections"]["highlights"]), 1)
        self.assertGreaterEqual(len(data["sections"]["x_topics"]), 1)
        self.assertGreaterEqual(len(data["sections"]["x_drafts"]), 1)
        self.assertGreaterEqual(len(data["sections"]["model_releases"]), 1)
        self.assertTrue(
            all(
                item["verification"] == "官方确认"
                for item in data["sections"]["model_releases"]
            )
        )

    def test_x_drafts_are_structured_and_copyable(self):
        briefing = DailyBriefing(dry_run=True)
        data = self.generate_quietly(briefing)
        markdown = briefing.format_output(data, "markdown")
        text = briefing.format_output(data, "text")
        drafts = data["sections"]["x_drafts"]

        self.assertGreaterEqual(len(drafts), 1)
        self.assertIn("body", drafts[0])
        self.assertIn("source", drafts[0])
        self.assertIn("url", drafts[0])
        self.assertIn("```text", markdown)
        self.assertIn("X 草稿", text)
        self.assertTrue("AI" in drafts[0]["body"] or "Web3" in drafts[0]["body"])

    def test_x_drafts_keep_source_diversity(self):
        briefing = DailyBriefing(dry_run=True)
        items = []
        for section, name, title, tags in [
            ("ai", "AI 热点", "AI video tool", ["视频/多模态"]),
            ("web3", "Web3 热点", "Bitcoin market signal", ["Web3"]),
            ("github", "GitHub 优质项目", "sample/agent-tool", ["Agent"]),
            ("github", "GitHub 优质项目", "sample/agent-tool-2", ["Agent"]),
        ]:
            items.append(
                {
                    "section": section,
                    "section_name": name,
                    "display_title": title,
                    "url": f"https://example.com/{title}",
                    "category": "Agent / AI 编码" if "Agent" in tags else "AI 行业动态",
                    "tags": tags,
                    "summary_cn": "适合做内容。",
                    "score": 90,
                    "rion_score": 100,
                    "rion_reason": "适合 Rion。",
                    "content_value": "优先跟进",
                }
            )

        drafts = briefing.generate_x_drafts(items)
        sources = {draft["source"] for draft in drafts}

        self.assertIn("AI video tool", sources)
        self.assertIn("Bitcoin market signal", sources)
        self.assertIn("sample/agent-tool", sources)

    def test_personalization_adds_rion_relevance_fields(self):
        briefing = DailyBriefing(dry_run=True)
        project = {
            "name": "sample/codex-agent-workflow",
            "description": "Codex agent workflow toolkit for B2B automation.",
            "language": "Python",
            "stars": "1,000",
            "today_stars": "100 stars today",
            "url": "https://github.com/sample/codex-agent-workflow",
        }

        briefing._enrich_project_item(project)

        self.assertGreaterEqual(project["personal_relevance"], 80)
        self.assertEqual(project["content_value"], "适合发 X")
        self.assertLessEqual(project["overall_score"], 96)
        self.assertIn("Agent / AI 编码", project["matched_signals"])
        self.assertIn("Codex", project["rion_reason"])

    def test_personalized_ranking_can_beat_generic_heat(self):
        briefing = DailyBriefing(dry_run=True)
        hot_generic = {
            "name": "popular/rom-manager",
            "description": "A beautiful app manager and player.",
            "language": "Python",
            "stars": "90,000",
            "today_stars": "2,000 stars today",
            "url": "https://github.com/popular/rom-manager",
        }
        rion_fit = {
            "name": "sample/codex-agent-workflow",
            "description": "Codex agent workflow toolkit for B2B automation.",
            "language": "Python",
            "stars": "2,000",
            "today_stars": "100 stars today",
            "url": "https://github.com/sample/codex-agent-workflow",
        }
        for project in [hot_generic, rion_fit]:
            briefing._enrich_project_item(project)

        items = briefing.all_content_items([], [], [], [hot_generic, rion_fit])
        topics = briefing.generate_x_topics(items)

        self.assertEqual(topics[0]["source"], "sample/codex-agent-workflow")

    def test_highlights_keep_source_diversity(self):
        briefing = DailyBriefing(dry_run=True)
        items = [
            {
                "section": "github",
                "section_name": "GitHub 优质项目",
                "display_title": f"repo-{index}",
                "url": f"https://example.com/repo-{index}",
                "category": "开源生态",
                "tags": ["开源生态"],
                "summary_cn": "GitHub 热门项目。",
                "score": 100 - index,
            }
            for index in range(4)
        ]
        items.extend(
            [
                {
                    "section": "ai",
                    "section_name": "AI 热点",
                    "display_title": "AI browser update",
                    "url": "https://example.com/ai",
                    "category": "产品发布/更新",
                    "tags": ["浏览器"],
                    "summary_cn": "AI 产品入口变化。",
                    "score": 60,
                },
                {
                    "section": "web3",
                    "section_name": "Web3 热点",
                    "display_title": "Bitcoin market update",
                    "url": "https://example.com/web3",
                    "category": "市场动态",
                    "tags": ["Web3"],
                    "summary_cn": "Web3 市场信号变化。",
                    "score": 59,
                },
                {
                    "section": "venture",
                    "section_name": "投资 & 经济",
                    "display_title": "AI startup funding",
                    "url": "https://example.com/venture",
                    "category": "融资并购",
                    "tags": ["融资/IPO"],
                    "summary_cn": "AI 商业化继续被资本关注。",
                    "score": 58,
                },
            ]
        )

        highlights = briefing.generate_highlights(items)
        sections = [item["section"] for item in highlights]

        self.assertLessEqual(sections.count("GitHub 优质项目"), 2)
        self.assertIn("AI 热点", sections)
        self.assertIn("Web3 热点", sections)
        self.assertIn("投资 & 经济", sections)

    def test_project_tags_avoid_common_false_positives(self):
        briefing = DailyBriefing(dry_run=True)
        cases = [
            (
                {
                    "name": "Zackriya-Solutions/meetily",
                    "description": "Meetily is a privacy-first meeting assistant with local transcription.",
                    "language": "TypeScript",
                    "stars": "1,000",
                    "today_stars": "100 stars today",
                    "url": "https://github.com/Zackriya-Solutions/meetily",
                },
                "Meta",
            ),
            (
                {
                    "name": "JuliusBrussee/caveman",
                    "description": "why use many token when few token do trick",
                    "language": "Rust",
                    "stars": "1,000",
                    "today_stars": "100 stars today",
                    "url": "https://github.com/JuliusBrussee/caveman",
                },
                "Web3",
            ),
            (
                {
                    "name": "harvard-edge/cs249r_book",
                    "description": "Open book for machine learning systems.",
                    "language": "Jupyter Notebook",
                    "stars": "1,000",
                    "today_stars": "100 stars today",
                    "url": "https://github.com/harvard-edge/cs249r_book",
                },
                "端侧/硬件",
            ),
        ]

        for project, bad_tag in cases:
            with self.subTest(project=project["name"]):
                briefing._enrich_project_item(project)
                self.assertNotIn(bad_tag, project["tags"])

    def test_x_topics_keep_ai_web3_and_venture_sources(self):
        briefing = DailyBriefing(dry_run=True)
        items = [
            {
                "section": "github",
                "section_name": "GitHub 优质项目",
                "display_title": f"repo-{index}",
                "url": f"https://example.com/repo-{index}",
                "category": "Agent / AI 编码",
                "tags": ["Agent"],
                "summary_cn": "GitHub 热门项目。",
                "score": 100 - index,
            }
            for index in range(4)
        ]
        items.extend(
            [
                {
                    "section": "ai",
                    "section_name": "AI 热点",
                    "display_title": "Mistral model update",
                    "url": "https://example.com/ai",
                    "category": "公司与模型",
                    "tags": ["Mistral"],
                    "summary_cn": "模型公司竞争加速。",
                    "score": 60,
                },
                {
                    "section": "web3",
                    "section_name": "Web3 热点",
                    "display_title": "UK crypto rules",
                    "url": "https://example.com/web3",
                    "category": "政策监管",
                    "tags": ["Web3", "监管"],
                    "summary_cn": "监管正在改变市场预期。",
                    "score": 59,
                },
                {
                    "section": "venture",
                    "section_name": "投资 & 经济",
                    "display_title": "AI startup funding",
                    "url": "https://example.com/venture",
                    "category": "融资并购",
                    "tags": ["融资/IPO"],
                    "summary_cn": "资本继续押注 AI 商业化。",
                    "score": 58,
                },
            ]
        )

        topics = briefing.generate_x_topics(items)
        sources = {topic["source"] for topic in topics}

        self.assertIn("Mistral model update", sources)
        self.assertIn("UK crypto rules", sources)
        self.assertIn("AI startup funding", sources)

    def test_mistral_summary_is_not_overridden_by_openai_competitor_phrase(self):
        briefing = DailyBriefing(dry_run=True)
        item = {
            "title": "What is Mistral AI? Everything to know about the OpenAI competitor",
            "summary": "",
        }

        briefing._enrich_news_item(item, "ai")

        self.assertIn("Mistral", item["summary_cn"])
        self.assertIn("Mistral", item["tags"])
        self.assertIn("模型公司格局", item["rion_reason"])

    def test_regulation_tag_avoids_plain_rules_false_positive(self):
        briefing = DailyBriefing(dry_run=True)
        item = {
            "title": "The new rules of early-stage fundraising",
            "summary": "",
            "source": "Sample",
            "url": "https://example.com/fundraising-rules",
        }

        briefing._enrich_news_item(item, "venture")

        self.assertNotIn("监管", item["tags"])

    def test_anthropic_product_news_not_forced_into_chip_summary(self):
        briefing = DailyBriefing(dry_run=True)
        item = {
            "title": "Anthropic's new Claude feature is quietly selling you on AI",
            "summary": "",
            "source": "Sample",
            "url": "https://example.com/claude-feature",
        }

        briefing._enrich_news_item(item, "ai")

        self.assertIn("Anthropic", item["summary_cn"])
        self.assertNotIn("芯片和算力基础设施", item["summary_cn"])

    def test_outputs_include_chinese_summaries_for_each_item(self):
        briefing = DailyBriefing(dry_run=True)
        data = self.generate_quietly(briefing)
        items = [
            item
            for section in ["ai_news", "web3_news", "venture_news", "github_projects"]
            for item in data["sections"][section]
        ]

        markdown = briefing.format_output(data, "markdown")
        text = briefing.format_output(data, "text")

        self.assertNotIn("中文总结：", markdown)
        self.assertNotIn("中文总结：", text)
        self.assertNotIn("摘要：", markdown)
        self.assertNotIn("摘要：", text)
        self.assertNotIn("一句话介绍：", markdown)
        self.assertNotIn("一句话介绍：", text)
        for item in items:
            self.assertIn(item["summary_cn"], markdown)
            self.assertIn(item["summary_cn"], text)

    def test_config_limits_are_applied(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text(
                "limits:\n"
                "  ai_news: 1\n"
                "  web3_news: 1\n"
                "  venture_news: 1\n"
                "  github_projects: 1\n"
                "  topics: 2\n",
                encoding="utf-8",
            )

            briefing = DailyBriefing(config_path=str(config_path), dry_run=True)
            data = self.generate_quietly(briefing)

        self.assertEqual(len(data["sections"]["ai_news"]), 1)
        self.assertEqual(len(data["sections"]["github_projects"]), 1)
        self.assertEqual(len(data["sections"]["topics"]), 2)

    def test_rss_parser_supports_link_and_guid_fallback(self):
        briefing = DailyBriefing(dry_run=True)
        briefing.config["quality"]["max_feed_age_days"] = 0
        feed = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0"><channel>
          <item>
            <title>OpenAI ships a new agent workflow</title>
            <description><![CDATA[<p>A useful <strong>agent</strong> update.</p>]]></description>
            <link>https://example.com/openai-agent</link>
            <pubDate>Fri, 10 Jul 2026 07:00:00 GMT</pubDate>
          </item>
          <item>
            <title>Hugging Face publishes a model guide</title>
            <description>Model deployment guide.</description>
            <guid>https://example.com/hf-model-guide</guid>
          </item>
        </channel></rss>"""

        rows = briefing._parse_feed_articles(feed, "Official AI", 5)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["url"], "https://example.com/openai-agent")
        self.assertEqual(rows[0]["summary"], "A useful agent update.")
        self.assertEqual(rows[1]["url"], "https://example.com/hf-model-guide")

    def test_official_feed_marks_model_launch_without_marking_enterprise_report(self):
        briefing = DailyBriefing(dry_run=True)
        model = {
            "title": "Introducing GPT-6",
            "summary": "A new frontier model is now available.",
        }
        report = {
            "title": "How enterprises put AI to work",
            "summary": "A report about adoption and workflows.",
        }
        application = {
            "title": "Putting sign language AI into users' hands",
            "summary": "A research model is now available to selected users.",
        }
        program = {
            "title": "Claude for nonprofits",
            "summary": "Anthropic is launching a social impact program.",
        }
        versioned_model = {
            "title": "Gemini 3.1 Pro",
            "summary": "The latest model in the Gemini family.",
        }

        briefing._mark_official_model_release(model)
        briefing._mark_official_model_release(report)
        briefing._mark_official_model_release(application)
        briefing._mark_official_model_release(program)
        briefing._mark_official_model_release(versioned_model)

        self.assertEqual(model["signal_type"], "model_release")
        self.assertTrue(model["official"])
        self.assertEqual(versioned_model["signal_type"], "model_release")
        self.assertNotIn("signal_type", report)
        self.assertNotIn("signal_type", application)
        self.assertNotIn("signal_type", program)

    def test_official_huggingface_org_returns_first_party_model_release(self):
        briefing = DailyBriefing(dry_run=False, history_enabled=False)
        briefing.config["quality"]["model_release_max_age_days"] = 0
        briefing.config["sources"]["official_model_orgs"] = [
            {"name": "Qwen", "author": "Qwen"}
        ]
        briefing._get_json = lambda url, params=None: [
            {
                "id": "Qwen/Qwen-Test-32B",
                "pipeline_tag": "text-generation",
                "likes": 88,
                "createdAt": "2026-08-12T08:00:00Z",
            }
        ]

        rows = briefing.fetch_official_model_orgs(limit_per_org=1)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["signal_type"], "model_release")
        self.assertEqual(rows[0]["release_kind"], "开源权重/模型卡")
        self.assertTrue(rows[0]["official"])
        self.assertEqual(
            rows[0]["url"], "https://huggingface.co/Qwen/Qwen-Test-32B"
        )

    def test_official_watchlists_cover_major_us_and_china_labs(self):
        briefing = DailyBriefing(dry_run=True)

        model_orgs = {
            row["name"]
            for row in briefing.config["sources"]["official_model_orgs"]
        }
        x_accounts = {
            row["name"]: row["handle"]
            for row in briefing.official_x_watchlist()
        }

        self.assertGreaterEqual(len(model_orgs), 42)
        self.assertTrue(
            {"OpenAI", "Microsoft", "NVIDIA", "Qwen", "DeepSeek", "Kimi", "MiniMax"}
            <= model_orgs
        )
        self.assertEqual(x_accounts["OpenAI"], "OpenAI")
        self.assertEqual(x_accounts["Qwen"], "Alibaba_Qwen")
        self.assertEqual(x_accounts["xAI"], "SpaceXAI")
        self.assertEqual(x_accounts["Tencent Hunyuan"], "TencentHunyuan")
        self.assertEqual(x_accounts["Huawei Cloud / Pangu"], "HuaweiCloud1")
        self.assertEqual(x_accounts["Claude"], "ClaudeAI")
        self.assertEqual(x_accounts["Grok"], "grok")
        self.assertEqual(x_accounts["Cursor"], "cursor_ai")
        self.assertEqual(x_accounts["Black Forest Labs"], "bfl_ai")
        self.assertEqual(x_accounts["Cerebras"], "Cerebras")
        self.assertEqual(x_accounts["Ant Ling"], "AntLingAGI")
        self.assertEqual(x_accounts["Wan"], "Alibaba_Wan")
        self.assertGreaterEqual(len(x_accounts), 61)
        product_pages = {
            row["name"] for row in briefing.official_product_page_watchlist()
        }
        self.assertTrue(
            {"Claude Code Changelog", "Cursor Changelog", "Grok Release Notes"}
            <= product_pages
        )

    def test_official_source_config_has_no_duplicates_or_known_unofficial_accounts(self):
        briefing = DailyBriefing(dry_run=True)
        sources = briefing.config["sources"]

        for key, field in (
            ("official_model_orgs", "author"),
            ("official_model_pages", "url"),
            ("official_product_pages", "url"),
            ("official_x_accounts", "handle"),
        ):
            values = [str(row[field]).lower() for row in sources[key]]
            self.assertEqual(len(values), len(set(values)), key)

        handles = {
            row["handle"].lower() for row in sources["official_x_accounts"]
        }
        self.assertNotIn("claude_code", handles)
        self.assertNotIn("bfl_ml", handles)
        self.assertNotIn("inclusionai", handles)

    def test_official_x_api_updates_keep_direct_post_links(self):
        briefing = DailyBriefing(dry_run=False, history_enabled=False)
        briefing.config["sources"]["official_x_accounts"] = [
            {"name": "OpenAI", "handle": "OpenAI", "country": "US"}
        ]

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "data": [
                        {
                            "id": "123",
                            "author_id": "1",
                            "created_at": "2026-08-13T01:00:00Z",
                            "text": "Codex now supports a faster review workflow.",
                            "public_metrics": {
                                "like_count": 100,
                                "retweet_count": 10,
                            },
                        }
                    ],
                    "includes": {
                        "users": [
                            {"id": "1", "name": "OpenAI", "username": "OpenAI"}
                        ]
                    },
                }

        briefing.session.get = lambda *args, **kwargs: Response()
        with patch.dict(os.environ, {"X_BEARER_TOKEN": "test-token"}):
            rows = briefing.fetch_official_x_updates()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["signal_type"], "official_social")
        self.assertEqual(rows[0]["url"], "https://x.com/OpenAI/status/123")
        self.assertTrue(rows[0]["official"])

    def test_qwen_changelog_parser_keeps_qwen_and_excludes_third_party_models(self):
        briefing = DailyBriefing(dry_run=True)
        briefing.config["quality"]["model_release_max_age_days"] = 0
        soup = BeautifulSoup(
            """
            <main>
              <div>August 12, 2026</div>
              <h3 id="qwen-test">qwen-test-32b</h3>
              <p>A new Qwen model with tool use.</p>
              <h3 id="glm-test">ZHIPU/GLM-Test</h3>
              <p>A third-party model is available.</p>
            </main>
            """,
            "html.parser",
        )
        config = {
            "name": "QwenCloud",
            "url": "https://docs.qwencloud.com/changelog/models",
            "include_prefixes": ["qwen", "wan"],
        }

        rows = briefing._parse_qwen_model_changelog(soup, config, 5)

        self.assertEqual(len(rows), 1)
        self.assertIn("qwen-test-32b", rows[0]["title"])
        self.assertEqual(rows[0]["published_at"], "2026-08-12T00:00:00+00:00")
        self.assertTrue(rows[0]["official"])

    def test_mistral_changelog_parser_only_keeps_model_release_blocks(self):
        briefing = DailyBriefing(dry_run=True)
        briefing.config["quality"]["model_release_max_age_days"] = 0
        soup = BeautifulSoup(
            """
            <main>
              <h3>Aug 26</h3>
              <h2>August 12</h2>
              <p>We released Mistral Test (mistral-test).</p>
              <span>MODEL RELEASED</span>
              <h2>August 11</h2>
              <p>We updated the dashboard.</p>
              <span>OTHER</span>
            </main>
            """,
            "html.parser",
        )
        config = {
            "name": "Mistral AI",
            "url": "https://docs.mistral.ai/resources/changelogs",
        }

        rows = briefing._parse_mistral_model_changelog(soup, config, 5)

        self.assertEqual(len(rows), 1)
        self.assertIn("Mistral Test", rows[0]["title"])
        self.assertEqual(rows[0]["release_kind"], "模型发布")

    def test_ai_relevance_filter_removes_unrelated_venture_story(self):
        briefing = DailyBriefing(dry_run=True)

        self.assertFalse(
            briefing._is_ai_relevant(
                {
                    "title": "Nandan Nilekani launches a $200M third fund",
                    "summary": "The venture firm will back consumer startups.",
                    "source": "TechCrunch",
                }
            )
        )
        self.assertTrue(
            briefing._is_ai_relevant(
                {
                    "title": "Ollama raises $65M for its open source AI developer tool",
                    "summary": "The company is building local model tooling.",
                    "source": "TechCrunch",
                }
            )
        )

    def test_similar_news_titles_are_clustered_with_related_link(self):
        briefing = DailyBriefing(dry_run=True)
        rows = briefing._dedupe_items(
            [
                {
                    "title": "OpenAI launches new agent tools for developers",
                    "url": "https://official.example.com/agent-tools",
                    "source": "OpenAI",
                    "summary": "Official announcement.",
                },
                {
                    "title": "OpenAI launches new agent tools for developers today",
                    "url": "https://media.example.com/openai-agent-tools",
                    "source": "Tech Media",
                    "summary": "Media report.",
                },
            ]
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "OpenAI / Tech Media")
        self.assertEqual(len(rows[0]["related_links"]), 1)

    def test_same_product_event_clusters_media_and_official_wording(self):
        briefing = DailyBriefing(dry_run=True)
        media = {
            "title": "OpenAI says GPT 5.6 is the preferred model for Microsoft Copilot 365 amid breakup chatter",
            "url": "https://media.example.com/gpt-copilot",
            "source": "Tech Media",
        }
        official = {
            "title": "GPT-5.6 is now the preferred model in Microsoft 365 Copilot",
            "url": "https://official.example.com/gpt-copilot",
            "source": "OpenAI",
        }

        self.assertTrue(briefing._items_duplicate(media, official))
        self.assertFalse(
            briefing._items_duplicate(
                {
                    "title": "OpenAI launches GPT-5.6",
                    "url": "https://media.example.com/gpt-launch",
                },
                official,
            )
        )

    def test_cross_section_dedup_uses_best_matching_section(self):
        briefing = DailyBriefing(dry_run=True)
        ai_item = {
            "title": "Startup raises a new $200M venture fund",
            "url": "https://example.com/fund?utm_source=newsletter",
            "source": "TechCrunch",
            "summary": "A venture capital fundraising story.",
        }
        venture_item = {
            "title": "Startup raises a new $200M venture fund",
            "url": "https://example.com/fund",
            "source": "Venture Media",
            "summary": "A venture capital fundraising story.",
        }

        sections = briefing._dedupe_news_sections([ai_item], [], [venture_item])

        self.assertEqual(sections["ai"], [])
        self.assertEqual(len(sections["venture"]), 1)
        self.assertEqual(
            sections["venture"][0]["source"],
            "Venture Media / TechCrunch",
        )

    def test_round_robin_keeps_source_diversity(self):
        briefing = DailyBriefing(dry_run=True)
        groups = [
            [{"source": "Media", "title": f"M{index}"} for index in range(3)],
            [{"source": "Official", "title": f"O{index}"} for index in range(3)],
        ]

        rows = briefing._round_robin(groups, 4)

        self.assertEqual(
            [row["source"] for row in rows],
            ["Media", "Official", "Media", "Official"],
        )

    def test_save_output_creates_expected_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_output("hello", "markdown", tmpdir)

            self.assertEqual(path.suffix, ".md")
            self.assertEqual(path.read_text(encoding="utf-8"), "hello")

    def test_x_drafts_cover_three_content_shapes(self):
        briefing = DailyBriefing(dry_run=True)
        data = self.generate_quietly(briefing)

        formats = [draft["format"] for draft in data["sections"]["x_drafts"]]

        self.assertEqual(formats, ["单帖", "thread", "视觉/视频脚本"])

    def test_source_tiers_distinguish_official_multi_and_aggregated(self):
        briefing = DailyBriefing(dry_run=True)
        official = briefing._source_profile({"source": "OpenAI"})
        multi = briefing._source_profile(
            {
                "source": "TechCrunch / CoinDesk",
                "related_links": [],
            }
        )
        trending = briefing._source_profile(
            {"source": "Hugging Face Trending"}
        )

        self.assertEqual(official["verification"], "官方确认")
        self.assertEqual(multi["verification"], "多源印证")
        self.assertEqual(multi["source_count"], 2)
        self.assertEqual(trending["verification"], "单源信号")
        self.assertLess(trending["credibility_score"], official["credibility_score"])

    def test_history_store_tracks_cross_day_rank_without_rerun_inflation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = BriefingStore(str(Path(tmpdir) / "history.sqlite3"))
            day_one_item = {
                "item_key": "https://example.com/agent",
                "display_title": "Agent update",
                "url": "https://example.com/agent",
                "section": "ai",
                "source": "Sample",
                "overall_score": 78,
                "source_count": 1,
            }
            store.annotate_items([day_one_item], "2026-07-12")
            self.assertEqual(day_one_item["history_status"], "首次出现")
            store.record_items([day_one_item], "2026-07-12")
            store.record_items([day_one_item], "2026-07-12")
            same_day_item = dict(day_one_item)
            store.annotate_items([same_day_item], "2026-07-12")
            self.assertEqual(same_day_item["history_status"], "首次出现")
            self.assertEqual(same_day_item["repeat_count"], 0)

            day_two_item = dict(day_one_item)
            day_two_item.update({"overall_score": 86, "source_count": 2})
            store.annotate_items([day_two_item], "2026-07-13")
            store.record_items([day_two_item], "2026-07-13")

            self.assertEqual(day_two_item["repeat_count"], 1)
            self.assertEqual(day_two_item["history_status"], "持续升温")
            self.assertEqual(day_two_item["score_delta"], 8)
            history = store.rank_history(day_two_item["item_key"])
            self.assertEqual(len(history), 2)
            self.assertEqual([row["rank"] for row in history], [1, 1])

    def test_aihot_parser_uses_current_server_rendered_cards(self):
        briefing = DailyBriefing(dry_run=False, history_enabled=False)
        html = """
        <article>
          <h3>OpenAI 发布新的开发者功能</h3>
          <p>面向开发者的真实更新。</p>
          <img alt="TechInAsia" />
        </article>
        """
        briefing._get_soup = lambda url: BeautifulSoup(html, "html.parser")

        rows = briefing.fetch_aihot(limit=1)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "AI HOT · TechInAsia")
        self.assertIn("item=", rows[0]["url"])

    def test_hn_and_huggingface_api_parsers_keep_ranking_signals(self):
        briefing = DailyBriefing(dry_run=False, history_enabled=False)
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        def fake_json(url, params=None):
            if "algolia" in url:
                return {
                    "hits": [
                        {
                            "title": "AI agent workflow release",
                            "url": "https://example.com/agent-release",
                            "points": 128,
                            "num_comments": 42,
                            "created_at": now,
                            "objectID": "123",
                        }
                    ]
                }
            return [
                {
                    "id": "sample/model",
                    "pipeline_tag": "text-generation",
                    "likes": 88,
                    "trendingScore": 123,
                    "createdAt": now,
                }
            ]

        briefing._get_json = fake_json
        hn_rows = briefing.fetch_hacker_news(limit=1)
        hf_rows = briefing.fetch_huggingface_models(limit=1)

        self.assertEqual(hn_rows[0]["popularity"], 128)
        self.assertIn("42 条讨论", hn_rows[0]["summary"])
        self.assertEqual(hf_rows[0]["popularity"], 123)
        self.assertEqual(hf_rows[0]["source"], "Hugging Face Trending")

    def test_editorial_queue_preserves_facts_links_and_dimensions(self):
        briefing = DailyBriefing(dry_run=True)
        data = self.generate_quietly(briefing)
        queue = data["sections"]["editorial_queue"]

        self.assertGreaterEqual(len(queue), 1)
        self.assertTrue(queue[0]["url"].startswith("http"))
        self.assertIn("raw_summary", queue[0])
        self.assertIn("editorial_hint", queue[0])
        self.assertIn("credibility_score", queue[0])
        self.assertEqual(
            {item["section_key"] for item in queue},
            {"ai", "web3", "venture", "github"},
        )
        self.assertTrue(
            any(item.get("signal_type") == "model_release" for item in queue)
        )

    def test_feedback_updates_future_ranking_with_bounded_adjustment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = BriefingStore(str(Path(tmpdir) / "feedback.sqlite3"))
            published_item = {
                "item_key": "https://example.com/published-agent",
                "display_title": "Published agent workflow",
                "url": "https://example.com/published-agent",
                "section": "ai",
                "source": "Agent Source",
                "category": "Agent / AI 编码",
                "tags": ["Agent"],
                "matched_signals": ["Agent / AI 编码"],
                "overall_score": 80,
                "source_count": 1,
            }
            store.record_items([published_item], "2026-08-01")
            store.record_feedback(
                published_item["item_key"],
                "published",
                created_at="2026-08-02T08:00:00+00:00",
            )

            future_item = {
                "item_key": "https://example.com/new-agent",
                "source": "Agent Source",
                "category": "Agent / AI 编码",
                "overall_score": 70,
                "rion_score": 70,
            }
            store.apply_feedback([future_item])

            self.assertGreater(future_item["overall_score"], 70)
            self.assertLessEqual(future_item["feedback_score"], 12)
            self.assertIn("来源", future_item["feedback_reason"])
            self.assertIn("类别", future_item["feedback_reason"])

    def test_dismissed_feedback_can_lower_exact_item_score(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = BriefingStore(str(Path(tmpdir) / "feedback.sqlite3"))
            item = {
                "item_key": "https://example.com/noise",
                "display_title": "Noisy story",
                "url": "https://example.com/noise",
                "section": "ai",
                "source": "Noise Source",
                "category": "AI 行业动态",
                "overall_score": 72,
                "source_count": 1,
            }
            store.record_items([item], "2026-08-01")
            store.record_feedback(
                item["item_key"],
                "dismissed",
                created_at="2026-08-02T08:00:00+00:00",
            )
            candidate = dict(item)
            candidate["rion_score"] = 72
            store.apply_feedback([candidate])

            self.assertLess(candidate["overall_score"], 72)
            self.assertGreaterEqual(candidate["feedback_score"], -12)

    def test_weekly_review_combines_items_feedback_and_source_health(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = BriefingStore(str(Path(tmpdir) / "weekly.sqlite3"))
            item = {
                "item_key": "https://example.com/weekly-agent",
                "display_title": "Weekly agent update",
                "url": "https://example.com/weekly-agent",
                "section": "ai",
                "source": "OpenAI",
                "category": "Agent / AI 编码",
                "overall_score": 84,
                "source_count": 1,
            }
            store.record_items([item], "2026-08-02", [item["item_key"]])
            item["overall_score"] = 87
            store.record_items([item], "2026-08-03", [item["item_key"]])
            store.record_feedback(
                item["item_key"],
                "saved",
                created_at="2026-08-03T09:00:00+00:00",
            )
            store.record_source_runs(
                "2026-08-02",
                [
                    {
                        "source": "OpenAI",
                        "status": "ok",
                        "item_count": 3,
                        "latency_ms": 120,
                    }
                ],
            )
            store.record_source_runs(
                "2026-08-03",
                [
                    {
                        "source": "OpenAI",
                        "status": "error",
                        "item_count": 0,
                        "error": "timeout",
                        "latency_ms": 500,
                    }
                ],
            )

            summary = store.weekly_summary(days=7, end_date="2026-08-08")
            briefing = DailyBriefing(dry_run=True)
            review = {
                "metadata": {
                    "title": "Rion AI 简报周复盘",
                    "generated_at": "2026-08-08T10:00:00",
                },
                **summary,
            }
            markdown = briefing.format_weekly_review(review, "markdown")

            self.assertEqual(summary["top_items"][0]["days_seen"], 2)
            self.assertEqual(summary["feedback"]["saved"], 1)
            self.assertEqual(summary["source_health"][0]["success_rate"], 50)
            self.assertIn("## 来源健康度", markdown)
            self.assertIn("检查不稳定来源：OpenAI", markdown)

    def test_existing_history_database_is_migrated_in_place(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "legacy.sqlite3"
            with sqlite3.connect(path) as connection:
                connection.execute(
                    """
                    CREATE TABLE items (
                        item_key TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        url TEXT NOT NULL DEFAULT '',
                        section TEXT NOT NULL DEFAULT '',
                        source TEXT NOT NULL DEFAULT '',
                        first_seen TEXT NOT NULL,
                        last_seen TEXT NOT NULL,
                        seen_count INTEGER NOT NULL DEFAULT 1,
                        selected_count INTEGER NOT NULL DEFAULT 0,
                        last_score INTEGER NOT NULL DEFAULT 0,
                        source_count INTEGER NOT NULL DEFAULT 1
                    )
                    """
                )

            BriefingStore(str(path))

            with sqlite3.connect(path) as connection:
                item_columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(items)")
                }
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
            self.assertTrue({"category", "tags_json", "signals_json"} <= item_columns)
            self.assertTrue({"feedback", "source_runs"} <= tables)


if __name__ == "__main__":
    unittest.main()
