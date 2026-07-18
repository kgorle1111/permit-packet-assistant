"""Hermetic test setup — no keys, no network, no repo writes."""
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import dotenv  # noqa: E402

dotenv.load_dotenv = lambda *a, **k: None
for _k in ("ANTHROPIC_API_KEY", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER"):
    os.environ.pop(_k, None)
os.environ["MIN_PER_FIELD"] = "1.5"

import pytest  # noqa: E402

from app import packet, receipt, store  # noqa: E402


@pytest.fixture(autouse=True)
def isolate_files(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "LOG", tmp_path / "projects.jsonl")
    monkeypatch.setattr(store, "MESSAGES", tmp_path / "messages.jsonl")
    monkeypatch.setattr(store, "DATA", tmp_path / "data")
    monkeypatch.setattr(store, "_PROJECTS", {})
    monkeypatch.setattr(receipt, "LOG", tmp_path / "receipts.jsonl")
    monkeypatch.setattr(packet, "PACKETS", tmp_path / "packets")
    return tmp_path


@pytest.fixture
def extraction():
    """Factory for a clean intake extraction dict."""
    def _make(**over):
        fields = {f: None for f in
                  __import__("app.intake", fromlist=["CANONICAL_FIELDS"]).CANONICAL_FIELDS}
        fields.update(over.pop("fields", {}))
        d = {"fields": fields, "confidence": {}, "reply_text": "What waterbody is the property on?",
             "needs_review": [], "routed_question": False, "parse_note": None}
        d.update(over)
        return d
    return _make
