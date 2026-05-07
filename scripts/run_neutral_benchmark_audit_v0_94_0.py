#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_neutral_benchmark_audit_v0_94_0 import run_neutral_benchmark_audit  # noqa: E402


def main() -> int:
    summary = run_neutral_benchmark_audit()
    print(
        json.dumps(
            {
                "status": summary["status"],
                "audited_path_count": summary["audited_path_count"],
                "review_path_count": summary["review_path_count"],
                "conclusion_allowed": summary["conclusion_allowed"],
            },
            sort_keys=True,
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
