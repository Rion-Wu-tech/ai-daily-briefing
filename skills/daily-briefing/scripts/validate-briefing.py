#!/usr/bin/env python3
"""Validate that linked briefing items have useful Chinese explanations."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


ITEM_RE = re.compile(
    r"^\s*(?:\d+\.|-)\s+\[(?P<title>[^\]]+)\]\((?P<url>https?://[^)]+)\)"
)
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
TRACKING_PARAMETERS = {"ref", "source", "campaign", "fbclid", "gclid"}
VISIBLE_STORY_ID_RE = re.compile(
    r"^\s*(?:#{1,6}\s+)?(?:\d+\.\s+|[-*+]\s+)?(?:\*\*)?E\d{2,}(?:\b|（)",
    re.IGNORECASE,
)
EMPTY_SECTION_PLACEHOLDERS = (
    "本轮没有符合条件的独立事件",
    "本轮没有新增的派生信号",
    "本轮暂无高置信度更新",
    "今天没有符合条件的条目",
    "暂未生成选题",
    "暂未生成 X 草稿",
)
REQUIRED_STORY_LABELS = ("发生了什么", "关键细节", "为什么重要")
MIN_STORY_CHINESE_CHARS = 70


def canonical_url(value: str) -> str:
    parts = urlsplit(value.strip())
    query = [
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
        and key.lower() not in TRACKING_PARAMETERS
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


def normalized_title(value: str) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", value.lower())


def _next_content_line(lines: list[str], start: int) -> tuple[int, str]:
    for index in range(start, len(lines)):
        value = lines[index].strip()
        if value:
            return index + 1, value
    return len(lines), ""


def _item_block(lines: list[str], start: int) -> list[str]:
    block: list[str] = []
    for line in lines[start:]:
        if ITEM_RE.match(line) or re.match(r"^\s*##\s+", line):
            break
        block.append(line)
    return block


def _labeled_story_values(block: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in block:
        match = re.match(
            r"^\s*\*\*(发生了什么|关键细节|为什么重要|待确认|来源与评分)：\*\*\s*(.*)$",
            line,
        )
        if match:
            values[match.group(1)] = match.group(2).strip()
    return values


def inspect_markdown(text: str) -> tuple[list[str], int]:
    lines = text.splitlines()
    errors: list[str] = []
    in_code_block = False
    seen_urls: dict[str, int] = {}
    seen_titles: dict[str, int] = {}
    linked_item_count = 0

    for index, line in enumerate(lines):
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if not in_code_block and VISIBLE_STORY_ID_RE.match(line):
            errors.append(
                f"第 {index + 1} 行暴露了内部事件编号；请删除编号索引并保留可独立阅读的内容"
            )
        if not in_code_block:
            placeholder = next(
                (phrase for phrase in EMPTY_SECTION_PLACEHOLDERS if phrase in line),
                "",
            )
            if placeholder:
                errors.append(
                    f"第 {index + 1} 行是空栏目占位（命中“{placeholder}”）；请省略整个栏目"
                )
        match = ITEM_RE.match(line)
        if in_code_block or not match:
            continue

        linked_item_count += 1
        current_line = index + 1
        url_key = canonical_url(match.group("url"))
        title_key = normalized_title(match.group("title"))
        if url_key in seen_urls:
            errors.append(
                f"第 {current_line} 行重复链接；首次出现在第 {seen_urls[url_key]} 行：{url_key}"
            )
        else:
            seen_urls[url_key] = current_line
        if title_key in seen_titles:
            errors.append(
                f"第 {current_line} 行重复标题；首次出现在第 {seen_titles[title_key]} 行：{match.group('title')}"
            )
        else:
            seen_titles[title_key] = current_line

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

        story_values = _labeled_story_values(_item_block(lines, index + 1))
        for label in REQUIRED_STORY_LABELS:
            if not story_values.get(label):
                errors.append(
                    f"第 {index + 1} 行缺少“{label}”内容，读者仍需打开原文才能理解：{title}"
                )
        if all(story_values.get(label) for label in REQUIRED_STORY_LABELS):
            narrative = " ".join(
                story_values[label] for label in REQUIRED_STORY_LABELS
            )
            chinese_char_count = len(CHINESE_RE.findall(narrative))
            if chinese_char_count < MIN_STORY_CHINESE_CHARS:
                errors.append(
                    f"第 {index + 1} 行正文信息量不足（中文信息 {chinese_char_count} 字，"
                    f"至少需要 {MIN_STORY_CHINESE_CHARS} 字）：{title}"
                )
            generic_depth = next(
                (
                    phrase
                    for phrase in GENERIC_EXPLANATIONS
                    if phrase in narrative
                ),
                "",
            )
            if generic_depth and generic_depth != generic:
                errors.append(
                    f"第 {index + 1} 行深摘要仍过于空泛（命中“{generic_depth}”）：{title}"
                )

    return errors, linked_item_count


def validate_markdown(text: str) -> list[str]:
    errors, _ = inspect_markdown(text)
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

    errors, linked_item_count = inspect_markdown(
        path.read_text(encoding="utf-8")
    )
    if errors:
        print("早报概括检查未通过：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        f"早报概括与去重检查通过：{path} · "
        f"独立链接 {linked_item_count} 条 · 唯一链接率 100%"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
