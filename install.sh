#!/usr/bin/env bash
# One-command install: clone, ./install.sh, done.
set -euo pipefail
cd "$(dirname "$0")"
command -v uv >/dev/null 2>&1 || { echo "uv not found. Install it first:  curl -LsSf https://astral.sh/uv/install.sh | sh"; exit 1; }
[ -d .venv ] || uv venv
uv pip install -r requirements-dev.txt
[ -f .env ] || cp .env.example .env
.venv/bin/python verify_setup.py
echo
echo "Install complete. Run the app:"
echo "  .venv/bin/uvicorn app.main:app --port 5080"
