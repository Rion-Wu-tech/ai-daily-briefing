#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="$REPO_ROOT/skills/daily-briefing"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
TARGET="$CODEX_HOME_DIR/skills/daily-briefing"
FORCE=0

if [ "${1:-}" = "--force" ]; then
  FORCE=1
elif [ "$#" -gt 0 ]; then
  echo "Usage: $0 [--force]" >&2
  exit 2
fi

if [ ! -f "$SOURCE/SKILL.md" ]; then
  echo "Missing skill source: $SOURCE" >&2
  exit 1
fi

mkdir -p "$(dirname "$TARGET")"

if [ -e "$TARGET" ] || [ -L "$TARGET" ]; then
  CURRENT="$(cd -P "$TARGET" 2>/dev/null && pwd || true)"
  if [ "$CURRENT" = "$SOURCE" ]; then
    echo "daily-briefing is already installed: $TARGET"
    exit 0
  fi

  if [ "$FORCE" -ne 1 ]; then
    echo "A daily-briefing skill already exists at $TARGET" >&2
    echo "Run $0 --force to back it up and install this version." >&2
    exit 1
  fi

  BACKUP="$TARGET.backup-$(date +%Y%m%d-%H%M%S)"
  mv "$TARGET" "$BACKUP"
  echo "Backed up existing skill to: $BACKUP"
fi

ln -s "$SOURCE" "$TARGET"
echo "Installed daily-briefing for Codex: $TARGET"
echo 'Invoke it with: $daily-briefing 生成今日早报'
