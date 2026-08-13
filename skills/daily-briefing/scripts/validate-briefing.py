#!/usr/bin/env python3
"""Validate that linked briefing items have useful Chinese explanations."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ITEM_RE = re.compile(r"^\s*(?:\d+\.|-)\s+\[[^\]]+\]\(https?://[^)]+\)")
CHINESE_RE = re.compile(r"[\u3400-\u9fff]")
METADATA_PREFIXES = (
    "来源：",
    "相关来源：",
    "形式：",
    "标签：",
    "项目地址",
)
GENERIC_EXPLANATIONS = (
    "值得关注",
    "可作为 AI 行业观察",
    "可作为行业观察",
    "可作为 AI 行业动态",
    "核心看点是工具链还没完全成熟",
    "这条围绕",
)


def _next_content_line(lines: list[str], start: int) -> tuple[int, str]:
    for index in range(start, len(lines)):
        value = lines[index].strip()
        if value:
            return index + 1, value
    return len(lines), ""


def validate_markdown(text: str) -> list[str]:
    lines = text.splitlines()
    errors: list[str] = []
    in_code_block = False

    for index, line in enumerate(lines):
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block or not ITEM_RE.match(line):
            continue

        next_line_number, explanation = _next_content_line(lines, index + 1)
        title = re.sub(r"^\s*(?:\d+\.|-)\s+", "", line).strip()
        if not explanation:
            errors.append(f"第 {index + 1} 行条目缺少中文概括：{title}")
            continue
        if not CHINESE_RE.search(explanation):
            errors.append(
                f"第 {index + 1} 行条目后的第 {next_line_number} 行不是中文概括：{title}"
            )
            continue
        if explanation.startswith(METADATA_PREFIXES) or explanation.startswith("`"):
            errors.append(
                f"第 {index + 1} 行条目后只有元数据，没有中文概括：{title}"
            )
            continue
        generic = next(
            (phrase for phrase in GENERIC_EXPLANATIONS if phrase in explanation),
            "",
        )
        if generic:
            errors.append(
                f"第 {index + 1} 行概括过于空泛（命中“{generic}”）：{title}"
            )

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate Chinese explanations in a Markdown briefing."
    )
    parser.add_argument("markdown_file", help="Markdown briefing to validate")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = Path(args.markdown_file).expanduser()
    if not path.is_file():
        print(f"找不到 Markdown 文件：{path}", file=sys.stderr)
        return 2

    errors = validate_markdown(path.read_text(encoding="utf-8"))
    if errors:
        print("早报概括检查未通过：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"早报概括检查通过：{path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
