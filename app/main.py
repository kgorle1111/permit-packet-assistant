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

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from app import intake, packet, receipt, store

load_dotenv()
app = FastAPI(title="permit-packet-assistant")


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
    return FileResponse(path, filename=path.name,
                        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


# kn: minimal demo page — intake box, flags, checklist, stage buttons, export.
@app.get("/", response_class=HTMLResponse)
def index():
    return """<!doctype html><html><head><meta charset="utf-8"><title>Permit Packet Assistant</title>
<style>body{font-family:system-ui;max-width:760px;margin:2rem auto;padding:0 1rem;color:#1a202c}
input,textarea,button,select{font:inherit;margin:.2rem 0}.flag{color:#b45309;font-weight:600}
.box{border:1px solid #ddd;border-radius:8px;padding:1rem;margin:.6rem 0}</style></head><body>
<h1>Permit Packet Assistant</h1>
<p>One intake, every agency. The software assembles drafts; the consultant reviews and files.</p>
<div class="box"><input id="cn" placeholder="Consultant name" value="Kannishk">
<input id="ph" placeholder="Homeowner phone (optional)"><button onclick="mk()">Create project</button></div>
<div id="proj"></div>
<script>
let PID=null;
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function mk(){const r=await fetch('/projects',{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify({consultant_name:document.getElementById('cn').value,owner_phone:document.getElementById('ph').value})});
 const j=await r.json();PID=j.id;render(j,'');}
async function refresh(reply){render(await (await fetch('/projects/'+PID)).json(),reply||'');}
async function talk(){const t=document.getElementById('t').value;
 const r=await fetch(`/projects/${PID}/intake`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:t})});
 const j=await r.json();refresh(j.reply_text);}
async function stage(s){await fetch(`/projects/${PID}/stage`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({stage:s})});refresh('');}
function render(p,reply){
 let h=`<div class="box"><h2>Project ${p.id} — stage: ${esc(p.stage)}</h2>
 <textarea id="t" rows="3" cols="70" placeholder="Paste the homeowner's message…"></textarea><br>
 <button onclick="talk()">Run intake</button> ${reply?`<p><i>Reply to homeowner:</i> ${esc(reply)}</p>`:''}
 <h3>Record</h3><ul>`;
 for(const[k,v]of Object.entries(p.fields)){h+=`<li>${esc(k)}: <b>${esc(v)}</b>${p.needs_review.includes(k)?' <span class="flag">REVIEW</span>':''}</li>`}
 h+=`</ul><h3>Docs</h3><ul>`;
 for(const[d,got]of Object.entries(p.docs)){h+=`<li>${got?'✅':'⬜'} ${esc(d)}</li>`}
 h+=`</ul><button onclick="fetch('/projects/'+PID+'/remind',{method:'POST'}).then(()=>refresh(''))">Send doc reminder</button>
 <h3>Stage</h3>`+['intake','assembling','consultant_review','submitted','rai_received','approved']
 .map(s=>`<button onclick="stage('${s}')">${s}</button>`).join(' ')+
 `<p><a href="/projects/${p.id}/packet.docx">Export draft packet (DOCX)</a> · <a href="/rollup">rollup</a></p></div>`;
 document.getElementById('proj').innerHTML=h;}
</script></body></html>"""
