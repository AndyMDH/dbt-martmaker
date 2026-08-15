import doctor


def test_not_ready_when_no_dbt_project(tmp_path):
    result = doctor.build_report(tmp_path)
    assert result["ready"] is False
    assert result["project_root"] is None
    assert any("dbt_project.yml" in m for m in result["messages"])


def test_ready_when_manifest_and_pyyaml_present(dbt_project):
    project_root = dbt_project({})
    result = doctor.build_report(project_root)
    assert result["ready"] is True
    assert result["checks"]["manifest_present"] is True
    assert result["checks"]["pyyaml_installed"] is True


def test_not_ready_when_manifest_missing(tmp_path):
    (tmp_path / "dbt_project.yml").write_text("name: test_project\nversion: '1.0'\n")
    result = doctor.build_report(tmp_path)
    assert result["ready"] is False
    assert result["checks"]["manifest_present"] is False
    assert any("dbt parse" in m for m in result["messages"])


def test_catalog_and_semantic_manifest_absence_is_reported_not_blocking(dbt_project):
    """Regression guard: neither catalog.json nor semantic_manifest.json is
    required -- both are enrichment, and most projects won't have either."""
    project_root = dbt_project({})
    result = doctor.build_report(project_root)
    assert result["ready"] is True
    assert result["checks"]["catalog_present"] is False
    assert result["checks"]["semantic_manifest_present"] is False


def test_walks_up_from_a_subdirectory(dbt_project):
    project_root = dbt_project({})
    subdir = project_root / "models" / "marts" / "finance"
    subdir.mkdir(parents=True)
    result = doctor.build_report(subdir)
    assert result["ready"] is True
    assert result["project_root"] == str(project_root.resolve())


def test_no_convention_source_is_reported_when_bouncer_and_marts_both_absent(dbt_project):
    project_root = dbt_project({})
    result = doctor.build_report(project_root)
    assert result["checks"]["dbt_bouncer_config_present"] is False
    assert result["checks"]["marts_dir_has_files"] is False
    assert any("nothing to sample" in m for m in result["messages"])
