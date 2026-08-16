#!/usr/bin/env python3
"""
Tracks, per metric, whether a sheet row has stayed ambiguous or blocked
across successive revisions -- the signal for the one thing this skill
deliberately never automates: escalating to a real conversation instead
of another async round.

Philosophy: default to the cheap channel (the sheet) every time. Escalate
to the expensive one (an actual conversation) only when the cheap channel
has already been given a real chance and demonstrably failed -- never on
a first pass, and never for a row that's already matched.

Usage:
    escalation.py <project_root> <slug> "<metric name>" <status> <sheet_checksum>

status must be one of: matched, ambiguous, blocked.

Output: a single JSON object on stdout, and (side effect) appends this
attempt to .dbt-martmaker/drafts/<slug>/history.json. One call both
records the current round and reports whether to escalate -- they are
never needed separately, since a row can only be flagged by looking at
its own history.
"""
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

# Give the cheap channel exactly one real chance to self-correct: stuck on
# attempt 1, the stakeholder revises, still stuck on attempt 2 -> escalate.
# Higher would tolerate too many repeated failures before ever suggesting
# a conversation; 1 would escalate on the very first pass, which defeats
# the point of trying the sheet at all.
ESCALATION_ROUND_THRESHOLD = 2

UNRESOLVED_STATUSES = {"ambiguous", "blocked"}
VALID_STATUSES = {"matched", "ambiguous", "blocked"}


def _history_path(project_root: Path, slug: str) -> Path:
    return project_root / ".dbt-martmaker" / "drafts" / slug / "history.json"


def load_history(project_root: Path, slug: str) -> dict:
    path = _history_path(project_root, slug)
    if not path.exists():
        return {"metrics": {}}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {"metrics": {}}


def save_history(project_root: Path, slug: str, history: dict) -> None:
    path = _history_path(project_root, slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, indent=2))


def should_escalate(
    prior_attempts: list[dict], current_status: str, threshold: int = ESCALATION_ROUND_THRESHOLD
) -> bool:
    """True when the current attempt is still unresolved, and the
    threshold - 1 attempts immediately before it were unresolved too. A
    metric's very first attempt never escalates -- the cheap channel
    always gets a real first try. A row that resolved at any point and
    later comes back unresolved gets a fresh first try too, since the
    "recent" window only looks at what's immediately preceding."""
    if current_status not in UNRESOLVED_STATUSES:
        return False
    if len(prior_attempts) < threshold - 1:
        return False
    recent = prior_attempts[-(threshold - 1):]
    return all(a["status"] in UNRESOLVED_STATUSES for a in recent)


def record_and_check(
    project_root: Path, slug: str, metric: str, status: str, sheet_checksum: str
) -> dict:
    history = load_history(project_root, slug)
    metrics = history.setdefault("metrics", {})
    attempts = metrics.setdefault(metric, [])

    # Idempotent: re-processing a sheet that hasn't actually changed must
    # never count as a second real attempt -- only keep its status current,
    # in case a correction or glossary change altered the outcome without
    # the sheet itself changing.
    if attempts and attempts[-1]["sheet_checksum"] == sheet_checksum:
        prior_attempts = attempts[:-1]
        escalate = should_escalate(prior_attempts, status)
        attempts[-1]["status"] = status
        save_history(project_root, slug, history)
        return {"metric": metric, "escalate": escalate, "total_attempts": len(attempts)}

    escalate = should_escalate(attempts, status)
    attempts.append(
        {
            "sheet_checksum": sheet_checksum,
            "status": status,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
    )
    save_history(project_root, slug, history)
    return {"metric": metric, "escalate": escalate, "total_attempts": len(attempts)}


def main() -> None:
    if len(sys.argv) != 6:
        print(
            json.dumps(
                {
                    "error": "bad_args",
                    "message": (
                        "Usage: escalation.py <project_root> <slug> "
                        '"<metric name>" <status> <sheet_checksum>'
                    ),
                }
            )
        )
        sys.exit(1)

    project_root = Path(sys.argv[1]).resolve()
    slug = sys.argv[2]
    metric = sys.argv[3]
    status = sys.argv[4]
    sheet_checksum = sys.argv[5]

    if status not in VALID_STATUSES:
        print(
            json.dumps(
                {
                    "error": "bad_status",
                    "message": f"status must be one of {sorted(VALID_STATUSES)} -- got {status!r}",
                }
            )
        )
        sys.exit(1)

    result = record_and_check(project_root, slug, metric, status, sheet_checksum)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
