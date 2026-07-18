"""Permit Packet Assistant — FastAPI surface.

Flow
    POST /projects                          create (consultant name + homeowner phone)
    POST /projects/{pid}/intake             homeowner freeform text -> extraction -> merged record
    POST /projects/{pid}/review/{field}     consultant resolves a flagged field (the only flag-clearing path)
    POST /projects/{pid}/docs               mark checklist doc received / send reminder
    POST /projects/{pid}/stage              stage change -> templated client update (never LLM text)
    GET  /projects/{pid}/packet.docx        multi-agency DRAFT packet, flags rendered inline
    GET  /rollup                            the pilot scoreboard

Trust boundaries
    - Homeowner text is untrusted: advice/fee/legal questions are deterministically
      routed to the consultant; injection guarded; extraction validated before merge.
    - The packet fill path contains NO LLM (packet.py) — a hallucinated parcel
      number on a federal form is the unrecoverable failure.
    - Client-facing texts are templated only; the LLM never writes to a client.
    - Nothing is ever submitted to an agency: exports are watermarked drafts.
    - If extraction fails, intake still succeeds fully-flagged — a homeowner
      message is never dropped.
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import intake, packet, receipt, store

load_dotenv()

STATIC = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_app):
    store.load_all()  # rehydrate persisted projects so the list survives a restart
    yield


app = FastAPI(title="permit-packet-assistant", lifespan=lifespan)


def _consultant_only(token: str | None):
    """Consultant-only endpoints (flag clearing, stage changes that text clients).
    CONSULTANT_TOKEN unset = local dev only — set it before any homeowner ever
    sees a URL, or anyone with the link can fire an 'approved' SMS."""
    expected = os.getenv("CONSULTANT_TOKEN")
    if expected and token != expected:
        raise HTTPException(403, "consultant token required")


class ProjectIn(BaseModel):
    consultant_name: str
    owner_phone: str = ""


class IntakeIn(BaseModel):
    text: str


class ReviewIn(BaseModel):
    value: str | float | bool | None


class DocIn(BaseModel):
    doc: str
    received: bool = True


class StageIn(BaseModel):
    stage: str


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/rollup")
def rollup():
    return receipt.rollup()


@app.get("/projects")
def list_projects():
    """Project list for the home view — summaries, newest activity first."""
    return store.list_projects()


@app.post("/projects")
def create_project(body: ProjectIn):
    if not body.consultant_name.strip():
        raise HTTPException(422, "consultant_name required")
    return store.create_project(body.consultant_name.strip()[:80], body.owner_phone.strip()[:20])


@app.get("/projects/{pid}")
def get_project(pid: str):
    p = store.get_project(pid)
    if not p:
        raise HTTPException(404, "project not found")
    return p


@app.post("/projects/{pid}/intake")
def intake_turn(pid: str, body: IntakeIn):
    p = store.get_project(pid)
    if not p:
        raise HTTPException(404, "project not found")
    if not body.text.strip():
        raise HTTPException(422, "text required")

    # The guards are deterministic and MUST NOT depend on the LLM call succeeding:
    # a fee question during an API outage still routes to the consultant.
    routed = intake.advice_guard(body.text)
    injected = intake.injection_guard(body.text)

    try:
        extraction = intake.extract(body.text[:4000], p["consultant_name"], p["fields"])
    except Exception:
        # Extraction down != lost message: log it fully-flagged, consultant reads the raw text.
        extraction = intake._empty("extraction failed — raw text preserved in intake_log")

    if injected:
        # A detected-injection turn's field payload is untrusted wholesale —
        # quarantine it rather than merging model output the attacker steered.
        extraction["fields"] = {f: None for f in intake.CANONICAL_FIELDS}
        extraction["needs_review"] = ["injection_detected — turn quarantined"]
    if routed or injected:
        extraction["reply_text"] = intake.ROUTED_LINE.format(consultant=p["consultant_name"])
        extraction["routed_question"] = True

    p = store.merge_intake(pid, extraction, body.text)
    receipt.log_event(pid, "intake_turn",
                      routed_questions=1 if extraction.get("routed_question") else 0)
    return {"reply_text": extraction["reply_text"], "fields": p["fields"],
            "needs_review": p["needs_review"]}


@app.post("/projects/{pid}/review/{field}")
def resolve_review(pid: str, field: str, body: ReviewIn,
                   x_consultant_token: str | None = Header(default=None)):
    _consultant_only(x_consultant_token)
    p = store.get_project(pid)
    if not p:
        raise HTTPException(404, "project not found")
    if field not in intake.CANONICAL_FIELDS:
        raise HTTPException(422, f"unknown field '{field}'")
    # The consultant path gets the SAME validation as the LLM path — a typo'd
    # "400O" ft on a federal form is the same failure regardless of author.
    v = body.value
    if v is None or (isinstance(v, str) and not v.strip()):
        raise HTTPException(422, "resolving a flag requires an actual value")
    if field in ("length_ft", "width_ft"):
        try:
            v = float(str(v).replace("ft", "").replace("'", "").strip())
            if not 0 < v < 2000:
                raise ValueError
        except (ValueError, TypeError):
            raise HTTPException(422, f"'{field}' must be a number between 0 and 2000")
    elif field == "structure_type" and str(v).lower() not in intake.STRUCTURE_TYPES:
        raise HTTPException(422, f"'{field}' must be one of {sorted(intake.STRUCTURE_TYPES)}")
    elif field == "work_type" and str(v).lower() not in intake.WORK_TYPES:
        raise HTTPException(422, f"'{field}' must be one of {sorted(intake.WORK_TYPES)}")
    elif field in ("survey_available", "photos_available") and not isinstance(v, bool):
        raise HTTPException(422, f"'{field}' must be true or false")
    return store.resolve_review(pid, field, v)


@app.post("/projects/{pid}/docs")
def update_doc(pid: str, body: DocIn, x_consultant_token: str | None = Header(default=None)):
    _consultant_only(x_consultant_token)
    if not store.get_project(pid):
        raise HTTPException(404, "project not found")
    try:
        return store.set_doc(pid, body.doc, body.received)
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.post("/projects/{pid}/remind")
def remind(pid: str, x_consultant_token: str | None = Header(default=None)):
    _consultant_only(x_consultant_token)
    if not store.get_project(pid):
        raise HTTPException(404, "project not found")
    msg = store.send_reminder(pid)
    if not msg:
        return {"sent": False, "reason": "no missing documents"}
    receipt.log_event(pid, "reminder_sent")
    # delivered: True (sent), False (Twilio failed — audit-logged), None (dry run)
    return {"sent": True, "delivered": msg["delivered"], "body": msg["body"]}


@app.post("/projects/{pid}/stage")
def set_stage(pid: str, body: StageIn, x_consultant_token: str | None = Header(default=None)):
    _consultant_only(x_consultant_token)
    if not store.get_project(pid):
        raise HTTPException(404, "project not found")
    try:
        p = store.set_stage(pid, body.stage)
    except ValueError as e:
        raise HTTPException(422, str(e))
    receipt.log_event(pid, "stage_update_sent")
    return p


@app.get("/projects/{pid}/packet.docx")
def export_packet(pid: str):
    p = store.get_project(pid)
    if not p:
        raise HTTPException(404, "project not found")
    if not any(v not in (None, "") for v in p["fields"].values()):
        raise HTTPException(409, "no intake captured yet — nothing to assemble")
    path = packet.build_packet(p)
    stats = packet.packet_stats(p)
    receipt.log_event(pid, "packet_exported", **stats)
    store.record_packet_export(pid)
    return FileResponse(path, filename=path.name,
                        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})
