import json

import escalation


def test_first_attempt_never_escalates(tmp_path):
    result = escalation.record_and_check(tmp_path, "churn", "Monthly churned users", "blocked", "csum-1")
    assert result["escalate"] is False
    assert result["total_attempts"] == 1


def test_escalates_after_threshold_consecutive_unresolved_rounds(tmp_path):
    escalation.record_and_check(tmp_path, "churn", "Monthly churned users", "blocked", "csum-1")
    result = escalation.record_and_check(
        tmp_path, "churn", "Monthly churned users", "ambiguous", "csum-2"
    )
    assert result["escalate"] is True
    assert result["total_attempts"] == 2


def test_no_escalation_once_matched(tmp_path):
    escalation.record_and_check(tmp_path, "churn", "Monthly churned users", "blocked", "csum-1")
    result = escalation.record_and_check(tmp_path, "churn", "Monthly churned users", "matched", "csum-2")
    assert result["escalate"] is False


def test_matched_row_breaks_the_unresolved_streak(tmp_path):
    """A metric that resolves at some point, then later regresses, gets a
    fresh first try rather than inheriting an old streak."""
    escalation.record_and_check(tmp_path, "churn", "Monthly churned users", "blocked", "csum-1")
    escalation.record_and_check(tmp_path, "churn", "Monthly churned users", "matched", "csum-2")
    result = escalation.record_and_check(
        tmp_path, "churn", "Monthly churned users", "ambiguous", "csum-3"
    )
    assert result["escalate"] is False


def test_rerun_of_unchanged_sheet_does_not_double_count(tmp_path):
    escalation.record_and_check(tmp_path, "churn", "Monthly churned users", "blocked", "csum-1")
    first = escalation.record_and_check(tmp_path, "churn", "Monthly churned users", "blocked", "csum-1")
    assert first["total_attempts"] == 1
    assert first["escalate"] is False


def test_rerun_of_unchanged_sheet_recomputes_if_status_changed(tmp_path):
    """A correction or glossary edit can change grounding output for the
    same, unchanged sheet checksum -- the recorded status must update
    without counting as a second attempt."""
    escalation.record_and_check(tmp_path, "churn", "Monthly churned users", "blocked", "csum-1")
    result = escalation.record_and_check(
        tmp_path, "churn", "Monthly churned users", "matched", "csum-1"
    )
    assert result["total_attempts"] == 1
    assert result["escalate"] is False

    history = escalation.load_history(tmp_path, "churn")
    assert history["metrics"]["Monthly churned users"][0]["status"] == "matched"


def test_history_persisted_to_disk_and_reloadable(tmp_path):
    escalation.record_and_check(tmp_path, "churn", "Monthly churned users", "blocked", "csum-1")

    history_path = tmp_path / ".dbt-martmaker" / "drafts" / "churn" / "history.json"
    assert history_path.exists()
    on_disk = json.loads(history_path.read_text())
    assert on_disk["metrics"]["Monthly churned users"][0]["status"] == "blocked"

    reloaded = escalation.load_history(tmp_path, "churn")
    assert reloaded == on_disk


def test_load_history_empty_when_absent(tmp_path):
    assert escalation.load_history(tmp_path, "nonexistent") == {"metrics": {}}


def test_different_metrics_tracked_independently(tmp_path):
    escalation.record_and_check(tmp_path, "churn", "Monthly churned users", "blocked", "csum-1")
    escalation.record_and_check(tmp_path, "churn", "Revenue lost to churn", "matched", "csum-1")

    result = escalation.record_and_check(
        tmp_path, "churn", "Monthly churned users", "blocked", "csum-2"
    )
    assert result["escalate"] is True

    result2 = escalation.record_and_check(
        tmp_path, "churn", "Revenue lost to churn", "matched", "csum-2"
    )
    assert result2["escalate"] is False


def test_should_escalate_respects_a_higher_threshold(tmp_path):
    prior = [{"status": "blocked"}, {"status": "ambiguous"}]
    assert escalation.should_escalate(prior, "blocked", threshold=3) is True
    assert escalation.should_escalate(prior[:1], "blocked", threshold=3) is False
