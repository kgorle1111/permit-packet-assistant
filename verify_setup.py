"""Proves the environment works before you touch real data. Run: .venv/bin/python verify_setup.py"""
import importlib
import os
import subprocess
import sys

MODULES = ["app.intake", "app.packet", "app.store", "app.receipt"]  # each has an assert-based __main__ self-check

failures = []

if sys.version_info < (3, 12):
    failures.append(f"Python 3.12+ required, found {sys.version.split()[0]}")

try:
    importlib.import_module("app.main")
    print("ok  app imports")
except Exception as e:
    failures.append(f"app.main failed to import: {e}")

for m in MODULES:
    r = subprocess.run([sys.executable, "-m", m], capture_output=True, text=True)
    if r.returncode == 0:
        print(f"ok  {m} self-check")
    else:
        failures.append(f"{m} self-check failed:\n{r.stdout}{r.stderr}")

if not os.path.exists(".env"):
    print("warn  no .env — cp .env.example .env and add your keys (tests run without them)")
else:
    from pathlib import Path
    env = Path(".env").read_text()
    if "ANTHROPIC_API_KEY=" not in env or "ANTHROPIC_API_KEY=\n" in env:
        print("warn  ANTHROPIC_API_KEY looks unset in .env — live calls will fail; tests still pass")

if failures:
    print("\nFAILED:")
    for f in failures:
        print(" -", f)
    sys.exit(1)
print("\nEnvironment verified. Run pytest for the full suite.")
