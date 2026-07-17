"""Project store: canonical record, doc checklist, status board, client messages.

kn: in-memory dict + append-only JSONL audit, same rung as my other builds;
sqlite at first multi-consultant pilot. Client messages are TEMPLATED ONLY —
status texts come from the approved strings below, never from an LLM, because
a hallucinated "your permit was approved" is an unrecoverable client-trust
failure.
"""
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "projects.jsonl"
MESSAGES = ROOT / "messages.jsonl"

REQUIRED_DOCS = ["signed survey", "site plan", "photos", "deed or proof of ownership"]

STAGES = ["intake", "assembling", "consultant_review", "submitted", "rai_received", "approved"]

# The ONLY client-facing status texts. Consultant-approved wording, filled by
# str.format with safe fields. No generative path writes to a client.
STATUS_TEMPLATES = {
    "intake": "Hi {name}, we've opened your dock/seawall project file. We'll ask for a few documents next.",
    "assembling": "Hi {name}, we have what we need and are assembling your agency paperwork.",
    "consultant_review": "Hi {name}, your draft permit packet is assembled and under review by {consultant}.",
    "submitted": "Hi {name}, {consultant} has submitted your applications to the agencies. We'll update you as they respond.",
    "rai_received": "Hi {name}, an agency has asked for additional information on your project. {consultant} is on it and will call if anything is needed from you.",
    "approved": "Hi {name}, good news — an approval has come through on your project. {consultant} will walk you through next steps.",
}
REMINDER_TEMPLATE = ("Hi {name}, quick reminder for your permit file — we still need: {missing}. "
                     "Reply here with photos/scans or questions any time.")

_PROJECTS: dict[str, dict] = {}


def _audit(event, **kw):
    with LOG.open("a") as f:
        f.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(), "event": event, **kw}) + "\n")


def safe_name(fields: dict) -> str:
    """The {name} slot in client templates: single line, hard cap, fallback.
    LLM-extracted names must never carry sentences into a client SMS."""
    v = " ".join(str(fields.get("owner_name") or "").split())
    return v[:60] if v else "there"


def _send(project, body):
    """SMS via client-owned Twilio; persisted locally first with an honest
    delivered status — a swallowed failure reported as success is how a client
    silently never hears about their permit."""
    msg = {"ts": datetime.now(timezone.utc).isoformat(), "project": project["id"],
           "to": project.get("owner_phone") or "(no phone on file)", "body": body,
           "delivered": None}  # None = dry run (no creds/phone)
    sid, tok, from_ = (os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"),
                       os.getenv("TWILIO_PHONE_NUMBER"))
    if sid and tok and from_ and project.get("owner_phone"):  # pragma: no cover - network
        try:
            from twilio.rest import Client
            Client(sid, tok).messages.create(to=project["owner_phone"], from_=from_, body=body)
            msg["delivered"] = True
        except Exception:
            msg["delivered"] = False
            _audit("sms_delivery_failed", project=project["id"])
    with MESSAGES.open("a") as f:
        f.write(json.dumps(msg) + "\n")
    return msg


def create_project(consultant_name: str, owner_phone: str = "") -> dict:
    pid = uuid.uuid4().hex[:10]
    _PROJECTS[pid] = {
        "id": pid, "created": datetime.now(timezone.utc).isoformat(),
        "consultant_name": consultant_name, "owner_phone": owner_phone,
        "fields": {}, "needs_review": [], "confidence": {},
        "docs": {d: False for d in REQUIRED_DOCS},
        "stage": "intake", "stage_history": [("intake", datetime.now(timezone.utc).isoformat())],
        "intake_log": [],
    }
    _audit("project_created", project=pid)
    return _PROJECTS[pid]


def get_project(pid: str) -> dict | None:
    return _PROJECTS.get(pid)


def merge_intake(pid: str, extraction: dict, raw_text: str) -> dict:
    """Fold an extraction in. Earlier captured values win (same rule as my SMS build);
    needs_review accumulates; the raw exchange is audit-logged."""
    p = _PROJECTS[pid]
    for k, v in (extraction.get("fields") or {}).items():
        if v in (None, "") or p["fields"].get(k) not in (None, ""):
            continue
        p["fields"][k] = v
    for f in extraction.get("needs_review", []):
        if f not in p["needs_review"]:
            p["needs_review"].append(f)
    p["confidence"].update(extraction.get("confidence") or {})
    p["intake_log"].append({"ts": datetime.now(timezone.utc).isoformat(),
                            "homeowner": raw_text[:20000],
                            "reply": extraction.get("reply_text"),
                            "routed_question": extraction.get("routed_question", False)})
    # Raw text goes to the durable audit line too: "extraction failure never loses
    # a homeowner message" has to survive a process restart, not just this dict.
    _audit("intake_merged", project=pid, needs_review=p["needs_review"],
           homeowner_text=raw_text[:20000])
    return p


def resolve_review(pid: str, field: str, value) -> dict:
    """Consultant fixes a flagged field — the only path that clears a flag."""
    p = _PROJECTS[pid]
    p["fields"][field] = value
    if field in p["needs_review"]:
        p["needs_review"].remove(field)
    _audit("review_resolved", project=pid, field=field)
    return p


def set_doc(pid: str, doc: str, received: bool) -> dict:
    p = _PROJECTS[pid]
    if doc not in p["docs"]:
        raise ValueError(f"unknown doc '{doc}'")
    p["docs"][doc] = received
    _audit("doc_updated", project=pid, doc=doc, received=received)
    return p


def missing_docs(pid: str) -> list[str]:
    return [d for d, got in _PROJECTS[pid]["docs"].items() if not got]


def send_reminder(pid: str) -> dict | None:
    p = _PROJECTS[pid]
    missing = missing_docs(pid)
    if not missing:
        return None
    body = REMINDER_TEMPLATE.format(name=safe_name(p["fields"]), missing=", ".join(missing))
    return _send(p, body)


def set_stage(pid: str, stage: str) -> dict:
    """Stage change fires the templated (never generated) client update."""
    if stage not in STAGES:
        raise ValueError(f"unknown stage '{stage}'")
    p = _PROJECTS[pid]
    p["stage"] = stage
    p["stage_history"].append((stage, datetime.now(timezone.utc).isoformat()))
    _send(p, STATUS_TEMPLATES[stage].format(name=safe_name(p["fields"]),
                                            consultant=p["consultant_name"]))
    _audit("stage_set", project=pid, stage=stage)
    return p


if __name__ == "__main__":
    import tempfile
    LOG = Path(tempfile.mkstemp(suffix=".jsonl")[1])
    MESSAGES = Path(tempfile.mkstemp(suffix=".jsonl")[1])

    p = create_project("Kannishk", "+18315550100")
    merge_intake(p["id"], {"fields": {"owner_name": "Pat", "length_ft": 40.0},
                           "needs_review": ["parcel_apn"], "confidence": {}, "reply_text": "ok"}, "my dock is 40ft")
    merge_intake(p["id"], {"fields": {"owner_name": "OVERWRITE ATTEMPT", "width_ft": 8.0},
                           "needs_review": [], "confidence": {}, "reply_text": "ok"}, "8 ft wide")
    assert p["fields"]["owner_name"] == "Pat" and p["fields"]["width_ft"] == 8.0  # first capture wins
    resolve_review(p["id"], "parcel_apn", "007-123-456")
    assert p["needs_review"] == []
    set_doc(p["id"], "photos", True)
    assert "photos" not in missing_docs(p["id"]) and len(missing_docs(p["id"])) == 3
    assert send_reminder(p["id"]) is not None
    set_stage(p["id"], "assembling")
    msgs = [json.loads(x) for x in MESSAGES.read_text().splitlines()]
    assert len(msgs) == 2 and "assembling your agency paperwork" in msgs[-1]["body"]
    try:
        set_stage(p["id"], "totally_done")
        raise AssertionError("accepted unknown stage")
    except ValueError:
        pass
    print("store OK — first capture wins, flags clear only via consultant, messages templated only")
