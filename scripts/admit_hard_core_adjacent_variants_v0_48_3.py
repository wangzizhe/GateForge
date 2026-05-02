#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_hard_core_adjacent_admission_v0_48_3 import run_hard_core_adjacent_admission  # noqa: E402


def main() -> int:
    summary = run_hard_core_adjacent_admission()
    print(
        json.dumps(
            {
                "status": summary["status"],
                "case_count": summary["case_count"],
                "admitted_case_count": summary["admitted_case_count"],
                "review_case_count": summary["review_case_count"],
                "admission_status_counts": summary["admission_status_counts"],
            },
            sort_keys=True,
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
