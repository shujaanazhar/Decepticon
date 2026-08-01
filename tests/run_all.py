#!/usr/bin/env python3
"""
Run every test. Plain scripts, no pytest — each file is also runnable on its own.

    .venv/bin/python tests/run_all.py

test_mic.py needs Playwright installed, because meet_driver imports it at
module scope. It does not launch a browser: MeetDriver is instantiated without
__init__ and handed a fake page object. test_orchestrator.py needs nothing
beyond the core dependencies.
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUITES = ["test_mic.py", "test_orchestrator.py"]


def main() -> int:
    failures = []

    for suite in SUITES:
        print(f"\n{'=' * 60}\n{suite}\n{'=' * 60}")
        result = subprocess.run([sys.executable, str(HERE / suite)])
        if result.returncode != 0:
            failures.append(suite)

    print(f"\n{'=' * 60}")
    if failures:
        print(f"FAILED: {', '.join(failures)}")
        return 1
    print(f"All suites passed ({len(SUITES)} files).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
