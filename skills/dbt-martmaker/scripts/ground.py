#!/usr/bin/env python3
"""
Ground one or more source-table references, and a metric name, against a
dbt project's own state: models that already exist in its
staging/intermediate layers, and metrics that already exist in its dbt
Semantic Layer.

Reads target/manifest.json directly -- no live dbt-mcp connection required.
If target/catalog.json is present, real warehouse column types are attached
to a matched/ambiguous candidate's columns, so a proposal can judge whether
a candidate column can actually support a stakeholder's calculation (e.g. an
amount column stored as a string). The catalog is enrichment only -- a
missing catalog never blocks or downgrades a match made from the manifest.

If target/semantic_manifest.json is present, the metric name is also scored
against every existing dbt Semantic Layer metric, using the same scorer used
for table grounding. A confident hit is never a silent block: it is surfaced
so the calling skill can ask whether a stakeholder still wants a materialized
duplicate of a metric MetricFlow already serves.

If a .mcp.json in the project configures a dbt MCP server, this script just
reports that fact so the calling skill can optionally use it for richer
lineage/detail lookups; this script never calls it itself.

Usage:
    ground.py <project_root> "<comma-separated source table references>" "<metric name>"

Output: a single JSON object on stdout. Never raises on a "no match" case --
that's a normal, expected result (status: blocked), not an error. Exits
non-zero only for genuine setup problems (missing manifest.json, bad args).
"""
import json
import re
import sys
from pathlib import Path

MATCHED_THRESHOLD = 0.72
AMBIGUOUS_THRESHOLD = 0.35
MAX_SHORTLIST = 10
DESC_ONLY_CEILING = 0.5  # a description mention alone can surface a candidate,
                          # but can never alone be confident enough to auto-match

STAGING_INTERMEDIATE_PREFIXES = ("models/staging", "models/intermediate")
LAYER_PREFIXES = {"stg", "int", "dim", "fct", "rpt", "base", "seed"}


def load_manifest(project_root: Path) -> dict:
    manifest_path = project_root / "target" / "manifest.json"
    if not manifest_path.exists():
        print(
            json.dumps(
                {
                    "error": "no_manifest",
                    "message": (
                        f"No target/manifest.json found at {manifest_path}. "
                        "Run 'dbt parse' in this project first."
                    ),
                }
            )
        )
        sys.exit(1)
    with manifest_path.open() as f:
        return json.load(f)


def load_catalog(project_root: Path) -> dict:
    """Optional enrichment. Returns {} (never errors, never exits) when
    target/catalog.json doesn't exist -- grounding must work the same
    without it, just without real column types."""
    catalog_path = project_root / "target" / "catalog.json"
    if not catalog_path.exists():
        return {}
    with catalog_path.open() as f:
        return json.load(f)


def _column_types(unique_id: str, catalog: dict) -> dict[str, str]:
    node = catalog.get("nodes", {}).get(unique_id, {})
    return {
        col_name: (col_info.get("type") or "")
        for col_name, col_info in node.get("columns", {}).items()
    }


def staging_and_intermediate_models(manifest: dict, catalog: dict | None = None) -> list[dict]:
    catalog = catalog or {}
    candidates = []
    # manifest.json's "nodes" dict is keyed by unique_id -- that key is the
    # authoritative id, not the (often absent in hand-built fixtures, and
    # redundant in real manifests) "unique_id" field some nodes also carry.
    for unique_id, node in manifest.get("nodes", {}).items():
        if node.get("resource_type") != "model":
            continue
        original_path = node.get("original_file_path", "")
        if not original_path.replace("\\", "/").startswith(STAGING_INTERMEDIATE_PREFIXES):
            continue
        candidates.append(
            {
                "name": node.get("name", ""),
                "description": node.get("description", "") or "",
                "columns": sorted(node.get("columns", {}).keys()),
                "column_types": _column_types(unique_id, catalog),
                "original_file_path": original_path,
                "unique_id": unique_id,
            }
        )
    return candidates


def semantic_layer_metrics(project_root: Path) -> list[dict]:
    """Every metric already defined in the project's dbt Semantic Layer, if
    it has one. Returns [] when target/semantic_manifest.json doesn't exist
    or defines no metrics -- never an error, since most projects don't run
    a Semantic Layer at all."""
    manifest_path = project_root / "target" / "semantic_manifest.json"
    if not manifest_path.exists():
        return []
    with manifest_path.open() as f:
        data = json.load(f)
    return [
        {
            "name": m.get("name", ""),
            "label": m.get("label") or "",
            "description": m.get("description", "") or "",
        }
        for m in data.get("metrics", [])
    ]


def _tokenize(text: str) -> set[str]:
    return {tok for tok in re.split(r"[^a-z0-9]+", text.lower()) if len(tok) > 2}


def _name_tokens(name: str) -> set[str]:
    # dbt layer prefixes (stg_/int_/dim_/...) are naming-convention noise, not
    # business meaning -- a user saying "payments" never says "stg payments".
    return _tokenize(name) - LAYER_PREFIXES


def score(reference: str, candidate: dict) -> float:
    ref_tokens = _tokenize(reference)
    if not ref_tokens:
        return 0.0

    # Name matching is token-containment based, not raw character-sequence
    # ratio -- difflib.SequenceMatcher.ratio() on two short, unrelated strings
    # (e.g. "widgets_inventory" vs "int_orders") produces meaningless
    # coincidental scores just from shared characters. Token overlap only
    # scores what's genuinely the same word.
    name_tokens = _name_tokens(candidate["name"])
    name_score = len(ref_tokens & name_tokens) / len(ref_tokens) if name_tokens else 0.0

    # Same reasoning for descriptions, but capped: an incidental word mention
    # in an otherwise-unrelated model's description (e.g. "payments" appearing
    # once in int_orders' description) is real but weaker evidence than an
    # actual name match, and must never be allowed to outscore or masquerade
    # as one -- so it's capped below the point where it could ever auto-match
    # on its own.
    desc_score = 0.0
    if candidate["description"]:
        desc_tokens = _tokenize(candidate["description"])
        if desc_tokens:
            desc_score = len(ref_tokens & desc_tokens) / len(ref_tokens)

    if name_score > 0:
        return name_score
    return min(desc_score, DESC_ONLY_CEILING)


def dbt_mcp_configured(project_root: Path) -> bool:
    mcp_config = project_root / ".mcp.json"
    if not mcp_config.exists():
        return False
    try:
        data = json.loads(mcp_config.read_text())
    except (json.JSONDecodeError, OSError):
        return False
    servers = data.get("mcpServers", {})
    return any("dbt" in str(cfg).lower() or "dbt" in name.lower() for name, cfg in servers.items())


def ground_one(reference: str, candidates: list[dict]) -> dict:
    scored = sorted(
        (
            {"model": c["name"], "score": round(score(reference, c), 3), **c}
            for c in candidates
        ),
        key=lambda c: c["score"],
        reverse=True,
    )
    if not scored or scored[0]["score"] < AMBIGUOUS_THRESHOLD:
        return {"reference": reference, "status": "blocked", "candidates": []}

    top = scored[0]
    second = scored[1]["score"] if len(scored) > 1 else 0.0
    if top["score"] >= MATCHED_THRESHOLD and (top["score"] - second) >= 0.15:
        return {
            "reference": reference,
            "status": "matched",
            "model": top["name"],
            "description": top["description"],
            "columns": top["columns"],
            "column_types": top["column_types"],
            "original_file_path": top["original_file_path"],
            "score": top["score"],
        }

    shortlist = [
        {
            "model": c["name"],
            "description": c["description"],
            "columns": c["columns"],
            "column_types": c["column_types"],
            "original_file_path": c["original_file_path"],
            "score": c["score"],
        }
        for c in scored[:MAX_SHORTLIST]
        if c["score"] >= AMBIGUOUS_THRESHOLD
    ]
    return {"reference": reference, "status": "ambiguous", "candidates": shortlist}


def ground_against_semantic_layer(metric_name: str, semantic_metrics: list[dict]) -> dict | None:
    """A confident hit only -- reuses MATCHED_THRESHOLD rather than a new
    magic number, since "confident enough to auto-match a table" is the same
    bar as "confident enough to tell a stakeholder this metric may already
    exist." Below that bar, stay silent rather than raise a shaky flag.

    Scores against both the metric's internal `name` and its human-readable
    `label` (when the Semantic Layer defines one) and keeps the better of
    the two -- a stakeholder's "Marketing ROI" often matches a metric's
    label even when it diverges from a snake_case name like `mktg_roi_pct`.
    """
    if not metric_name or not semantic_metrics:
        return None
    scored = []
    for m in semantic_metrics:
        name_score = score(metric_name, {"name": m["name"], "description": m["description"]})
        label_score = (
            score(metric_name, {"name": m["label"], "description": ""}) if m["label"] else 0.0
        )
        scored.append(
            {
                "metric": m["name"],
                "label": m["label"],
                "description": m["description"],
                "score": round(max(name_score, label_score), 3),
            }
        )
    scored.sort(key=lambda c: c["score"], reverse=True)
    top = scored[0]
    if top["score"] < MATCHED_THRESHOLD:
        return None
    return top


def main() -> None:
    if len(sys.argv) != 4:
        print(
            json.dumps(
                {
                    "error": "bad_args",
                    "message": (
                        "Usage: ground.py <project_root> "
                        '"<comma-separated source table references>" "<metric name>"'
                    ),
                }
            )
        )
        sys.exit(1)

    project_root = Path(sys.argv[1]).resolve()
    references = [r.strip() for r in sys.argv[2].split(",") if r.strip()]
    metric_name = sys.argv[3].strip()

    manifest = load_manifest(project_root)
    catalog = load_catalog(project_root)
    candidates = staging_and_intermediate_models(manifest, catalog)

    results = [ground_one(ref, candidates) for ref in references]

    semantic_metrics = semantic_layer_metrics(project_root)
    semantic_match = ground_against_semantic_layer(metric_name, semantic_metrics)

    print(
        json.dumps(
            {
                "dbt_mcp_configured": dbt_mcp_configured(project_root),
                "catalog_available": bool(catalog),
                "candidate_pool_size": len(candidates),
                "results": results,
                "semantic_layer": {
                    "available": (project_root / "target" / "semantic_manifest.json").exists(),
                    "match": semantic_match,
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
