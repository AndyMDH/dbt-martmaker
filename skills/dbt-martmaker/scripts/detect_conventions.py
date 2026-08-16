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


# Not every project keeps marts in a dedicated models/marts/ subfolder --
# dbt's own jaffle-shop starter, among plenty of real projects, keeps them
# at the top level of models/ instead. Sampling only ever looked in
# models/marts/, so a project shaped that way reported "no marts to sample
# from" despite genuinely having marts.
NON_MART_MODEL_DIRS = {"staging", "intermediate", "seeds", "snapshots"}


def marts_search_root(project_root: Path) -> Path | None:
    """Where to sample marts conventions from. Prefers models/marts/ when
    it actually has SQL files in it -- the documented convention. Falls
    back to models/ itself otherwise; callers must exclude
    NON_MART_MODEL_DIRS when scanning that fallback, since models/ also
    contains staging/intermediate/etc."""
    marts_dir = project_root / "models" / "marts"
    if marts_dir.exists() and any(marts_dir.rglob("*.sql")):
        return marts_dir
    models_dir = project_root / "models"
    return models_dir if models_dir.exists() else None


def _is_mart_path(path: Path, search_root: Path) -> bool:
    if search_root.name == "marts":
        return True
    parts = set(path.relative_to(search_root).parts[:-1])
    return not (parts & NON_MART_MODEL_DIRS)


def sample_naming_from_files(project_root: Path) -> dict | None:
    search_root = marts_search_root(project_root)
    if search_root is None:
        return None
    sql_files = [
        p.stem for p in search_root.rglob("*.sql") if _is_mart_path(p, search_root)
    ]
    if not sql_files:
        return None

    location = search_root.relative_to(project_root)
    prefixes = Counter()
    for name in sql_files:
        match = re.match(r"^([a-z]+_)", name)
        if match:
            prefixes[match.group(1)] += 1
    if not prefixes:
        # Real files were found, but none share a prefix -- worth reporting
        # as "no convention detected", distinct from "nothing found at all".
        return {
            "pattern": None,
            "source": f"sampled:{location} ({len(sql_files)} files) -- no common prefix found",
        }
    common = sorted(prefixes, key=lambda p: -prefixes[p])
    pattern = "^" + "|^".join(re.escape(p) for p in common)
    return {"pattern": pattern, "source": f"sampled:{location} ({len(sql_files)} files)"}


def sample_property_file_pattern(project_root: Path) -> dict | None:
    search_root = marts_search_root(project_root)
    if search_root is None:
        return None
    per_dir_patterns = {}
    for yml_file in search_root.rglob("*.yml"):
        if not _is_mart_path(yml_file, search_root):
            continue
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


BUILTIN_GENERIC_TESTS = {"not_null", "unique", "accepted_values", "relationships"}


def detect_existing_tests(project_root: Path) -> dict:
    """
    Survey generic tests already used in this project's manifest, so a new
    test doesn't get drafted from a generic/package default when the
    project has its own established convention (e.g. a custom
    `not_negative` test already used on similar columns elsewhere) --
    never invents a new custom test macro, only surfaces what's already
    real and in use.
    """
    manifest_path = project_root / "target" / "manifest.json"
    if not manifest_path.exists():
        return {
            "builtin": {},
            "package": [],
            "custom": [],
            "source": "none -- no target/manifest.json found",
        }

    with manifest_path.open() as f:
        manifest = json.load(f)

    builtin_counts = Counter()
    package_counts = Counter()
    custom_counts = Counter()

    for node in manifest.get("nodes", {}).values():
        if node.get("resource_type") != "test":
            continue
        test_metadata = node.get("test_metadata")
        if not test_metadata:
            continue  # singular test (raw SQL), no generic test name to compare
        name = test_metadata.get("name")
        namespace = test_metadata.get("namespace")
        if namespace:
            package_counts[(namespace, name)] += 1
        elif name in BUILTIN_GENERIC_TESTS:
            builtin_counts[name] += 1
        else:
            custom_counts[name] += 1

    return {
        "builtin": dict(builtin_counts),
        "package": [
            {"namespace": ns, "name": name, "count": count}
            for (ns, name), count in package_counts.most_common()
        ],
        "custom": [
            {"name": name, "count": count} for name, count in custom_counts.most_common()
        ],
        "source": "target/manifest.json",
    }


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
    existing_tests = detect_existing_tests(project_root)

    result = {
        "naming": naming or {"pattern": None, "source": "none -- marts folder empty or missing, do not guess"},
        "property_files": property_files or {"per_directory_samples": {}, "source": "none -- no existing marts property files to sample"},
        "materialization": materialization or {"materialized": None, "source": "none -- fall back to dbt's own default"},
        "existing_tests": existing_tests,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
