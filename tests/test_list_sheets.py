import json

import list_sheets


def test_no_sheets_dir_reports_absent(tmp_path):
    result = list_sheets_report(tmp_path)
    assert result["sheets_dir_present"] is False
    assert result["sheets"] == []


def test_sheet_with_no_proposal_yet(tmp_path):
    sheets_dir = tmp_path / ".dbt-martmaker" / "sheets"
    sheets_dir.mkdir(parents=True)
    (sheets_dir / "churn-metrics.csv").write_text("metric,description,reasoning,importance\n")

    result = list_sheets_report(tmp_path)

    assert result["sheets_dir_present"] is True
    assert result["sheets"][0]["slug"] == "churn-metrics"
    assert result["sheets"][0]["status"] == "no proposal yet"


def test_sheet_matching_checksum_reports_meta_status(tmp_path):
    sheets_dir = tmp_path / ".dbt-martmaker" / "sheets"
    sheets_dir.mkdir(parents=True)
    sheet_path = sheets_dir / "churn-metrics.csv"
    sheet_path.write_text("metric,description,reasoning,importance\n")

    import hashlib

    checksum = hashlib.sha256(sheet_path.read_bytes()).hexdigest()
    drafts_dir = tmp_path / ".dbt-martmaker" / "drafts" / "churn-metrics"
    drafts_dir.mkdir(parents=True)
    (drafts_dir / "meta.json").write_text(
        json.dumps(
            {
                "sheet_checksum": checksum,
                "generated_at": "2026-08-01T00:00:00Z",
                "status": "proposed",
                "rows": [
                    {"metric": "A", "status": "matched"},
                    {"metric": "B", "status": "blocked"},
                ],
            }
        )
    )

    result = list_sheets_report(tmp_path)

    entry = result["sheets"][0]
    assert entry["status"] == "proposed"
    assert entry["row_counts"] == {"matched": 1, "ambiguous": 0, "blocked": 1}


def test_sheet_with_stale_checksum_reported_as_stale(tmp_path):
    sheets_dir = tmp_path / ".dbt-martmaker" / "sheets"
    sheets_dir.mkdir(parents=True)
    sheet_path = sheets_dir / "churn-metrics.csv"
    sheet_path.write_text("metric,description,reasoning,importance\n")

    drafts_dir = tmp_path / ".dbt-martmaker" / "drafts" / "churn-metrics"
    drafts_dir.mkdir(parents=True)
    (drafts_dir / "meta.json").write_text(
        json.dumps({"sheet_checksum": "stale-checksum-does-not-match", "status": "built"})
    )

    result = list_sheets_report(tmp_path)

    assert result["sheets"][0]["status"] == "stale (sheet changed since last proposal)"


list_sheets_report = list_sheets.build_report
