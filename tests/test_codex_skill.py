import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "daily-briefing"


class CodexSkillTests(unittest.TestCase):
    def test_skill_has_codex_metadata(self):
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        metadata = (SKILL_DIR / "agents" / "openai.yaml").read_text(
            encoding="utf-8"
        )

        self.assertTrue(skill.startswith("---\nname: daily-briefing\n"))
        self.assertIn("Generate a source-linked Chinese AI/Web3", skill)
        self.assertIn("**发生了什么：**", skill)
        self.assertIn("**关键细节：**", skill)
        self.assertIn("**为什么重要：**", skill)
        self.assertIn("global event ledger", skill)
        self.assertIn("exactly one primary section", skill)
        self.assertIn("Make every story understandable", metadata)
        self.assertIn("$daily-briefing", metadata)

    def test_compatibility_skill_matches_current_counts_and_validation(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("19 个基础模型发布页", skill)
        self.assertIn("62 个中美模型公司", skill)
        self.assertIn("validate-briefing.py", skill)

    def test_runner_is_portable(self):
        runner = SKILL_DIR / "scripts" / "run-daily-briefing.sh"
        source = runner.read_text(encoding="utf-8")

        self.assertTrue(os.access(runner, os.X_OK))
        self.assertNotIn("/Users/rion", source)
        self.assertIn("DAILY_BRIEFING_PROJECT", source)
        self.assertIn("ai-daily-briefing.git", source)

    def test_runner_generates_markdown_in_dry_run(self):
        runner = SKILL_DIR / "scripts" / "run-daily-briefing.sh"
        result = subprocess.run(
            ["bash", str(runner), "--dry-run", "--no-save"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("# Rion 每日早报", result.stdout)
        self.assertIn("## 产品与工具更新", result.stdout)
        self.assertIn("## AI 产业链概览", result.stdout)
        self.assertIn("## 应用层趋势", result.stdout)
        self.assertIn("## AI 投融资与商业化", result.stdout)
        self.assertIn("## 可能爆火的 AI 新闻", result.stdout)
        self.assertNotIn("## 今日必须看", result.stdout)
        self.assertNotIn("## 相比昨天的新变化", result.stdout)
        self.assertNotRegex(result.stdout, r"\bE\d{2}\b")
        self.assertIn("**发生了什么：**", result.stdout)
        self.assertIn("**关键细节：**", result.stdout)
        self.assertIn("**为什么重要：**", result.stdout)
        self.assertIn("**来源与评分：**", result.stdout)
        self.assertIn("](", result.stdout)

    def test_runner_supports_targeted_briefings(self):
        runner = SKILL_DIR / "scripts" / "run-daily-briefing.sh"
        result = subprocess.run(
            [
                "bash",
                str(runner),
                "--dry-run",
                "--no-save",
                "--mode",
                "hotspots",
                "--focus",
                "Agent",
                "--hours",
                "48",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("方向：`Agent`", result.stdout)
        self.assertIn("时间：过去 `48` 小时", result.stdout)

    def test_runner_supports_industry_briefing(self):
        runner = SKILL_DIR / "scripts" / "run-daily-briefing.sh"
        result = subprocess.run(
            [
                "bash",
                str(runner),
                "--dry-run",
                "--no-save",
                "--mode",
                "industry",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("## AI 产业链概览", result.stdout)
        self.assertIn("## 产业链联动", result.stdout)
        self.assertIn("## 应用层趋势", result.stdout)
        self.assertIn("## AI 投融资与商业化", result.stdout)

    def test_markdown_to_html_renderer_is_portable(self):
        renderer = SKILL_DIR / "scripts" / "render-briefing-html.py"
        source = renderer.read_text(encoding="utf-8")

        self.assertTrue(os.access(renderer, os.X_OK))
        self.assertNotIn("/Users/rion", source)
        self.assertIn("briefing_html", source)
        self.assertIn("DAILY_BRIEFING_PROJECT", source)
        self.assertIn("daily-briefing-runtime", source)

        with tempfile.TemporaryDirectory() as tmpdir:
            markdown = Path(tmpdir) / "briefing.md"
            output = Path(tmpdir) / "briefing.html"
            markdown.write_text(
                "# AI 简报\n\n## 今日必须看\n\n"
                "1. [官方更新](https://example.com)\n\n"
                "   示例公司发布了新功能。\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    str(ROOT / ".venv" / "bin" / "python"),
                    str(renderer),
                    str(markdown),
                    "--output-file",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output.is_file())
            self.assertIn("briefing-search", output.read_text(encoding="utf-8"))

    def test_summary_validator_accepts_specific_chinese_explanation(self):
        validator = SKILL_DIR / "scripts" / "validate-briefing.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            markdown = Path(tmpdir) / "briefing.md"
            markdown.write_text(
                "# 简报\n\n"
                "1. [Claude Code 更新](https://example.com/release)\n\n"
                "    **发生了什么：** Anthropic 发布 Claude Code 更新，修复 MCP OAuth 重定向错误并恢复预注册客户端登录。\n\n"
                "    **关键细节：** 修复覆盖 Slack 等客户端；OAuth 回调现在会回到原始会话；已有配置无需重新创建。\n\n"
                "    **为什么重要：** 这能减少企业接入 MCP 服务时的登录中断，降低开发团队排查认证问题的时间。\n\n"
                "    **来源与评分：** Anthropic · 官方确认\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                ["python3", str(validator), str(markdown)],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("检查通过", result.stdout)

    def test_summary_validator_rejects_shallow_headline_card(self):
        validator = SKILL_DIR / "scripts" / "validate-briefing.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            markdown = Path(tmpdir) / "briefing.md"
            markdown.write_text(
                "# 简报\n\n"
                "1. [产品更新](https://example.com/product)\n"
                "   示例公司发布了一项新功能。\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                ["python3", str(validator), str(markdown)],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("缺少“发生了什么”", result.stderr)
        self.assertIn("缺少“关键细节”", result.stderr)
        self.assertIn("缺少“为什么重要”", result.stderr)

    def test_summary_validator_rejects_missing_or_generic_explanation(self):
        validator = SKILL_DIR / "scripts" / "validate-briefing.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            markdown = Path(tmpdir) / "briefing.md"
            markdown.write_text(
                "# 简报\n\n"
                "1. [产品更新](https://example.com/product)\n"
                "   来源：示例公司\n\n"
                "2. [行业新闻](https://example.com/news)\n"
                "   这条围绕行业新闻展开，可作为 AI 行业观察。\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                ["python3", str(validator), str(markdown)],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("只有元数据", result.stderr)
        self.assertIn("过于空泛", result.stderr)

    def test_summary_validator_rejects_duplicate_canonical_urls_and_titles(self):
        validator = SKILL_DIR / "scripts" / "validate-briefing.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            markdown = Path(tmpdir) / "briefing.md"
            markdown.write_text(
                "# 简报\n\n"
                "## 模型更新\n\n"
                "1. [Wan 3.0 公开可用](https://example.com/wan?utm_source=x)\n"
                "   QwenCloud 将 Wan 3.0 从邀请测试转为公开 API。\n\n"
                "## 今日必须看\n\n"
                "1. [Wan 3.0 公开可用](https://example.com/wan)\n"
                "   QwenCloud 的视频模型现在面向全部开发者开放。\n\n"
                "2. [另一个重复标题](https://example.com/a)\n"
                "   示例公司发布了一个新功能。\n\n"
                "3. [另一个重复标题](https://example.com/b)\n"
                "   另一来源再次描述同一项功能。\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                ["python3", str(validator), str(markdown)],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("重复链接", result.stderr)
        self.assertIn("重复标题", result.stderr)

    def test_summary_validator_rejects_internal_ids_and_empty_sections(self):
        validator = SKILL_DIR / "scripts" / "validate-briefing.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            markdown = Path(tmpdir) / "briefing.md"
            markdown.write_text(
                "# 简报\n\n"
                "## 今日必须看\n\n"
                "- **E01（主栏目：产品与工具更新）** · 优先级 01\n\n"
                "## Web3 热点\n\n"
                "- 本轮没有符合条件的独立事件。\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                ["python3", str(validator), str(markdown)],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("内部事件编号", result.stderr)
        self.assertIn("空栏目占位", result.stderr)


if __name__ == "__main__":
    unittest.main()
