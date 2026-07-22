import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import make_model
from dbt_martsmith import cli

SHEET_CSV = """metric,definition,calculation,source_tables
Payment count,Number of payments processed,count(payment_id),payments
"""

AMBIGUOUS_SHEET_CSV = """metric,definition,calculation,source_tables
Customer count,Total distinct customers,count(distinct customer_id),customers
"""


def _write_sheet(project_root: Path, content: str, name: str = "metrics") -> Path:
    sheets_dir = project_root / ".dbt-martsmith" / "sheets"
    sheets_dir.mkdir(parents=True, exist_ok=True)
    path = sheets_dir / f"{name}.csv"
    path.write_text(content)
    return path


def test_run_writes_proposal_and_draft_for_matched_row(dbt_project, monkeypatch):
    nodes = {}
    nodes.update(make_model("stg_payments", "staging", columns=["payment_id"]))
    project_root = dbt_project(nodes)
    sheet_path = _write_sheet(project_root, SHEET_CSV)

    monkeypatch.chdir(project_root)
    cli.cmd_run(SimpleNamespace(sheet=str(sheet_path)))

    drafts_dir = project_root / ".dbt-martsmith" / "drafts" / "metrics"
    proposal = (drafts_dir / "proposal.md").read_text()
    assert "Payment count" in proposal
    assert "matched `stg_payments`" in proposal

    model_files = list((drafts_dir / "models").glob("draft__*.sql"))
    assert len(model_files) == 1
    assert "ref('stg_payments')" in model_files[0].read_text()

    meta = json.loads((drafts_dir / "meta.json").read_text())
    assert meta["rows"][0]["status"] == "matched"


def test_run_is_idempotent_on_unchanged_sheet(dbt_project, monkeypatch, capsys):
    nodes = {}
    nodes.update(make_model("stg_payments", "staging"))
    project_root = dbt_project(nodes)
    sheet_path = _write_sheet(project_root, SHEET_CSV)

    monkeypatch.chdir(project_root)
    cli.cmd_run(SimpleNamespace(sheet=str(sheet_path)))
    capsys.readouterr()  # discard first run's output

    cli.cmd_run(SimpleNamespace(sheet=str(sheet_path)))
    output = capsys.readouterr().out
    assert "SKIPPED" in output


def test_run_ambiguous_row_produces_no_draft_file_but_flags_open_question(dbt_project, monkeypatch):
    nodes = {}
    nodes.update(make_model("stg_customers", "staging"))
    nodes.update(make_model("int_customers", "intermediate", description="basic customer info"))
    project_root = dbt_project(nodes)
    sheet_path = _write_sheet(project_root, AMBIGUOUS_SHEET_CSV)

    monkeypatch.chdir(project_root)
    cli.cmd_run(SimpleNamespace(sheet=str(sheet_path)))

    drafts_dir = project_root / ".dbt-martsmith" / "drafts" / "metrics"
    proposal = (drafts_dir / "proposal.md").read_text()
    assert "Open questions" in proposal
    assert "Confirm which of" in proposal
    assert not list((drafts_dir / "models").glob("draft__*.sql"))


def test_run_errors_on_unconfirmed_draft_sheet(dbt_project, monkeypatch, capsys):
    project_root = dbt_project({})
    sheet_path = _write_sheet(project_root, SHEET_CSV, name="metrics.draft")
    # _write_sheet produces "metrics.draft.csv" via the name param -- rename
    # explicitly to be unambiguous about what's under test.
    draft_path = sheet_path.parent / "metrics.draft.csv"
    sheet_path.rename(draft_path)

    monkeypatch.chdir(project_root)
    with pytest.raises(SystemExit) as exc_info:
        cli.cmd_run(SimpleNamespace(sheet=str(draft_path)))

    assert exc_info.value.code == 1
    assert "unconfirmed draft sheet" in capsys.readouterr().out


def test_run_errors_when_no_manifest(dbt_project, monkeypatch, capsys):
    project_root = dbt_project({})
    (project_root / "target" / "manifest.json").unlink()
    sheet_path = _write_sheet(project_root, SHEET_CSV)

    monkeypatch.chdir(project_root)
    with pytest.raises(SystemExit) as exc_info:
        cli.cmd_run(SimpleNamespace(sheet=str(sheet_path)))

    assert exc_info.value.code == 1
    output = json.loads(capsys.readouterr().out)
    assert output["error"] == "no_manifest"


def test_init_scaffolds_template_sheet(dbt_project, monkeypatch):
    project_root = dbt_project({})
    monkeypatch.chdir(project_root)

    cli.cmd_init(SimpleNamespace(name="metrics"))

    dest = project_root / ".dbt-martsmith" / "sheets" / "metrics.csv"
    assert dest.exists()
    assert "metric,definition,calculation,source_tables" in dest.read_text()


def test_init_refuses_to_overwrite_existing_sheet(dbt_project, monkeypatch, capsys):
    project_root = dbt_project({})
    _write_sheet(project_root, SHEET_CSV)
    monkeypatch.chdir(project_root)

    with pytest.raises(SystemExit) as exc_info:
        cli.cmd_init(SimpleNamespace(name="metrics"))

    assert exc_info.value.code == 1
    assert "already exists" in capsys.readouterr().out
