import detect_conventions


def test_naming_from_bouncer_takes_precedence(dbt_project):
    bouncer_yml = """
manifest_checks:
  - name: check_model_names
    include: ^models/marts
    model_name_pattern: ^dim_|^fct_|^rpt_
"""
    project_root = dbt_project({}, extra_files={"dbt-bouncer.yml": bouncer_yml})

    result = detect_conventions.detect_naming_from_bouncer(project_root)

    assert result is not None
    assert result["pattern"] == "^dim_|^fct_|^rpt_"
    assert result["source"] == "dbt-bouncer.yml"


def test_naming_falls_back_to_sampling_when_bouncer_absent(dbt_project):
    project_root = dbt_project(
        {},
        extra_files={
            "models/marts/finance/fct_orders.sql": "select 1",
            "models/marts/finance/dim_customers.sql": "select 1",
        },
    )

    result = detect_conventions.sample_naming_from_files(project_root)

    assert result is not None
    assert "fct_" in result["pattern"]
    assert "dim_" in result["pattern"]
    assert "sampled" in result["source"]


def test_naming_never_guessed_when_marts_folder_empty(dbt_project):
    project_root = dbt_project({})

    bouncer_result = detect_conventions.detect_naming_from_bouncer(project_root)
    sampled_result = detect_conventions.sample_naming_from_files(project_root)

    assert bouncer_result is None
    assert sampled_result is None


def test_naming_falls_back_to_models_root_when_no_marts_subfolder(dbt_project):
    """Regression guard for the real-project finding: dbt's own
    jaffle-shop starter (and plenty of real projects) keeps marts at the
    top level of models/, with no dedicated marts/ subfolder. Sampling
    must not report "nothing to sample" just because it looked in the
    wrong place."""
    project_root = dbt_project(
        {},
        extra_files={
            "models/customers.sql": "select 1",
            "models/dim_orders.sql": "select 1",
            "models/staging/stg_customers.sql": "select 1",
        },
    )

    result = detect_conventions.sample_naming_from_files(project_root)

    assert result is not None
    assert "dim_" in result["pattern"]
    assert "models" in result["source"]
    assert "staging" not in result["source"]


def test_naming_prefers_dedicated_marts_subfolder_when_it_has_files(dbt_project):
    project_root = dbt_project(
        {},
        extra_files={
            "models/marts/fct_orders.sql": "select 1",
            "models/customers.sql": "select 1",  # would confuse a naive fallback
        },
    )

    result = detect_conventions.sample_naming_from_files(project_root)

    assert result is not None
    assert "fct_" in result["pattern"]
    assert "models/marts" in result["source"]


def test_naming_reports_no_common_prefix_distinctly_from_nothing_found(dbt_project):
    """Files were genuinely found, but none share a name prefix (e.g.
    customers.sql, orders.sql) -- that's a real, reportable convention
    ("this project doesn't prefix mart names"), not the same as finding
    no files at all."""
    project_root = dbt_project(
        {},
        extra_files={
            "models/customers.sql": "select 1",
            "models/orders.sql": "select 1",
        },
    )

    result = detect_conventions.sample_naming_from_files(project_root)

    assert result is not None
    assert result["pattern"] is None
    assert "no common prefix" in result["source"]


def test_property_file_pattern_falls_back_to_models_root(dbt_project):
    project_root = dbt_project(
        {},
        extra_files={
            "models/_models.yml": "models: []",
            "models/staging/schema.yml": "models: []",
        },
    )

    result = detect_conventions.sample_property_file_pattern(project_root)

    assert result is not None
    assert "models" in result["per_directory_samples"]
    assert "models/staging" not in result["per_directory_samples"]


def test_property_file_pattern_is_sampled_per_directory_not_project_wide(dbt_project):
    """Regression guard: dbt_template itself has inconsistent property-file
    naming across marts subdirectories, so this must never assume one
    project-wide pattern -- it must return per-directory samples."""
    project_root = dbt_project(
        {},
        extra_files={
            "models/marts/finance/_finance__models.yml": "models: []",
            "models/marts/finance/fct_orders.sql": "select 1",
            "models/marts/marketing/_marketing_schema.yml": "models: []",
        },
    )

    result = detect_conventions.sample_property_file_pattern(project_root)

    assert result is not None
    samples = result["per_directory_samples"]
    assert "models/marts/finance" in samples
    assert "models/marts/marketing" in samples
    assert samples["models/marts/finance"] != samples["models/marts/marketing"]


def test_materialization_detected_from_dbt_project_yml(dbt_project):
    dbt_project_yml = """
name: test_project
version: '1.0'
models:
  test_project:
    marts:
      +materialized: table
"""
    project_root = dbt_project({})
    (project_root / "dbt_project.yml").write_text(dbt_project_yml)

    result = detect_conventions.detect_materialization(project_root)

    assert result is not None
    assert result["materialized"] == "table"
    assert result["source"] == "dbt_project.yml"


def test_materialization_none_when_not_configured(dbt_project):
    project_root = dbt_project({})
    result = detect_conventions.detect_materialization(project_root)
    assert result is None


def _test_node(unique_id: str, name: str, namespace=None, has_metadata: bool = True) -> dict:
    node = {"resource_type": "test", "name": f"{name}_test"}
    if has_metadata:
        node["test_metadata"] = {"name": name, "namespace": namespace, "kwargs": {}}
    return {unique_id: node}


def test_existing_tests_classifies_builtin_package_and_custom(dbt_project):
    """Regression guard for the real shape found in dbt_template's manifest:
    built-in tests have no namespace, package tests (dbt_expectations,
    dbt_utils) carry one, and a project's own custom generic test (e.g.
    not_negative) has no namespace but also isn't one of dbt's 4 built-ins."""
    nodes = {}
    nodes.update(_test_node("test.p.not_null_a", "not_null"))
    nodes.update(_test_node("test.p.not_null_b", "not_null"))
    nodes.update(_test_node("test.p.unique_a", "unique"))
    nodes.update(_test_node("test.p.expect_a", "expect_table_row_count_to_be_between", namespace="dbt_expectations"))
    nodes.update(_test_node("test.p.custom_a", "not_negative"))
    nodes.update(_test_node("test.p.custom_b", "not_negative"))
    project_root = dbt_project(nodes)

    result = detect_conventions.detect_existing_tests(project_root)

    assert result["builtin"] == {"not_null": 2, "unique": 1}
    assert result["package"] == [
        {"namespace": "dbt_expectations", "name": "expect_table_row_count_to_be_between", "count": 1}
    ]
    assert result["custom"] == [{"name": "not_negative", "count": 2}]


def test_existing_tests_ignores_singular_tests(dbt_project):
    """Singular tests (raw SQL, no test_metadata) aren't generic tests and
    shouldn't be treated as an existing generic-test convention."""
    nodes = {}
    nodes.update(_test_node("test.p.singular_a", "some_singular_test", has_metadata=False))
    project_root = dbt_project(nodes)

    result = detect_conventions.detect_existing_tests(project_root)

    assert result["builtin"] == {}
    assert result["package"] == []
    assert result["custom"] == []


def test_existing_tests_none_when_no_manifest(dbt_project):
    project_root = dbt_project({})
    (project_root / "target" / "manifest.json").unlink()

    result = detect_conventions.detect_existing_tests(project_root)

    assert result["builtin"] == {}
    assert "no target/manifest.json" in result["source"]


def test_yaml_dependent_functions_degrade_gracefully_without_pyyaml(dbt_project, monkeypatch):
    """Regression guard: this module used to sys.exit(1) at import time
    if PyYAML was missing, which made it impossible for another script
    (doctor.py) to import and reuse the YAML-independent parts of it. The
    functions that genuinely need YAML must now degrade to None instead
    of crashing; the ones that never needed it are unaffected."""
    monkeypatch.setattr(detect_conventions, "yaml", None)
    bouncer_yml = "manifest_checks:\n  - name: check_model_names\n    include: ^models/marts\n"
    project_root = dbt_project({}, extra_files={"dbt-bouncer.yml": bouncer_yml})

    assert detect_conventions.detect_naming_from_bouncer(project_root) is None
    assert detect_conventions.detect_materialization(project_root) is None


def test_sample_naming_from_files_never_needed_pyyaml(dbt_project, monkeypatch):
    monkeypatch.setattr(detect_conventions, "yaml", None)
    project_root = dbt_project(
        {}, extra_files={"models/customers.sql": "select 1"}
    )

    result = detect_conventions.sample_naming_from_files(project_root)

    assert result is not None
