#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_hard_positive_candidate_attempts_v0_60_1 import run_hard_positive_candidate_attempts  # noqa: E402


def main() -> int:
    summary = run_hard_positive_candidate_attempts()
    print(
        json.dumps(
            {
                "status": summary["status"],
                "attempt_count": summary["attempt_count"],
                "verified_pass_count": summary["verified_pass_count"],
                "failed_attempt_count": summary["failed_attempt_count"],
            },
            sort_keys=True,
        )
    )
    return 0 if summary["artifact_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
