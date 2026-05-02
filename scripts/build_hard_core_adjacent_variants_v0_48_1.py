#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_hard_core_adjacent_plan_v0_48_0 import run_hard_core_adjacent_plan  # noqa: E402
from gateforge.agent_modelica_hard_core_adjacent_variants_v0_48_1 import run_hard_core_adjacent_variants  # noqa: E402


def main() -> int:
    plan = run_hard_core_adjacent_plan()
    summary = run_hard_core_adjacent_variants()
    print(
        json.dumps(
            {
                "plan_status": plan["status"],
                "status": summary["status"],
                "variant_count": summary["variant_count"],
                "anchor_counts": summary["anchor_counts"],
            },
            sort_keys=True,
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
