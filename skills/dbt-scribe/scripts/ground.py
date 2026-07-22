#!/usr/bin/env python3
"""
Ground one or more source-table references against models that already
exist in a dbt project's staging/intermediate layers.

Reads target/manifest.json directly -- no live dbt-mcp connection required.
If a .mcp.json in the project configures a dbt MCP server, this script just
reports that fact so the calling skill can optionally use it for richer
lineage/detail lookups; this script never calls it itself.

Usage:
    ground.py <project_root> "<comma-separated source table references>"

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


def staging_and_intermediate_models(manifest: dict) -> list[dict]:
    candidates = []
    for node in manifest.get("nodes", {}).values():
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
                "original_file_path": original_path,
                "unique_id": node.get("unique_id", ""),
            }
        )
    return candidates


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
            "original_file_path": top["original_file_path"],
            "score": top["score"],
        }

    shortlist = [
        {
            "model": c["name"],
            "description": c["description"],
            "original_file_path": c["original_file_path"],
            "score": c["score"],
        }
        for c in scored[:MAX_SHORTLIST]
        if c["score"] >= AMBIGUOUS_THRESHOLD
    ]
    return {"reference": reference, "status": "ambiguous", "candidates": shortlist}


def main() -> None:
    if len(sys.argv) != 3:
        print(
            json.dumps(
                {
                    "error": "bad_args",
                    "message": 'Usage: ground.py <project_root> "<comma-separated source table references>"',
                }
            )
        )
        sys.exit(1)

    project_root = Path(sys.argv[1]).resolve()
    references = [r.strip() for r in sys.argv[2].split(",") if r.strip()]

    manifest = load_manifest(project_root)
    candidates = staging_and_intermediate_models(manifest)

    results = [ground_one(ref, candidates) for ref in references]

    print(
        json.dumps(
            {
                "dbt_mcp_configured": dbt_mcp_configured(project_root),
                "candidate_pool_size": len(candidates),
                "results": results,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
