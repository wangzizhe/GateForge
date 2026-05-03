#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_hard_positive_workbench_v0_60_0 import run_hard_positive_workbench  # noqa: E402


def main() -> int:
    summary = run_hard_positive_workbench()
    print(
        json.dumps(
            {
                "status": summary["status"],
                "case_count": summary["case_count"],
                "complete_task_record_count": summary["complete_task_record_count"],
                "readiness_status": summary["readiness_status"],
            },
            sort_keys=True,
        )
    )
    return 0 if summary["artifact_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
