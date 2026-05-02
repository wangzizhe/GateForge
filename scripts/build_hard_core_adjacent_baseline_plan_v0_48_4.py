#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_hard_core_adjacent_baseline_plan_v0_48_4 import run_hard_core_adjacent_baseline_plan  # noqa: E402


def main() -> int:
    summary = run_hard_core_adjacent_baseline_plan()
    print(
        json.dumps(
            {
                "status": summary["status"],
                "planned_run_count": summary["planned_run_count"],
                "anchor_counts": summary["anchor_counts"],
            },
            sort_keys=True,
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
