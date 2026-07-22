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
