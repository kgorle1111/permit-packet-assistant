# 🌊 Permit Packet Assistant

One intake, every agency: a waterfront homeowner describes their dock/seawall
project once, and the consultant gets review-ready draft packets for the
county building department, the state environmental agency, and the USACE
worksheet — plus automatic doc-chasing and templated client status updates.
**The software assembles; the consultant reviews and files.**

> The value is the re-keying: the same ~30 project facts typed into three or
> more disconnected agency forms, per project, at consultant billing rates.

Vertical selected by a 561→100→9→3 research funnel with dated competitor scans
and an adversarial kill panel: PermitFlow/Pulley chase general contractors,
Ecobot covers the wetland-delineation side, service bureaus are quote-only —
nobody combines homeowner intake + multi-agency assembly + client comms for
marine permitting consultants.

## What it does

- 💬 **Guided intake** — homeowner's freeform message → one structured LLM
  call extracts the canonical project record (14 fields, per-field confidence);
  deterministic validators (numeric dimensions, known structure types) flag
  anything questionable as NEEDS REVIEW instead of guessing.
- 📋 **Multi-agency draft packets** — deterministic code (NO LLM in the fill
  path) maps the validated record onto three agency templates; every missing
  or flagged field renders as `[CONSULTANT REVIEW: …]` inline; DOCX export is
  loudly watermarked DRAFT.
- 📄 **Doc checklist + chaser** — survey, site plan, photos, deed; templated
  SMS/email reminders until complete.
- 📈 **Status board** — consultant sets the stage; each change fires a
  pre-written, consultant-approved client update. The LLM never writes to a
  client.
- 🧾 **Value receipt** — fields auto-filled vs flagged, re-keying minutes
  avoided, advice questions routed, updates sent.

### Hard boundaries (enforced in code, not just prompt)

- **No advice, ever**: "do I need a permit / what's exempt / what does it
  cost / is this legal" is caught by a deterministic guard on the homeowner's
  text and routed to the consultant — regardless of what the model generates.
- **No LLM in the form-fill path**: a hallucinated parcel number on a federal
  form is the one unrecoverable failure, so agency fields are filled only from
  the validated record by plain code.
- **No submissions**: output is a draft packet; the consultant files.
- **No generated client messages**: status texts are byte-identical to
  approved templates (pinned by test).

## Architecture

```
homeowner text ──► POST /intake ──► advice/injection guard (deterministic)
                                        │ routed? -> consultant answers, not the agent
                              ONE structured LLM call ──► fields + confidence
                                        │ validators: numeric, enums, ranges
                              canonical record (first capture wins; flags accumulate)
                                        │
        consultant resolves flags ──► packet.py (NO LLM) ──► 3 agency DOCX drafts
                                        │                        │ [CONSULTANT REVIEW] inline
              doc checklist + templated reminders          value receipt ◄─┘
              stage changes -> templated client updates
```

Extraction failure ≠ lost message: intake lands fully-flagged with the raw
text preserved in the project log.

## Quickstart

```bash
uv venv && source .venv/bin/activate
uv pip install -r requirements-dev.txt
python -m app.intake && python -m app.packet && python -m app.store && python -m app.receipt
pytest                          # hermetic — no keys, no network
cp .env.example .env            # ANTHROPIC_API_KEY; Twilio optional for real SMS
uvicorn app.main:app --port 5080   # open http://localhost:5080
python evals/run_evals.py       # live behavioral evals (~$0.05)
```

## The pitch script

1. Ask the consultant to read you their last homeowner intake email, verbatim.
2. Paste it live; watch the record fill and the flags land.
3. Export the packet: "here's your county, DEP, and USACE drafts — which of
   these fields would you normally have typed three times?"
4. Show `/rollup`: re-keying minutes at their billing rate.
5. Close: measure their last 5 projects' hours in discovery; 4-week pilot on
   their accounts; $500/mo, county pack included.

## Running costs (client's own accounts)

| Item | Cost |
|---|---|
| Intake extraction (claude-sonnet-5) | ~$0.01–0.02 per turn |
| Twilio SMS updates | ~$0.008/message |
| A busy month (10 projects) | **under $5** |

## Repo layout

```
app/
  main.py     FastAPI · intake / review / docs / stage / packet endpoints · demo UI
  intake.py   advice+injection guards (deterministic) + single extraction call + validators
  packet.py   NO-LLM multi-agency assembler · inline review flags · DRAFT watermarks
  store.py    project record · first-capture-wins · doc checklist · templated messages ONLY
  receipt.py  re-keying receipts + pilot rollup
templates/    agency form mappings (the ONLY per-jurisdiction artifact)
tests/        hermetic pytest — guards, validators, fill flags, templated-message pinning
evals/        live probes: extraction accuracy, advice routing, injection, one-question discipline
```

## Tests & evals

```bash
pytest                     # offline: the judgment guard, validators, fill path, message pinning
python evals/run_evals.py  # live: advice questions must route, injection must not leak
```
