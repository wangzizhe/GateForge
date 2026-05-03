#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_hard_positive_resolution_plan_v0_60_2 import run_hard_positive_resolution_plan  # noqa: E402


def main() -> int:
    summary = run_hard_positive_resolution_plan()
    print(
        json.dumps(
            {
                "status": summary["status"],
                "near_miss_reference_queue_count": summary["near_miss_reference_queue_count"],
                "frontier_unresolved_count": summary["frontier_unresolved_count"],
            },
            sort_keys=True,
        )
    )
    return 0 if summary["artifact_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
