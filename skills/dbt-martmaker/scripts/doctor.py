#!/usr/bin/env python3
"""
Readiness check for dbt-martmaker. Run this before Step 0 of AGENTS.md when
it's unclear whether the current directory (or its parents) has everything
the skill needs -- one report instead of discovering missing prerequisites
one error at a time mid-workflow.

Usage:
    doctor.py [start_dir]

start_dir defaults to the current working directory. Walks upward looking
for dbt_project.yml, the same way AGENTS.md Step 0 does.

Output: a single JSON object on stdout. Never exits non-zero -- an
unready project is a normal, reportable result, not a script failure.
"""
import json
import sys
from pathlib import Path

MAX_WALK_UP = 10


def find_project_root(start: Path) -> Path | None:
    current = start.resolve()
    for _ in range(MAX_WALK_UP):
        if (current / "dbt_project.yml").exists():
            return current
        if current.parent == current:
            return None
        current = current.parent
    return None


def pyyaml_importable() -> bool:
    try:
        import yaml  # noqa: F401

        return True
    except ImportError:
        return False


def build_report(start: Path) -> dict:
    project_root = find_project_root(start)

    checks = {}
    messages = []

    checks["dbt_project_found"] = project_root is not None
    if project_root is None:
        messages.append(
            f"No dbt_project.yml found walking up from {start.resolve()} "
            f"(checked {MAX_WALK_UP} levels). Run from inside a dbt project."
        )
        return {"ready": False, "project_root": None, "checks": checks, "messages": messages}

    manifest_present = (project_root / "target" / "manifest.json").exists()
    checks["manifest_present"] = manifest_present
    if not manifest_present:
        messages.append("No target/manifest.json -- run 'dbt parse' in this project first.")

    checks["pyyaml_installed"] = pyyaml_importable()
    if not checks["pyyaml_installed"]:
        messages.append(
            "PyYAML isn't importable in this environment -- detect_conventions.py needs it "
            "to read dbt_project.yml/dbt-bouncer.yml. Install it where dbt runs: pip install pyyaml"
        )

    # Enrichment only -- never block readiness on these, just report them.
    checks["catalog_present"] = (project_root / "target" / "catalog.json").exists()
    if not checks["catalog_present"]:
        messages.append(
            "No target/catalog.json -- grounding will work without it, just without real "
            "column types. Run 'dbt docs generate' to add it."
        )

    checks["semantic_manifest_present"] = (
        project_root / "target" / "semantic_manifest.json"
    ).exists()
    if not checks["semantic_manifest_present"]:
        messages.append(
            "No target/semantic_manifest.json -- this project doesn't appear to run a dbt "
            "Semantic Layer. The Semantic Layer duplicate-metric check will be skipped, which "
            "is expected for most projects."
        )

    checks["dbt_bouncer_config_present"] = (project_root / "dbt-bouncer.yml").exists()
    marts_dir = project_root / "models" / "marts"
    checks["marts_dir_has_files"] = marts_dir.exists() and any(marts_dir.rglob("*.sql"))
    if not checks["dbt_bouncer_config_present"] and not checks["marts_dir_has_files"]:
        messages.append(
            "No dbt-bouncer.yml and no existing files under models/marts/ -- there's nothing "
            "to sample a naming/materialization convention from yet. Not an error; the "
            "proposal will ask you to confirm a convention instead of guessing one."
        )

    checks["sheets_dir_present"] = (project_root / ".dbt-martmaker" / "sheets").exists()

    ready = checks["dbt_project_found"] and checks["manifest_present"] and checks["pyyaml_installed"]

    return {
        "ready": ready,
        "project_root": str(project_root),
        "checks": checks,
        "messages": messages,
    }


def main() -> None:
    start = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    print(json.dumps(build_report(start), indent=2))


if __name__ == "__main__":
    main()
