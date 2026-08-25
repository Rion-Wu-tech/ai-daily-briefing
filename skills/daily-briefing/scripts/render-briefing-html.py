#!/usr/bin/env python3
"""Convert a finalized Daily Briefing Markdown file to interactive HTML."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def project_root() -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    candidates = [
        Path(os.environ["DAILY_BRIEFING_PROJECT"])
        if os.environ.get("DAILY_BRIEFING_PROJECT")
        else None,
        Path.cwd(),
        Path(__file__).resolve().parents[3],
        codex_home / "daily-briefing-runtime",
    ]
    for candidate in candidates:
        if candidate and (candidate / "briefing_html.py").is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        "找不到 briefing_html.py。请在 ai-daily-briefing 仓库内运行，"
        "或设置 DAILY_BRIEFING_PROJECT。"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="把最终 Markdown 早报转换成可搜索、筛选和收藏的单文件 HTML。"
    )
    parser.add_argument("markdown_file", help="输入 Markdown 文件")
    parser.add_argument("--output-file", help="输出 HTML 文件，默认与输入同名")
    parser.add_argument("--title", help="可选页面标题；默认读取 Markdown 一级标题")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        root = project_root()
        sys.path.insert(0, str(root))
        from briefing_html import render_markdown_file

        input_path = Path(args.markdown_file)
        output_path = Path(args.output_file) if args.output_file else None
        target = render_markdown_file(
            input_path,
            output_path,
            page_title=args.title,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"交互 HTML 已保存到：{target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
