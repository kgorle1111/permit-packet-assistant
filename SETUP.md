# SETUP — zero to a live demo

## 1. Local

One command:

```bash
./install.sh   # venv + deps + .env scaffold + environment verification
```

Or manually:

```bash
uv venv && source .venv/bin/activate
uv pip install -r requirements-dev.txt
python -m app.intake && python -m app.packet && python -m app.store && python -m app.receipt
pytest        # all green, no keys needed
```

## 2. Keys

`cp .env.example .env`:
- `ANTHROPIC_API_KEY` — intake extraction (~$0.01–0.02/turn). Client's key for a pilot.
- Twilio trio (optional) — real SMS reminders/status updates; without it every
  message is still persisted to `messages.jsonl`, so the demo works dry.

## 3. Run

```bash
uvicorn app.main:app --port 5080
```

Open http://localhost:5080 — create a project, paste a homeowner message, watch
the record fill and flags land, mark docs, change stages, export the packet.

## 4. Wire a real jurisdiction (pilot week one)

Everything per-county lives in `templates/agency_forms.json`: replace the
generic field labels with the pilot consultant's actual county/state/USACE
form fields, mapping each to a canonical field. One sitting with the
consultant and their last submitted packet is enough.

## 5. Pilot hand-off checklist

- [ ] Client's Anthropic key (their console, their card); Twilio theirs if SMS is on
- [ ] Real agency form mappings wired and reviewed by the consultant
- [ ] `MIN_PER_FIELD` set from timing their actual re-keying on one packet
- [ ] Baseline measured: consultant hours on their last 5 projects (the pilot
      success metric compares against this)
- [ ] One-page runbook: what it does, where data lives, who to call when
- [ ] Walk them through one routed advice question live — seeing "how much
      will this cost?" get deflected to them is what buys the trust
