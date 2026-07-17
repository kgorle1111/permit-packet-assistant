# TRADEOFFS — what I cut and what it costs

The bar I set: a permitting consultant's business is their reputation with
agencies and homeowners. One wrong parcel number on a federal form, or one
"your permit's approved" text that wasn't true, ends the relationship. Every
cut below protects those two failure modes; nothing touches them.

## No LLM in the form-fill path — the load-bearing decision

The intake LLM extracts into a validated canonical record; plain code maps
that record onto agency templates. I could have had the model fill forms
directly from conversation — it would demo flashier and handle odd forms
better. I didn't, because extraction errors get caught by validators and
review flags at ONE choke point, while direct-fill errors scatter across
every form. The cost: new agency forms need a hand-written mapping (an hour
each). That hour is the moat, not the bug — the mapping file is the only
per-jurisdiction artifact.

## Templated client messages only — no generation

Status updates are byte-identical to consultant-approved strings (a test pins
this). A generative "friendlier" update path would read better and
occasionally say something untrue about a government process to a stressed
homeowner. Not worth it at any fluency gain. The LLM talks to the homeowner
only during intake, where the guard routes anything consequential.

## Advice guard is regex-first, prompt-second

"Do I need a permit / is this exempt / what does it cost / is it legal" gets
routed to the consultant by pattern match on the HOMEOWNER'S text, so a
jailbroken or confused model can't answer it — the routed reply overwrites
whatever the model wrote. False positive cost: one over-routed question the
consultant answers anyway (they want those calls). False negative cost:
unlicensed advice on a regulated process.
`kn: regex on inbound; add reply-side screening if pilot logs show leaks.`

## One Florida-style agency trio, generic templates, in v1

The product spec scopes v1 to one county + state env + USACE district. My
demo templates are GENERIC (county building / state env / USACE worksheet)
because I don't have the real forms yet — the pilot consultant's actual
county forms get wired in during week one by editing `templates/
agency_forms.json`, nothing else. Shipping generic-but-honest beats shipping
fake-specific.

## First capture wins on intake merges

Same rule as my SMS build: a field captured earlier survives a later
contradicting extraction; contradictions surface to the consultant rather
than silently flipping. Homeowners correct themselves constantly ("actually
it's 45 feet") — the consultant resolves those via the review endpoint, which
is the only path that clears a flag. The cost: one extra click per genuine
correction. Cheaper than a silent overwrite on a legal document.

## In-memory store + JSONL audit

Same rung as my other builds. A restart drops working state; the audit log
and message log survive. SQLite at the first multi-consultant pilot; the
store interface doesn't change.
`kn: in-memory + jsonl; sqlite when a pilot shows real concurrent use.`

## Skipped entirely, and the trigger to add each

- **County portal automation / e-filing** — never in scope for me; submission
  stays human. This is a one-way-door action on a government system.
- **RAG over the regulatory corpus** — rule Q&A is judgment-adjacent; v1 maps
  forms instead. Revisit only with the consultant reviewing every answer.
- **Real fillable-PDF (AcroForm) output** — v1 exports DOCX drafts. Add
  per-agency when the pilot supplies the actual PDF forms (pypdf, an
  afternoon per form).
- **Voice intake** — the product spec defers Twilio voice; SMS/web covers the
  demo. Add if discovery says homeowners won't type.
- **Multi-user, billing, e-signatures** — firm-scale features; this sells to
  1-5 person consultancies first.
