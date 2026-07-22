#!/usr/bin/env bash
# Install dbt-scribe as a Claude Code / agent skill.
#
# Usage:
#   ./install.sh                 # symlink into ~/.claude/skills/dbt-scribe (global)
#   ./install.sh --project       # symlink into ./.claude/skills/dbt-scribe (current project only)
#   ./install.sh --copy          # copy instead of symlink (won't track future `git pull` updates)
#   ./install.sh --project --copy

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$REPO_DIR/skills/dbt-scribe"

TARGET_ROOT="$HOME/.claude/skills"
MODE="symlink"

for arg in "$@"; do
  case "$arg" in
    --project) TARGET_ROOT="$(pwd)/.claude/skills" ;;
    --copy) MODE="copy" ;;
    *)
      echo "Unknown argument: $arg" >&2
      echo "Usage: $0 [--project] [--copy]" >&2
      exit 1
      ;;
  esac
done

DEST="$TARGET_ROOT/dbt-scribe"
mkdir -p "$TARGET_ROOT"

if [ -e "$DEST" ] || [ -L "$DEST" ]; then
  echo "Error: $DEST already exists. Remove it first if you want to reinstall." >&2
  exit 1
fi

if [ "$MODE" = "symlink" ]; then
  ln -s "$SRC" "$DEST"
  echo "Symlinked $DEST -> $SRC"
  echo "Future 'git pull' in $REPO_DIR will update the installed skill automatically."
else
  cp -R "$SRC" "$DEST"
  echo "Copied $SRC -> $DEST"
  echo "This copy will NOT update on 'git pull' -- rerun install.sh --copy to refresh it."
fi

echo
echo "Prerequisites, checked at run time by the skill itself, not here:"
echo "  - a dbt project with target/manifest.json present (run 'dbt parse')"
echo "  - PyYAML available in whatever environment runs the skill's scripts"
