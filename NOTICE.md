# NOTICE

Third-party runtime dependencies and their licenses, audited 2026-08-03
(pip-licenses against the pinned environment). All permissive; no copyleft,
no attribution-bearing model weights (LLM access is via the Anthropic API,
nothing is bundled).

| Package | License |
|---|---|
| fastapi | MIT |
| uvicorn | BSD-3-Clause |
| python-dotenv | BSD-3-Clause |
| anthropic | MIT |
| twilio | MIT |
| python-docx | MIT |

Transitive dependencies are pulled in by the above and carry MIT/BSD/Apache-
style licenses. Re-audit after any dependency change:

```bash
uvx pip-licenses --python .venv/bin/python
```
