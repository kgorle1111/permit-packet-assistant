# Permit Packet Assistant — Demo Script

Opening line for a consultant: **"You re-key the same thirty facts into three
agencies' forms on every project. Stop."**

9 scenes, about three minutes narrated. Everything shown is the real app with a
real project extracted live from homeowner messages, including the guard
routing a fee question away from the AI.

---

## Scene 1 — `01-home` · Projects home
**Say:** "This is the Permit Packet Assistant, built for dock and seawall permit consultants. The header carries the whole idea: one intake, every agency, and you file. This is the project list, with a scoreboard tracking intake turns, re-key minutes saved, and packets delivered."

## Scene 2 — `02-new-project` · New project
**Say:** "A new project is two fields: your firm name and the homeowner's phone. The homeowner never installs anything. They just text or email like they already do."

## Scene 3 — `03-detail` · The project record
**Say:** "Here's a live project. Marcus Alvarez wrote three ordinary messages about replacing his dock in Sarasota, and the record filled itself: address, parcel number, waterbody, dimensions, the boat lift, the seawall that's staying. Thirteen of fourteen fields captured from plain conversation, each one tracked with a confidence level, and anything uncertain gets flagged for your review instead of guessed."

## Scene 4 — `04-conversation` · The guard in action
**Say:** "Watch what happened when he asked how much the county fees would cost. The assistant didn't answer. It said that question belongs to Gulf Coast Marine Permitting, flagged it, and kept collecting facts. That's a hard rule in code, not a polite suggestion to the model. Fee, advice, and legal questions always route to you, even if the AI is down."

## Scene 5 — `05-intake` · Zero-friction intake
**Say:** "Your side of intake is one box. Paste whatever the homeowner sent, email, text, a rambling voicemail transcript, and run it. Every message lands in the same structured record."

## Scene 6 — `06-docs` · Document checklist
**Say:** "The document checklist tracks the survey, site plan, photos, and proof of ownership, and one button sends the homeowner a reminder for whatever's still missing. No more chasing attachments across three email threads."

## Scene 7 — `07-status` · The stage pipeline
**Say:** "Every project moves through the same stages, intake to assembling to review, submitted, and approved. Stage changes can text the homeowner a status update automatically, and those messages are your approved templates verbatim. The software never improvises a message to a client."

## Scene 8 — `08-packet` · The draft packet
**Say:** "When the record's ready, one click exports the multi-agency draft packet, county, state, and Army Corps forms filled from that single record. Every uncertain field prints an inline consultant-review flag, and the whole packet is watermarked draft. You review, you sign, you file. The software never touches an agency system."

## Scene 9 — `09-dark` · Close
**Say:** "That's the whole product. The homeowner talks like a homeowner, the record builds itself, and the thirty facts get keyed exactly once. You stay the expert, and the re-keying is gone."

---

## Q&A ammunition

- **"Every county's forms are different."** Correct, and that's the moat. The
  per-county mapping is an hour of setup with your last packet, and it's the
  only per-jurisdiction artifact. Platforms can't afford that per tiny county.
  You can.
- **"What if it gives permitting advice?"** It can't. Advice, fee, and
  eligibility questions route to you deterministically, in code, regardless of
  what the model says. Scene 4 is the live proof.
- **"Will agencies accept auto-filled forms?"** You file, not the software.
  Nothing fills silently: uncertain fields render an inline review flag and
  the packet is watermarked draft until you clear them.
