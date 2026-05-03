#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_solvable_holdout_baseline_runner_v0_61_2 import (  # noqa: E402
    run_solvable_holdout_baseline,
    run_solvable_holdout_baseline_streaming,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run GateForge base tool-use baseline on solvable benchmark holdout.")
    parser.add_argument("--tasks-path", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--max-steps", type=int, default=10)
    parser.add_argument("--max-token-budget", type=int, default=32000)
    parser.add_argument("--planner-backend", default="auto")
    parser.add_argument("--tool-profile", default="base")
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--streaming", action="store_true")
    args = parser.parse_args()
    kwargs = {
        "max_steps": args.max_steps,
        "max_token_budget": args.max_token_budget,
        "planner_backend": args.planner_backend,
        "tool_profile": args.tool_profile,
    }
    if args.tasks_path is not None:
        kwargs["tasks_path"] = args.tasks_path
    if args.out_dir is not None:
        kwargs["out_dir"] = args.out_dir
    if args.case_id:
        kwargs["case_ids"] = list(args.case_id)
    if args.limit:
        kwargs["limit"] = args.limit
    if args.streaming:
        summary = run_solvable_holdout_baseline_streaming(**kwargs)
    else:
        summary = run_solvable_holdout_baseline(**kwargs)
    print(
        json.dumps(
            {
                "status": summary["status"],
                "case_count": summary["case_count"],
                "completed_case_count": summary.get("completed_case_count", summary["case_count"]),
                "pass_count": summary["pass_count"],
                "fail_count": summary["fail_count"],
                "provider_error_count": summary["provider_error_count"],
            },
            sort_keys=True,
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
