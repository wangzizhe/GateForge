#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_medium_candidate_mining_v0_54_0 import run_medium_candidate_mining  # noqa: E402


def main() -> int:
    summary = run_medium_candidate_mining()
    print(
        json.dumps(
            {
                "status": summary["status"],
                "readiness_status": summary["readiness_status"],
                "medium_candidate_count": summary["medium_candidate_count"],
                "observed_case_count": summary["observed_case_count"],
            },
            sort_keys=True,
        )
    )
    return 0 if summary["artifact_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
