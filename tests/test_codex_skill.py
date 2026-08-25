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
        self.assertIn("Immediately below every retained news", skill)
        self.assertIn("every linked item is immediately followed", metadata)
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
        self.assertIn("## 今日必须看", result.stdout)
        self.assertIn("## 产品与工具更新", result.stdout)
        self.assertIn("## AI 产业链全景", result.stdout)
        self.assertIn("## 应用层趋势", result.stdout)
        self.assertIn("## AI 投融资与商业化", result.stdout)
        self.assertIn("## 可能爆火的 AI 新闻", result.stdout)
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
        self.assertIn("## AI 产业链全景", result.stdout)
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
                "1. [Claude Code 更新](https://example.com/release)\n"
                "   Anthropic 修复了 MCP OAuth 重定向错误，Slack 等预注册客户端可以恢复登录。\n"
                "   `官方确认`\n",
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


if __name__ == "__main__":
    unittest.main()
