#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_benchmark_v1_closeout_v0_58_0 import run_benchmark_v1_closeout  # noqa: E402


def main() -> int:
    summary = run_benchmark_v1_closeout()
    print(
        json.dumps(
            {
                "status": summary["status"],
                "readiness_status": summary["readiness_status"],
                "freeze_ready": summary["freeze_ready"],
                "blockers": summary["blockers"],
            },
            sort_keys=True,
        )
    )
    return 0 if summary["artifact_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
