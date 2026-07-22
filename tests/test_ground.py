import json

import pytest

from dbt_martsmith import ground
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
    dbt-martsmith builds marts, it doesn't match against other marts."""
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
