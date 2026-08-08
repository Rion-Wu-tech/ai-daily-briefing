#!/usr/bin/env bash
set -euo pipefail

REPOSITORY_URL="https://github.com/Rion-Wu-tech/ai-daily-briefing.git"
SCRIPT_DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd -P)"
EMBEDDED_REPO="$(cd "$SKILL_DIR/../.." && pwd -P)"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
RUNTIME_DIR="$CODEX_HOME_DIR/daily-briefing-runtime"

find_project() {
  if [ -n "${DAILY_BRIEFING_PROJECT:-}" ] && [ -f "$DAILY_BRIEFING_PROJECT/briefing.py" ]; then
    printf '%s\n' "$DAILY_BRIEFING_PROJECT"
    return
  fi

  if [ -f "$PWD/briefing.py" ] && [ -f "$PWD/config.yaml" ]; then
    printf '%s\n' "$PWD"
    return
  fi

  if [ -f "$EMBEDDED_REPO/briefing.py" ]; then
    printf '%s\n' "$EMBEDDED_REPO"
    return
  fi

  if [ ! -f "$RUNTIME_DIR/briefing.py" ]; then
    mkdir -p "$(dirname "$RUNTIME_DIR")"
    git clone --depth 1 "$REPOSITORY_URL" "$RUNTIME_DIR" >&2
  fi
  printf '%s\n' "$RUNTIME_DIR"
}

PROJECT_DIR="$(find_project)"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"

cd "$PROJECT_DIR"

if [ ! -x "$PYTHON_BIN" ]; then
  python3 -m venv .venv
  "$PYTHON_BIN" -m pip install -r requirements.txt
fi

if [ "$#" -eq 0 ]; then
  set -- --format markdown
fi

exec "$PYTHON_BIN" briefing.py "$@"
