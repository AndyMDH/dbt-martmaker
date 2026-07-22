#!/usr/bin/env python3
"""
Detect this dbt project's own mart-layer naming, materialization, and
property-file conventions -- never assume one fixed convention, since it
differs per project (confirmed inconsistent even within a single template
repo).

Usage:
    detect_conventions.py <project_root>

Output: a single JSON object on stdout describing what was detected and
where it came from, so the calling skill can cite its source in the
proposal rather than presenting a guess as fact.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

try:
    import yaml
except ImportError:
    print(
        json.dumps(
            {
                "error": "missing_dependency",
                "message": (
                    "PyYAML is required to parse dbt_project.yml/dbt-bouncer.yml. "
                    "Install it in the same environment dbt runs in: pip install pyyaml"
                ),
            }
        )
    )
    sys.exit(1)


def detect_naming_from_bouncer(project_root: Path) -> dict | None:
    bouncer_path = project_root / "dbt-bouncer.yml"
    if not bouncer_path.exists():
        return None
    data = yaml.safe_load(bouncer_path.read_text()) or {}
    for check in data.get("manifest_checks", []) or []:
        if check.get("name") != "check_model_names":
            continue
        include = check.get("include", "")
        if "marts" in include:
            return {
                "pattern": check.get("model_name_pattern", ""),
                "source": "dbt-bouncer.yml",
            }
    return None


def sample_naming_from_files(project_root: Path) -> dict | None:
    marts_dir = project_root / "models" / "marts"
    if not marts_dir.exists():
        return None
    sql_files = [p.stem for p in marts_dir.rglob("*.sql")]
    if not sql_files:
        return None
    prefixes = Counter()
    for name in sql_files:
        match = re.match(r"^([a-z]+_)", name)
        if match:
            prefixes[match.group(1)] += 1
    if not prefixes:
        return None
    common = sorted(prefixes, key=lambda p: -prefixes[p])
    pattern = "^" + "|^".join(re.escape(p) for p in common)
    return {"pattern": pattern, "source": f"sampled:models/marts ({len(sql_files)} files)"}


def sample_property_file_pattern(project_root: Path) -> dict | None:
    marts_dir = project_root / "models" / "marts"
    if not marts_dir.exists():
        return None
    per_dir_patterns = {}
    for yml_file in marts_dir.rglob("*.yml"):
        rel_dir = str(yml_file.parent.relative_to(project_root))
        per_dir_patterns.setdefault(rel_dir, []).append(yml_file.name)
    if not per_dir_patterns:
        return None
    return {"per_directory_samples": per_dir_patterns, "source": "sampled per-directory"}


def detect_materialization(project_root: Path) -> dict | None:
    project_yml = project_root / "dbt_project.yml"
    if not project_yml.exists():
        return None
    data = yaml.safe_load(project_yml.read_text()) or {}
    models_config = data.get("models", {})

    def find_marts_materialization(node, path=""):
        if not isinstance(node, dict):
            return None
        if "marts" in path and "+materialized" in node:
            return node["+materialized"]
        for key, value in node.items():
            if key.startswith("+"):
                continue
            found = find_marts_materialization(value, path + "/" + key)
            if found:
                return found
        return None

    materialized = find_marts_materialization(models_config)
    if materialized:
        return {"materialized": materialized, "source": "dbt_project.yml"}
    return None


def main() -> None:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "bad_args", "message": "Usage: detect_conventions.py <project_root>"}))
        sys.exit(1)

    project_root = Path(sys.argv[1]).resolve()
    if not (project_root / "dbt_project.yml").exists():
        print(
            json.dumps(
                {
                    "error": "not_a_dbt_project",
                    "message": f"No dbt_project.yml found at {project_root}",
                }
            )
        )
        sys.exit(1)

    naming = detect_naming_from_bouncer(project_root) or sample_naming_from_files(project_root)
    property_files = sample_property_file_pattern(project_root)
    materialization = detect_materialization(project_root)

    result = {
        "naming": naming or {"pattern": None, "source": "none -- marts folder empty or missing, do not guess"},
        "property_files": property_files or {"per_directory_samples": {}, "source": "none -- no existing marts property files to sample"},
        "materialization": materialization or {"materialized": None, "source": "none -- fall back to dbt's own default"},
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
