#!/usr/bin/env python3
"""
Ground one or more source-table references, and a metric name, against a
dbt project's own state: models that already exist in its
staging/intermediate layers (local and, when configured, public models in
sibling dbt Mesh projects), and metrics that already exist in its dbt
Semantic Layer.

Reads target/manifest.json directly -- no live dbt-mcp connection required.
If target/catalog.json is present, real warehouse column types are attached
to a matched/ambiguous candidate's columns. If target/semantic_manifest.json
is present, the metric name is scored against every existing dbt Semantic
Layer metric. Both are enrichment: absence never blocks or downgrades a
match made from the manifest.

Two further, entirely optional layers of matching:

- A project-specific glossary at .dbt-martmaker/glossary.yml, merged on
  top of a small built-in synonym list, so "clients" and "customers"
  overlap without every project needing to teach the tool its own
  vocabulary from scratch.
- A corrections log at .dbt-martmaker/corrections.jsonl: once a human
  corrects a match, it is remembered and applied deterministically to
  every future run of that exact reference -- checked before scoring,
  never overridden by a score.

If VOYAGE_API_KEY is set in the environment, reference and candidate text
is also embedded via the Voyage AI API and compared by cosine similarity.
This is enrichment only and never decides a match by itself: it can attach
a confidence signal to an existing match/ambiguous result, and it can
surface a "blocked" reference as "ambiguous" when embeddings find a
plausible candidate token overlap missed entirely -- but nothing above the
embedding floor is ever auto-matched. Without the key, or if the API call
fails for any reason, grounding behaves exactly as it does with no network
access at all.

If a .mcp.json in the project configures a dbt MCP server, this script just
reports that fact so the calling skill can optionally use it for richer
lineage/detail lookups, or to look up a public model in a sibling dbt Cloud
project this script has no local manifest for; this script never calls it
itself.

Usage:
    ground.py <project_root> "<comma-separated source table references>" "<metric name>"

Output: a single JSON object on stdout. Never raises on a "no match" case --
that's a normal, expected result (status: blocked), not an error. Exits
non-zero only for genuine setup problems (missing manifest.json, bad args).
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

# Deliberately conservative, not tuned per-project: a false "matched" that
# silently picks the wrong model is worse than an "ambiguous" that asks a
# human, so every threshold below is set to fail toward asking, not guessing.
MATCHED_THRESHOLD = 0.72  # top score must clear this to auto-match
AMBIGUOUS_THRESHOLD = 0.35  # below this, a candidate isn't even shortlisted
MAX_SHORTLIST = 10
DESC_ONLY_CEILING = 0.5  # a description mention alone can surface a candidate,
                          # but can never alone be confident enough to auto-match
# top score must beat the runner-up by this margin to auto-match -- without
# it, two similarly-named models (stg_orders vs stg_order_items) could tie
# into a wrong pick instead of surfacing both as ambiguous candidates.
MATCH_MARGIN = 0.15
# Cosine-similarity floor for embeddings alone to surface a "blocked"
# reference as "ambiguous". Deliberately high: embeddings only ever widen
# what gets shown to a human, never narrow it to an auto-match.
EMBEDDING_AMBIGUOUS_FLOOR = 0.75

STAGING_INTERMEDIATE_PREFIXES = ("models/staging", "models/intermediate")
LAYER_PREFIXES = {"stg", "int", "dim", "fct", "rpt", "base", "seed"}

# Common analytics-engineering synonyms -- not exhaustive NLP, just the
# handful of business-term pairs that come up constantly (a stakeholder
# says "clients", the project's staging model says stg_customers) and would
# otherwise score zero token overlap despite meaning the same thing. A
# project can extend this via .dbt-martmaker/glossary.yml (see
# load_glossary) instead of editing this file.
SYNONYM_GROUPS = [
    {"customer", "customers", "client", "clients"},
    {"order", "orders", "purchase", "purchases"},
    {"revenue", "sales"},
    {"user", "users", "member", "members"},
    {"employee", "employees", "staff"},
    {"payment", "payments", "transaction", "transactions"},
]
_BUILTIN_SYNONYM_CANONICAL = {token: min(group) for group in SYNONYM_GROUPS for token in group}

VOYAGE_API_URL = "https://api.voyageai.com/v1/embeddings"
VOYAGE_DEFAULT_MODEL = "voyage-4-lite"  # cost/latency-conscious default for
                                          # an enrichment call, not the
                                          # decision-maker; override via
                                          # VOYAGE_MODEL if you want more.


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


def _real_columns(unique_id: str, node: dict, catalog: dict) -> tuple[list[str], bool]:
    """The most complete column list available for this model, and
    whether it's actually complete. target/catalog.json reflects the real
    warehouse schema -- every column, documented or not. target/manifest.json
    only lists columns someone wrote a `columns:` entry for in a
    schema.yml, which real projects usually document only a subset of
    (whichever columns have a test on them). Prefer catalog when this node
    is in it; otherwise fall back to the manifest's documented-only list
    and say so, so a caller never mistakes "undocumented" for "confirmed
    absent"."""
    catalog_columns = catalog.get("nodes", {}).get(unique_id, {}).get("columns", {})
    if catalog_columns:
        return sorted(catalog_columns.keys()), True
    return sorted(node.get("columns", {}).keys()), False


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
        columns, columns_complete = _real_columns(unique_id, node, catalog)
        candidates.append(
            {
                "name": node.get("name", ""),
                "description": node.get("description", "") or "",
                "columns": columns,
                "columns_complete": columns_complete,
                "column_types": _column_types(unique_id, catalog),
                "original_file_path": original_path,
                "unique_id": unique_id,
                "source_project": None,  # local to this project's own manifest
            }
        )
    return candidates


def load_mesh_projects(project_root: Path) -> list[dict]:
    """Sibling dbt projects reachable on disk, listed in
    .dbt-martmaker/mesh_manifests.yml:

        projects:
          - name: shared_models
            manifest: ../shared-models-repo/target/manifest.json

    Returns [] when the config is absent or PyYAML isn't installed -- dbt
    Mesh awareness is entirely optional; most projects don't run it."""
    config_path = project_root / ".dbt-martmaker" / "mesh_manifests.yml"
    if not config_path.exists() or yaml is None:
        return []
    data = yaml.safe_load(config_path.read_text()) or {}
    return data.get("projects", []) or []


def mesh_candidates(project_root: Path) -> list[dict]:
    """Public models from sibling projects listed in mesh_manifests.yml. A
    model must declare access: public in its own manifest to be eligible --
    dbt Mesh's own contract boundary, never overridden here."""
    candidates = []
    for project in load_mesh_projects(project_root):
        manifest_rel_path = project.get("manifest")
        if not manifest_rel_path:
            continue
        manifest_path = (project_root / manifest_rel_path).resolve()
        if not manifest_path.exists():
            continue
        project_name = project.get("name") or manifest_path.parent.parent.name
        with manifest_path.open() as f:
            sibling_manifest = json.load(f)
        for unique_id, node in sibling_manifest.get("nodes", {}).items():
            if node.get("resource_type") != "model":
                continue
            if node.get("access") != "public":
                continue
            candidates.append(
                {
                    "name": node.get("name", ""),
                    "description": node.get("description", "") or "",
                    "columns": sorted(node.get("columns", {}).keys()),
                    "columns_complete": False,  # sibling catalog.json isn't read -- documented-only
                    "column_types": {},  # sibling catalog.json isn't read; local-only enrichment
                    "original_file_path": node.get("original_file_path", ""),
                    "unique_id": unique_id,
                    "source_project": project_name,
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


def load_glossary(project_root: Path) -> dict[str, str]:
    """Project-specific synonym groups from .dbt-martmaker/glossary.yml:

        synonyms:
          - [signups, registrations]
          - [members, subscribers]

    Returns a token -> canonical-form mapping, same shape as the built-in
    SYNONYM_GROUPS produce, merged on top of them by the caller. Returns
    {} when the file is absent or PyYAML isn't installed -- the glossary
    is optional, grounding must work the same without it."""
    glossary_path = project_root / ".dbt-martmaker" / "glossary.yml"
    if not glossary_path.exists() or yaml is None:
        return {}
    data = yaml.safe_load(glossary_path.read_text()) or {}
    canonical = {}
    for group in data.get("synonyms", []) or []:
        terms = [str(t).strip().lower() for t in group if str(t).strip()]
        if not terms:
            continue
        canonical_form = min(terms)
        for term in terms:
            canonical[term] = canonical_form
    return canonical


def canonical_map(project_root: Path | None) -> dict[str, str]:
    """Built-in synonyms, with a project's own glossary.yml layered on
    top -- a project's own vocabulary choices win over the built-in
    defaults on any overlapping term."""
    merged = dict(_BUILTIN_SYNONYM_CANONICAL)
    if project_root is not None:
        merged.update(load_glossary(project_root))
    return merged


def load_corrections(project_root: Path) -> dict[str, str]:
    """Reference -> correct model name, from every line ever appended to
    .dbt-martmaker/corrections.jsonl. A stale or malformed line is skipped,
    never fatal -- the log is a growing append-only file a human (or the
    calling skill, on the human's behalf) writes to, not a curated one."""
    corrections_path = project_root / ".dbt-martmaker" / "corrections.jsonl"
    if not corrections_path.exists():
        return {}
    corrections = {}
    for line in corrections_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            reference = str(entry["reference"]).strip().lower()
            corrections[reference] = str(entry["correct_candidate"])
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
    return corrections


def _tokenize(text: str, canonical: dict[str, str] | None = None) -> set[str]:
    tokens = {tok for tok in re.split(r"[^a-z0-9]+", text.lower()) if len(tok) > 2}
    canonical = canonical if canonical is not None else _BUILTIN_SYNONYM_CANONICAL
    # Canonicalize known synonyms so "clients" and "customers" overlap --
    # every caller (reference, name, description tokens) gets this for free.
    return {canonical.get(tok, tok) for tok in tokens}


def _name_tokens(name: str, canonical: dict[str, str] | None = None) -> set[str]:
    # dbt layer prefixes (stg_/int_/dim_/...) are naming-convention noise, not
    # business meaning -- a user saying "payments" never says "stg payments".
    return _tokenize(name, canonical) - LAYER_PREFIXES


def score(reference: str, candidate: dict, canonical: dict[str, str] | None = None) -> float:
    ref_tokens = _tokenize(reference, canonical)
    if not ref_tokens:
        return 0.0

    # Name matching is token-containment based, not raw character-sequence
    # ratio -- difflib.SequenceMatcher.ratio() on two short, unrelated strings
    # (e.g. "widgets_inventory" vs "int_orders") produces meaningless
    # coincidental scores just from shared characters. Token overlap only
    # scores what's genuinely the same word.
    name_tokens = _name_tokens(candidate["name"], canonical)
    name_score = len(ref_tokens & name_tokens) / len(ref_tokens) if name_tokens else 0.0

    # Same reasoning for descriptions, but capped: an incidental word mention
    # in an otherwise-unrelated model's description (e.g. "payments" appearing
    # once in int_orders' description) is real but weaker evidence than an
    # actual name match, and must never be allowed to outscore or masquerade
    # as one -- so it's capped below the point where it could ever auto-match
    # on its own.
    desc_score = 0.0
    if candidate["description"]:
        desc_tokens = _tokenize(candidate["description"], canonical)
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


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def embed_texts(texts: list[str], api_key: str, model: str) -> list[list[float]] | None:
    """Calls the Voyage AI embeddings API (Anthropic's recommended
    embeddings provider) for a batch of texts in a single request. Returns
    None on any failure whatsoever -- a bad key, no network, a timeout, an
    unexpected response shape -- never raises. Embeddings are enrichment
    only: a failed call must leave grounding exactly as capable as it is
    with no VOYAGE_API_KEY set at all."""
    if not texts:
        return []
    body = json.dumps({"input": texts, "model": model}).encode("utf-8")
    request = urllib.request.Request(
        VOYAGE_API_URL,
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
        vectors = data["embeddings"]
        if len(vectors) != len(texts):
            return None
        return vectors
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, KeyError, ValueError):
        return None


def embedding_similarity_matrix(
    references: list[str], candidates: list[dict], api_key: str | None, model: str
) -> dict[str, dict[str, float]]:
    """{reference: {candidate_name: cosine_similarity}} for every
    reference/candidate pair, computed from exactly one Voyage API call
    covering every reference and candidate at once. Returns {} (not an
    error) when there's no api_key, no references, or no candidates, or
    when the call fails -- callers must treat an empty result as "no
    embedding signal available", not as a blocked/failed run."""
    if not api_key or not references or not candidates:
        return {}
    candidate_texts = [f"{c['name']} {c['description']}".strip() for c in candidates]
    vectors = embed_texts(references + candidate_texts, api_key, model)
    if vectors is None:
        return {}
    ref_vectors = vectors[: len(references)]
    candidate_vectors = vectors[len(references) :]
    return {
        reference: {
            c["name"]: round(_cosine(ref_vector, cv), 3)
            for c, cv in zip(candidates, candidate_vectors)
        }
        for reference, ref_vector in zip(references, ref_vectors)
    }


def ground_one(
    reference: str,
    candidates: list[dict],
    canonical: dict[str, str] | None = None,
    corrections: dict[str, str] | None = None,
    embedding_scores: dict[str, float] | None = None,
) -> dict:
    corrections = corrections or {}
    embedding_scores = embedding_scores or {}

    # A remembered human correction is deterministic and wins outright --
    # never re-litigated by a score. If the corrected model no longer
    # exists in the candidate pool (renamed, removed), the correction is
    # stale and grounding falls through to scoring as normal rather than
    # silently trusting a reference that no longer resolves to anything.
    corrected_name = corrections.get(reference.strip().lower())
    if corrected_name:
        for c in candidates:
            if c["name"] == corrected_name:
                return {
                    "reference": reference,
                    "status": "matched",
                    "model": c["name"],
                    "description": c["description"],
                    "columns": c["columns"],
                    "columns_complete": c.get("columns_complete", False),
                    "column_types": c["column_types"],
                    "original_file_path": c["original_file_path"],
                    "source_project": c.get("source_project"),
                    "score": 1.0,
                    "matched_via": "correction",
                }

    scored = sorted(
        (
            {"model": c["name"], "score": round(score(reference, c, canonical), 3), **c}
            for c in candidates
        ),
        key=lambda c: c["score"],
        reverse=True,
    )

    if not scored or scored[0]["score"] < AMBIGUOUS_THRESHOLD:
        return _blocked_or_embedding_ambiguous(reference, candidates, embedding_scores)

    top = scored[0]
    second = scored[1]["score"] if len(scored) > 1 else 0.0
    if top["score"] >= MATCHED_THRESHOLD and (top["score"] - second) >= MATCH_MARGIN:
        return {
            "reference": reference,
            "status": "matched",
            "model": top["name"],
            "description": top["description"],
            "columns": top["columns"],
            "columns_complete": top.get("columns_complete", False),
            "column_types": top["column_types"],
            "original_file_path": top["original_file_path"],
            "source_project": top.get("source_project"),
            "score": top["score"],
            "embedding_score": embedding_scores.get(top["name"]),
        }

    shortlist = [
        {
            "model": c["name"],
            "description": c["description"],
            "columns": c["columns"],
            "columns_complete": c.get("columns_complete", False),
            "column_types": c["column_types"],
            "original_file_path": c["original_file_path"],
            "source_project": c.get("source_project"),
            "score": c["score"],
            "embedding_score": embedding_scores.get(c["name"]),
        }
        for c in scored[:MAX_SHORTLIST]
        if c["score"] >= AMBIGUOUS_THRESHOLD
    ]
    return {"reference": reference, "status": "ambiguous", "candidates": shortlist}


def _blocked_or_embedding_ambiguous(
    reference: str, candidates: list[dict], embedding_scores: dict[str, float]
) -> dict:
    """Token overlap found nothing at all. Embeddings get one more look --
    never to auto-match, only to widen a dead end into a real (if weak)
    shortlist a human or the calling agent can still evaluate."""
    if embedding_scores:
        lifted = sorted(
            (
                c
                for c in candidates
                if embedding_scores.get(c["name"], 0.0) >= EMBEDDING_AMBIGUOUS_FLOOR
            ),
            key=lambda c: embedding_scores[c["name"]],
            reverse=True,
        )[:MAX_SHORTLIST]
        if lifted:
            return {
                "reference": reference,
                "status": "ambiguous",
                "candidates": [
                    {
                        "model": c["name"],
                        "description": c["description"],
                        "columns": c["columns"],
                        "columns_complete": c.get("columns_complete", False),
                        "column_types": c["column_types"],
                        "original_file_path": c["original_file_path"],
                        "source_project": c.get("source_project"),
                        "score": 0.0,
                        "embedding_score": embedding_scores[c["name"]],
                        "matched_via": "embedding",
                    }
                    for c in lifted
                ],
            }
    return {"reference": reference, "status": "blocked", "candidates": []}


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
    candidates = staging_and_intermediate_models(manifest, catalog) + mesh_candidates(project_root)
    canonical = canonical_map(project_root)
    corrections = load_corrections(project_root)

    api_key = os.environ.get("VOYAGE_API_KEY")
    embedding_model = os.environ.get("VOYAGE_MODEL", VOYAGE_DEFAULT_MODEL)
    embedding_matrix = embedding_similarity_matrix(references, candidates, api_key, embedding_model)

    results = [
        ground_one(ref, candidates, canonical, corrections, embedding_matrix.get(ref))
        for ref in references
    ]

    semantic_metrics = semantic_layer_metrics(project_root)
    semantic_match = ground_against_semantic_layer(metric_name, semantic_metrics)

    print(
        json.dumps(
            {
                "dbt_mcp_configured": dbt_mcp_configured(project_root),
                "catalog_available": bool(catalog),
                "candidate_pool_size": len(candidates),
                "mesh_projects": len(load_mesh_projects(project_root)),
                "glossary_terms": len(load_glossary(project_root)),
                "corrections_loaded": len(corrections),
                "embeddings_available": bool(embedding_matrix),
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
