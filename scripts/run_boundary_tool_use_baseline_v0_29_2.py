#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_boundary_tool_use_baseline_v0_29_2 import (
    DEFAULT_OUT_DIR,
    DEFAULT_TASK_ROOT,
    run_boundary_tool_use_baseline,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run boundary benchmark cases through the tool-use baseline.")
    parser.add_argument("--task-root", type=Path, default=DEFAULT_TASK_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--case-id-prefix", default="boundary_")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-steps", type=int, default=10)
    parser.add_argument("--max-token-budget", type=int, default=32000)
    parser.add_argument("--planner-backend", default="auto")
    parser.add_argument("--tool-profile", default="base", choices=["base", "structural", "connector"])
    parser.add_argument("--summary-version", default="v0.29.4")
    args = parser.parse_args()

    summary = run_boundary_tool_use_baseline(
        task_root=args.task_root,
        out_dir=args.out_dir,
        case_id_prefix=args.case_id_prefix,
        limit=args.limit,
        max_steps=args.max_steps,
        max_token_budget=args.max_token_budget,
        planner_backend=args.planner_backend,
        tool_profile=args.tool_profile,
        summary_version=args.summary_version,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
