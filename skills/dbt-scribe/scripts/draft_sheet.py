#!/usr/bin/env python3
"""
Scaffold a blank draft metric sheet at .dbt-scribe/sheets/<slug>.draft.csv.

This script only creates the file skeleton (header row) -- it does not read
a transcript or fill in any rows. Turning a transcript into candidate rows
requires language understanding, which is the calling skill/agent's job,
not this script's. See AGENTS.md, "If asked to draft a sheet from a
transcript."

Usage:
    draft_sheet.py <project_root> <slug>
"""
import sys
from pathlib import Path

HEADER = "metric,definition,calculation,source_tables\n"


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: draft_sheet.py <project_root> <slug>", file=sys.stderr)
        sys.exit(1)

    project_root = Path(sys.argv[1]).resolve()
    slug = sys.argv[2]

    sheets_dir = project_root / ".dbt-scribe" / "sheets"
    sheets_dir.mkdir(parents=True, exist_ok=True)

    draft_path = sheets_dir / f"{slug}.draft.csv"
    if draft_path.exists():
        print(f"ERROR: {draft_path} already exists -- not overwriting.", file=sys.stderr)
        sys.exit(1)

    draft_path.write_text(HEADER)
    print(str(draft_path))


if __name__ == "__main__":
    main()
