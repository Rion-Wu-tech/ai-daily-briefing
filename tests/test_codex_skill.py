import os
import subprocess
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
        self.assertIn("$daily-briefing", metadata)

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
        self.assertIn("](", result.stdout)


if __name__ == "__main__":
    unittest.main()
