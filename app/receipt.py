"""Value receipt: the re-keying math. Every packet export logs fields auto-filled
vs flagged; the rollup speaks in the consultant's own unit — hours not re-typed.

kn: 1.5 min per re-keyed field is my placeholder; week one of a pilot replaces
it with the consultant's own timing. The rollup math doesn't change.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

LOG = Path(__file__).resolve().parent.parent / "receipts.jsonl"

MIN_PER_FIELD = float(os.getenv("MIN_PER_FIELD", "1.5"))


def log_event(project, outcome, fields_autofilled=0, fields_flagged=0, routed_questions=0):
    """outcome: intake_turn | packet_exported | reminder_sent | stage_update_sent"""
    row = {"ts": datetime.now(timezone.utc).isoformat(), "project": project, "outcome": outcome,
           "fields_autofilled": fields_autofilled, "fields_flagged": fields_flagged,
           "routed_questions": routed_questions}
    if outcome == "packet_exported":
        row["rekey_minutes_avoided"] = round(fields_autofilled * MIN_PER_FIELD, 1)
    with LOG.open("a") as f:
        f.write(json.dumps(row) + "\n")
    return row


def rollup(path=None):
    """LOG resolved at call time so tests that repoint receipt.LOG see the right file."""
    path = Path(path or LOG)
    if not path.exists():
        return {}
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    # Re-downloading the same packet must not inflate the scoreboard: latest
    # export per project wins, one packet counts once.
    latest = {}
    for r in rows:
        if r["outcome"] == "packet_exported":
            latest[r["project"]] = r
    packets = list(latest.values())
    return {
        "projects_touched": len({r["project"] for r in rows}),
        "intake_turns": sum(1 for r in rows if r["outcome"] == "intake_turn"),
        "advice_questions_routed_to_consultant": sum(r.get("routed_questions", 0) for r in rows),
        "packets_exported": len(packets),
        "fields_autofilled": sum(r.get("fields_autofilled", 0) for r in packets),
        "fields_flagged_for_review": sum(r.get("fields_flagged", 0) for r in packets),
        "rekey_minutes_avoided": round(sum(r.get("rekey_minutes_avoided", 0) for r in packets), 1),
        "reminders_sent": sum(1 for r in rows if r["outcome"] == "reminder_sent"),
        "status_updates_sent": sum(1 for r in rows if r["outcome"] == "stage_update_sent"),
    }


if __name__ == "__main__":
    import tempfile
    LOG = Path(tempfile.mkstemp(suffix=".jsonl")[1])
    log_event("P1", "intake_turn", routed_questions=1)
    log_event("P1", "packet_exported", fields_autofilled=24, fields_flagged=4)
    log_event("P1", "reminder_sent")
    log_event("P1", "stage_update_sent")
    r = rollup(LOG)
    assert r["packets_exported"] == 1
    assert r["rekey_minutes_avoided"] == 36.0
    assert r["advice_questions_routed_to_consultant"] == 1
    print("receipt OK", r["rekey_minutes_avoided"], "min avoided")
