#!/usr/bin/env python3
"""
Status overview of every metric sheet in a project's .dbt-martmaker/sheets/,
cross-referenced against its drafts' meta.json -- so "what have I got in
flight, and is any of it stale?" doesn't require manually reading multiple
directories.

Usage:
    list_sheets.py <project_root>

Output: a single JSON object on stdout. An empty sheets directory (or none
at all) is a normal, reportable result, not an error.
"""
import hashlib
import json
import sys
from pathlib import Path


def sheet_status(project_root: Path, sheet_path: Path) -> dict:
    slug = sheet_path.stem
    checksum = hashlib.sha256(sheet_path.read_bytes()).hexdigest()
    meta_path = project_root / ".dbt-martmaker" / "drafts" / slug / "meta.json"

    entry = {"slug": slug, "sheet": str(sheet_path.relative_to(project_root))}

    if not meta_path.exists():
        entry["status"] = "no proposal yet"
        return entry

    try:
        meta = json.loads(meta_path.read_text())
    except (json.JSONDecodeError, OSError):
        entry["status"] = "meta.json unreadable"
        return entry

    if meta.get("sheet_checksum") != checksum:
        entry["status"] = "stale (sheet changed since last proposal)"
        entry["last_generated_at"] = meta.get("generated_at")
        return entry

    entry["status"] = meta.get("status", "unknown")
    entry["generated_at"] = meta.get("generated_at")
    rows = meta.get("rows", [])
    entry["row_counts"] = {
        "matched": sum(1 for r in rows if r.get("status") == "matched"),
        "ambiguous": sum(1 for r in rows if r.get("status") == "ambiguous"),
        "blocked": sum(1 for r in rows if r.get("status") == "blocked"),
    }
    return entry


def build_report(project_root: Path) -> dict:
    sheets_dir = project_root / ".dbt-martmaker" / "sheets"
    if not sheets_dir.exists():
        return {"sheets_dir_present": False, "sheets": []}

    sheets = sorted(sheets_dir.glob("*.csv"))
    return {
        "sheets_dir_present": True,
        "sheets": [sheet_status(project_root, s) for s in sheets],
    }


def main() -> None:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "bad_args", "message": "Usage: list_sheets.py <project_root>"}))
        sys.exit(1)

    project_root = Path(sys.argv[1]).resolve()
    print(json.dumps(build_report(project_root), indent=2))


if __name__ == "__main__":
    main()
