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


def test_semantic_layer_confident_hit_is_surfaced(dbt_project):
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
