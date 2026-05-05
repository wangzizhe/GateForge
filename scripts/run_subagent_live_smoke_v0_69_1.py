from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_subagent_isolation_v0_69_0 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    run_live_subagent_repair,
)
from gateforge.agent_modelica_workspace_style_probe_v0_67_0 import load_holdout_tasks  # noqa: E402
from gateforge.agent_modelica_boundary_tool_use_baseline_v0_29_2 import (  # noqa: E402
    task_to_tool_use_case,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.69.1 single sub-agent live smoke.")
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--strategy-hint", required=True)
    parser.add_argument("--diagnostic-hint", default="")
    parser.add_argument("--planner-backend", default="auto")
    parser.add_argument("--max-steps", type=int, default=6)
    parser.add_argument("--max-token-budget", type=int, default=48000)
    args = parser.parse_args()

    tasks = [
        task for task in load_holdout_tasks(args.tasks)
        if str(task.get("case_id") or "") == args.case_id
    ]
    if not tasks:
        raise SystemExit(f"case_not_found:{args.case_id}")

    summary = run_live_subagent_repair(
        case=task_to_tool_use_case(tasks[0]),
        out_dir=args.out_dir,
        strategy_hint=args.strategy_hint,
        diagnostic_hint=args.diagnostic_hint,
        planner_backend=args.planner_backend,
        max_steps=args.max_steps,
        max_token_budget=args.max_token_budget,
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
