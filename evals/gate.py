"""Eval regression gate — run locally after any prompt/model change.

Deliberately not in CI: costs money (~$0.10/run) and needs ANTHROPIC_API_KEY.

Runs the live suite via run_evals.run(), reads the results file it just wrote,
and exits nonzero if passed < BASELINE.json min_passed.

    python evals/gate.py                    # gate against the baseline
    python evals/gate.py --update-baseline  # accept current results as the new floor
                                            # (do this after adding photo cases)
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_evals  # noqa: E402

BASELINE = Path(__file__).parent / "BASELINE.json"


def latest_results() -> dict:
    # kn: run() writes a timestamped file and returns only a bool; the newest
    # file is the run we just did. Refactor run() to return counts if this
    # ever races (it can't today — gate is single-process).
    files = sorted(run_evals.RESULTS.glob("*.json"))
    if not files:
        sys.exit("no results file found — run_evals.run() should have written one")
    return json.loads(files[-1].read_text())


def main() -> int:
    run_evals.run()
    res = latest_results()
    passed, total = res["passed"], res["total"]

    if "--update-baseline" in sys.argv:
        BASELINE.write_text(json.dumps({"min_passed": passed, "total": total}, indent=2) + "\n")
        print(f"baseline updated: min_passed={passed}, total={total}")
        return 0

    base = json.loads(BASELINE.read_text())
    if passed < base["min_passed"]:
        print(f"GATE FAIL: {passed}/{total} passed; baseline requires >= {base['min_passed']}")
        return 1
    print(f"GATE PASS: {passed}/{total} passed (baseline {base['min_passed']}/{base['total']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
