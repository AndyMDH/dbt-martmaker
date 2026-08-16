import json

import pytest

import ground
from conftest import make_model


def test_matched_on_clean_name_hit(dbt_project):
    nodes = {}
    nodes.update(make_model("stg_payments", "staging", columns=["payment_id", "payment_method"]))
    project_root = dbt_project(nodes)

    manifest = ground.load_manifest(project_root)
    candidates = ground.staging_and_intermediate_models(manifest)
    result = ground.ground_one("payments", candidates)

    assert result["status"] == "matched"
    assert result["model"] == "stg_payments"


def test_ambiguous_on_genuine_tie(dbt_project):
    nodes = {}
    nodes.update(make_model("stg_customers", "staging"))
    nodes.update(
        make_model(
            "int_customers",
            "intermediate",
            description="This table has basic information about a customer",
        )
    )
    project_root = dbt_project(nodes)

    manifest = ground.load_manifest(project_root)
    candidates = ground.staging_and_intermediate_models(manifest)
    result = ground.ground_one("customers", candidates)

    assert result["status"] == "ambiguous"
    matched_names = {c["model"] for c in result["candidates"]}
    assert matched_names == {"stg_customers", "int_customers"}


def test_blocked_when_nothing_matches(dbt_project):
    nodes = {}
    nodes.update(make_model("stg_payments", "staging"))
    nodes.update(make_model("int_orders", "intermediate", description="orders and payments facts"))
    project_root = dbt_project(nodes)

    manifest = ground.load_manifest(project_root)
    candidates = ground.staging_and_intermediate_models(manifest)
    result = ground.ground_one("widgets_inventory", candidates)

    assert result["status"] == "blocked"
    assert result["candidates"] == []


def test_incidental_description_mention_does_not_outrank_real_name_match(dbt_project):
    """Regression test: a coincidental word match in an unrelated model's
    description (e.g. "payments" mentioned once inside int_orders' description)
    must never outscore or tie with an actual name match on stg_payments."""
    nodes = {}
    nodes.update(make_model("stg_payments", "staging"))
    nodes.update(
        make_model(
            "int_orders",
            "intermediate",
            description="This table has basic information about orders, as well as some derived facts based on payments",
        )
    )
    project_root = dbt_project(nodes)

    manifest = ground.load_manifest(project_root)
    candidates = ground.staging_and_intermediate_models(manifest)
    result = ground.ground_one("payments", candidates)

    assert result["status"] == "matched"
    assert result["model"] == "stg_payments"


def test_description_only_evidence_never_auto_matches(dbt_project):
    """A model with zero name-token overlap but a description that mentions
    the reference term should surface as ambiguous evidence at most, never
    as a confident auto-match on its own."""
    nodes = {}
    nodes.update(
        make_model(
            "int_customer_orders",
            "intermediate",
            description="Aggregates customer orders and total revenue",
        )
    )
    project_root = dbt_project(nodes)

    manifest = ground.load_manifest(project_root)
    candidates = ground.staging_and_intermediate_models(manifest)
    result = ground.ground_one("revenue", candidates)

    assert result["status"] != "matched"


def test_only_staging_and_intermediate_models_are_candidates(dbt_project):
    """Mart-layer models themselves must never be grounding candidates --
    dbt-martmaker builds marts, it doesn't match against other marts."""
    nodes = {}
    nodes.update(make_model("stg_payments", "staging"))
    nodes["model.test_project.fct_orders"] = {
        "resource_type": "model",
        "name": "fct_orders",
        "original_file_path": "models/marts/finance/fct_orders.sql",
        "description": "",
        "columns": {},
    }
    project_root = dbt_project(nodes)

    manifest = ground.load_manifest(project_root)
    candidates = ground.staging_and_intermediate_models(manifest)

    assert all(c["name"] != "fct_orders" for c in candidates)


def test_missing_manifest_errors_loudly(dbt_project, capsys):
    project_root = dbt_project({})
    (project_root / "target" / "manifest.json").unlink()

    with pytest.raises(SystemExit) as exc_info:
        ground.load_manifest(project_root)

    assert exc_info.value.code == 1
    output = json.loads(capsys.readouterr().out)
    assert output["error"] == "no_manifest"


def test_dbt_mcp_configured_detection(dbt_project):
    project_root = dbt_project(
        {},
        extra_files={
            ".mcp.json": json.dumps(
                {"mcpServers": {"dbt": {"command": "uvx", "args": ["dbt-mcp"]}}}
            )
        },
    )
    assert ground.dbt_mcp_configured(project_root) is True


def test_dbt_mcp_not_configured_when_absent(dbt_project):
    project_root = dbt_project({})
    assert ground.dbt_mcp_configured(project_root) is False


def test_synonym_match_clients_to_customers(dbt_project):
    """The exact gap flagged in review: a stakeholder saying "clients"
    against a project that models stg_customers must not read as blocked."""
    nodes = {}
    nodes.update(make_model("stg_customers", "staging"))
    project_root = dbt_project(nodes)

    manifest = ground.load_manifest(project_root)
    candidates = ground.staging_and_intermediate_models(manifest)
    result = ground.ground_one("clients", candidates)

    assert result["status"] == "matched"
    assert result["model"] == "stg_customers"


def test_synonym_match_is_symmetric(dbt_project):
    nodes = {}
    nodes.update(make_model("stg_clients", "staging"))
    project_root = dbt_project(nodes)

    manifest = ground.load_manifest(project_root)
    candidates = ground.staging_and_intermediate_models(manifest)
    result = ground.ground_one("customers", candidates)

    assert result["status"] == "matched"
    assert result["model"] == "stg_clients"


def test_synonym_does_not_widen_unrelated_matches(dbt_project):
    """Regression guard: synonym canonicalization must not accidentally
    make unrelated terms overlap -- "orders" must still not match a model
    that's genuinely about something else."""
    nodes = {}
    nodes.update(make_model("stg_customers", "staging"))
    project_root = dbt_project(nodes)

    manifest = ground.load_manifest(project_root)
    candidates = ground.staging_and_intermediate_models(manifest)
    result = ground.ground_one("orders", candidates)

    assert result["status"] == "blocked"


def test_column_types_attached_when_catalog_present(dbt_project):
    nodes = {}
    nodes.update(make_model("stg_payments", "staging", columns=["payment_id", "amount"]))
    catalog = {
        "nodes": {
            "model.test_project.stg_payments": {
                "columns": {
                    "payment_id": {"type": "integer"},
                    "amount": {"type": "numeric"},
                }
            }
        }
    }
    project_root = dbt_project(
        nodes, extra_files={"target/catalog.json": json.dumps(catalog)}
    )

    manifest = ground.load_manifest(project_root)
    catalog_data = ground.load_catalog(project_root)
    candidates = ground.staging_and_intermediate_models(manifest, catalog_data)
    result = ground.ground_one("payments", candidates)

    assert result["status"] == "matched"
    assert result["column_types"] == {"payment_id": "integer", "amount": "numeric"}


def test_column_types_empty_without_catalog(dbt_project):
    nodes = {}
    nodes.update(make_model("stg_payments", "staging", columns=["payment_id"]))
    project_root = dbt_project(nodes)

    manifest = ground.load_manifest(project_root)
    catalog_data = ground.load_catalog(project_root)
    candidates = ground.staging_and_intermediate_models(manifest, catalog_data)
    result = ground.ground_one("payments", candidates)

    assert catalog_data == {}
    assert result["column_types"] == {}


def test_semantic_layer_metrics_empty_without_semantic_manifest(dbt_project):
    project_root = dbt_project({})
    assert ground.semantic_layer_metrics(project_root) == []


def test_semantic_layer_metrics_read_when_present(dbt_project):
    semantic_manifest = {
        "metrics": [
            {
                "name": "avg_payment_amount",
                "label": "Average Payment Amount",
                "description": "Average dollar amount per payment",
            }
        ]
    }
    project_root = dbt_project(
        {}, extra_files={"target/semantic_manifest.json": json.dumps(semantic_manifest)}
    )

    metrics = ground.semantic_layer_metrics(project_root)

    assert metrics == [
        {
            "name": "avg_payment_amount",
            "label": "Average Payment Amount",
            "description": "Average dollar amount per payment",
        }
    ]


def test_semantic_layer_metrics_label_defaults_empty_when_absent(dbt_project):
    semantic_manifest = {"metrics": [{"name": "avg_payment_amount", "description": ""}]}
    project_root = dbt_project(
        {}, extra_files={"target/semantic_manifest.json": json.dumps(semantic_manifest)}
    )

    metrics = ground.semantic_layer_metrics(project_root)

    assert metrics[0]["label"] == ""


def test_semantic_layer_confident_hit_is_surfaced():
    semantic_metrics = [{"name": "avg_payment_amount", "label": "", "description": ""}]

    match = ground.ground_against_semantic_layer("avg payment amount", semantic_metrics)

    assert match is not None
    assert match["metric"] == "avg_payment_amount"


def test_semantic_layer_matches_on_label_when_name_diverges():
    """Regression guard: a stakeholder's natural phrasing ("Marketing ROI")
    must match a metric via its human-readable label even when the metric's
    internal name is an abbreviated snake_case id the phrasing shares no
    tokens with."""
    semantic_metrics = [
        {"name": "mktg_roi_pct", "label": "Marketing ROI", "description": ""}
    ]

    match = ground.ground_against_semantic_layer("Marketing ROI", semantic_metrics)

    assert match is not None
    assert match["metric"] == "mktg_roi_pct"
    assert match["label"] == "Marketing ROI"


def test_semantic_layer_weak_overlap_never_auto_matches():
    """Regression guard: a metric name sharing no real tokens with any
    existing Semantic Layer metric (by name or label) must stay unmatched,
    never a guess."""
    semantic_metrics = [{"name": "avg_payment_amount", "label": "", "description": ""}]

    match = ground.ground_against_semantic_layer("Monthly churned users", semantic_metrics)

    assert match is None


def test_semantic_layer_match_none_when_no_metrics_defined():
    assert ground.ground_against_semantic_layer("Average payment amount", []) is None


# --- glossary ---------------------------------------------------------


def test_glossary_absent_returns_empty(dbt_project):
    project_root = dbt_project({})
    assert ground.load_glossary(project_root) == {}


def test_glossary_read_and_canonicalized(dbt_project):
    project_root = dbt_project(
        {},
        extra_files={
            ".dbt-martmaker/glossary.yml": "synonyms:\n  - [signups, registrations]\n"
        },
    )
    glossary = ground.load_glossary(project_root)
    assert glossary["signups"] == glossary["registrations"]


def test_glossary_merges_on_top_of_builtin(dbt_project):
    project_root = dbt_project(
        {},
        extra_files={
            ".dbt-martmaker/glossary.yml": "synonyms:\n  - [signups, registrations]\n"
        },
    )
    merged = ground.canonical_map(project_root)
    assert merged["customer"] == merged["client"]  # built-in still present
    assert merged["signups"] == merged["registrations"]  # project's own added


def test_glossary_enables_a_real_match(dbt_project):
    """Regression guard: a term only in the project's own glossary, not
    the built-in list, must still ground successfully end to end."""
    nodes = {}
    nodes.update(make_model("stg_registrations", "staging"))
    project_root = dbt_project(
        nodes,
        extra_files={
            ".dbt-martmaker/glossary.yml": "synonyms:\n  - [signups, registrations]\n"
        },
    )
    manifest = ground.load_manifest(project_root)
    candidates = ground.staging_and_intermediate_models(manifest)
    canonical = ground.canonical_map(project_root)

    result = ground.ground_one("signups", candidates, canonical=canonical)

    assert result["status"] == "matched"
    assert result["model"] == "stg_registrations"


# --- corrections --------------------------------------------------------


def test_corrections_absent_returns_empty(dbt_project):
    project_root = dbt_project({})
    assert ground.load_corrections(project_root) == {}


def test_corrections_applied_deterministically_even_below_threshold(dbt_project):
    """A correction must win outright, even for a reference/model pair
    that would otherwise score far below AMBIGUOUS_THRESHOLD."""
    nodes = {}
    nodes.update(make_model("stg_registrations", "staging"))
    project_root = dbt_project(
        nodes,
        extra_files={
            ".dbt-martmaker/corrections.jsonl": json.dumps(
                {
                    "reference": "signups",
                    "wrong_candidate": None,
                    "correct_candidate": "stg_registrations",
                }
            )
            + "\n"
        },
    )
    manifest = ground.load_manifest(project_root)
    candidates = ground.staging_and_intermediate_models(manifest)
    corrections = ground.load_corrections(project_root)

    result = ground.ground_one("signups", candidates, corrections=corrections)

    assert result["status"] == "matched"
    assert result["model"] == "stg_registrations"
    assert result["matched_via"] == "correction"


def test_stale_correction_falls_through_to_normal_scoring(dbt_project):
    """The corrected model no longer exists (renamed/removed) -- the
    correction must never be trusted blindly; grounding falls back to
    scoring the reference against whatever candidates actually exist."""
    nodes = {}
    nodes.update(make_model("stg_payments", "staging"))
    project_root = dbt_project(
        nodes,
        extra_files={
            ".dbt-martmaker/corrections.jsonl": json.dumps(
                {"reference": "payments", "correct_candidate": "stg_payments_old_name"}
            )
            + "\n"
        },
    )
    manifest = ground.load_manifest(project_root)
    candidates = ground.staging_and_intermediate_models(manifest)
    corrections = ground.load_corrections(project_root)

    result = ground.ground_one("payments", candidates, corrections=corrections)

    assert result["status"] == "matched"
    assert result["model"] == "stg_payments"
    assert "matched_via" not in result


def test_malformed_correction_lines_are_skipped(dbt_project):
    project_root = dbt_project(
        {},
        extra_files={
            ".dbt-martmaker/corrections.jsonl": "not json\n"
            + json.dumps({"reference": "orders", "correct_candidate": "stg_orders"})
            + "\n"
        },
    )
    corrections = ground.load_corrections(project_root)
    assert corrections == {"orders": "stg_orders"}


# --- dbt Mesh -------------------------------------------------------------


def test_mesh_candidates_empty_without_config(dbt_project):
    project_root = dbt_project({})
    assert ground.mesh_candidates(project_root) == []


def test_mesh_candidates_only_public_models(tmp_path, dbt_project):
    sibling_root = tmp_path / "sibling"
    sibling_target = sibling_root / "target"
    sibling_target.mkdir(parents=True)
    sibling_manifest = {
        "nodes": {
            "model.sibling.stg_shared_customers": {
                "resource_type": "model",
                "name": "stg_shared_customers",
                "description": "",
                "original_file_path": "models/staging/stg_shared_customers.sql",
                "columns": {},
                "access": "public",
            },
            "model.sibling.stg_internal_only": {
                "resource_type": "model",
                "name": "stg_internal_only",
                "description": "",
                "original_file_path": "models/staging/stg_internal_only.sql",
                "columns": {},
                "access": "private",
            },
        }
    }
    (sibling_target / "manifest.json").write_text(json.dumps(sibling_manifest))

    project_root = dbt_project(
        {},
        extra_files={
            ".dbt-martmaker/mesh_manifests.yml": (
                "projects:\n"
                "  - name: sibling\n"
                f"    manifest: {sibling_target / 'manifest.json'}\n"
            )
        },
    )

    candidates = ground.mesh_candidates(project_root)

    names = {c["name"] for c in candidates}
    assert names == {"stg_shared_customers"}
    assert candidates[0]["source_project"] == "sibling"


def test_mesh_candidates_skip_missing_manifest_file(dbt_project):
    project_root = dbt_project(
        {},
        extra_files={
            ".dbt-martmaker/mesh_manifests.yml": (
                "projects:\n  - name: gone\n    manifest: ../nowhere/target/manifest.json\n"
            )
        },
    )
    assert ground.mesh_candidates(project_root) == []


# --- embeddings (Voyage AI) -- network layer mocked, never called for real ---


def test_embed_texts_returns_none_on_network_error(monkeypatch):
    def _raise(*args, **kwargs):
        raise OSError("network unreachable")

    monkeypatch.setattr(ground.urllib.request, "urlopen", _raise)
    assert ground.embed_texts(["hello"], api_key="fake", model="voyage-4-lite") is None


def test_embed_texts_returns_none_on_mismatched_response_length(monkeypatch):
    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"embeddings": [[0.1, 0.2]]}).encode("utf-8")

    monkeypatch.setattr(ground.urllib.request, "urlopen", lambda *a, **k: _FakeResponse())
    result = ground.embed_texts(["one", "two"], api_key="fake", model="voyage-4-lite")
    assert result is None


def test_embedding_similarity_matrix_empty_without_api_key(dbt_project):
    nodes = {}
    nodes.update(make_model("stg_payments", "staging"))
    project_root = dbt_project(nodes)
    manifest = ground.load_manifest(project_root)
    candidates = ground.staging_and_intermediate_models(manifest)

    matrix = ground.embedding_similarity_matrix(["payments"], candidates, api_key=None, model="voyage-4-lite")

    assert matrix == {}


def test_embedding_similarity_matrix_computes_cosine(monkeypatch):
    # reference vector and candidate vector are identical -> cosine 1.0
    monkeypatch.setattr(
        ground,
        "embed_texts",
        lambda texts, api_key, model: [[1.0, 0.0], [1.0, 0.0]],
    )
    candidates = [{"name": "stg_signups", "description": ""}]

    matrix = ground.embedding_similarity_matrix(
        ["signups"], candidates, api_key="fake", model="voyage-4-lite"
    )

    assert matrix == {"signups": {"stg_signups": 1.0}}


def test_cosine_orthogonal_vectors_score_zero():
    assert ground._cosine([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_ground_one_blocked_lifted_to_ambiguous_by_embedding(dbt_project):
    """The whole point of embeddings: catch what token overlap misses
    entirely, without ever letting it silently auto-match."""
    nodes = {}
    nodes.update(make_model("stg_signups", "staging"))
    project_root = dbt_project(nodes)
    manifest = ground.load_manifest(project_root)
    candidates = ground.staging_and_intermediate_models(manifest)

    # "registrations" shares no tokens with "stg_signups" -- would be blocked.
    result = ground.ground_one(
        "registrations", candidates, embedding_scores={"stg_signups": 0.9}
    )

    assert result["status"] == "ambiguous"
    assert result["candidates"][0]["model"] == "stg_signups"
    assert result["candidates"][0]["matched_via"] == "embedding"


def test_ground_one_embedding_below_floor_stays_blocked(dbt_project):
    nodes = {}
    nodes.update(make_model("stg_signups", "staging"))
    project_root = dbt_project(nodes)
    manifest = ground.load_manifest(project_root)
    candidates = ground.staging_and_intermediate_models(manifest)

    result = ground.ground_one(
        "registrations", candidates, embedding_scores={"stg_signups": 0.5}
    )

    assert result["status"] == "blocked"


def test_columns_complete_false_when_manifest_only(dbt_project):
    """Regression guard for the real-project finding: manifest.json only
    lists a column when someone documented it in schema.yml, which is
    usually a strict subset of what actually exists. columns_complete
    must say so, rather than implying the list is exhaustive."""
    nodes = {}
    nodes.update(make_model("stg_payments", "staging", columns=["payment_id"]))
    project_root = dbt_project(nodes)

    manifest = ground.load_manifest(project_root)
    candidates = ground.staging_and_intermediate_models(manifest)
    result = ground.ground_one("payments", candidates)

    assert result["status"] == "matched"
    assert result["columns"] == ["payment_id"]
    assert result["columns_complete"] is False


def test_columns_complete_true_and_full_when_catalog_present(dbt_project):
    """The real fix: when catalog.json is present, the column list comes
    from it (every real column), not just the manifest's documented
    subset -- catalog.json is strictly more complete."""
    nodes = {}
    nodes.update(make_model("stg_payments", "staging", columns=["payment_id"]))
    catalog = {
        "nodes": {
            "model.test_project.stg_payments": {
                "columns": {
                    "payment_id": {"type": "integer"},
                    "order_id": {"type": "integer"},
                    "amount": {"type": "numeric"},
                }
            }
        }
    }
    project_root = dbt_project(
        nodes, extra_files={"target/catalog.json": json.dumps(catalog)}
    )

    manifest = ground.load_manifest(project_root)
    catalog_data = ground.load_catalog(project_root)
    candidates = ground.staging_and_intermediate_models(manifest, catalog_data)
    result = ground.ground_one("payments", candidates)

    assert result["columns_complete"] is True
    assert result["columns"] == ["amount", "order_id", "payment_id"]


def test_columns_complete_propagated_on_ambiguous_shortlist(dbt_project):
    nodes = {}
    nodes.update(make_model("stg_customers", "staging"))
    nodes.update(
        make_model(
            "int_customers", "intermediate", description="basic customer information"
        )
    )
    project_root = dbt_project(nodes)

    manifest = ground.load_manifest(project_root)
    candidates = ground.staging_and_intermediate_models(manifest)
    result = ground.ground_one("customers", candidates)

    assert result["status"] == "ambiguous"
    assert all(c["columns_complete"] is False for c in result["candidates"])


def test_columns_complete_false_for_mesh_candidates():
    candidates = [
        {
            "name": "stg_shared",
            "description": "",
            "columns": ["id"],
            "columns_complete": False,
            "column_types": {},
            "original_file_path": "models/staging/stg_shared.sql",
            "source_project": "sibling",
        }
    ]
    result = ground.ground_one("shared", candidates)
    assert result["status"] == "matched"
    assert result["columns_complete"] is False


def test_ground_one_embedding_never_auto_matches_by_itself(dbt_project):
    """Even a perfect embedding score must never produce status: matched
    on its own -- only ambiguous. Confirmed match still requires the
    existing token-overlap confidence bar."""
    nodes = {}
    nodes.update(make_model("stg_signups", "staging"))
    project_root = dbt_project(nodes)
    manifest = ground.load_manifest(project_root)
    candidates = ground.staging_and_intermediate_models(manifest)

    result = ground.ground_one(
        "registrations", candidates, embedding_scores={"stg_signups": 1.0}
    )

    assert result["status"] != "matched"
