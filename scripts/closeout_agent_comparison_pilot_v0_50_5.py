#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_agent_comparison_pilot_closeout_v0_50_5 import run_agent_comparison_pilot_closeout  # noqa: E402


def main() -> int:
    summary = run_agent_comparison_pilot_closeout()
    print(
        json.dumps(
            {
                "status": summary["status"],
                "external_results_ready": summary["external_results_ready"],
                "next_action": summary["next_action"],
            },
            sort_keys=True,
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
