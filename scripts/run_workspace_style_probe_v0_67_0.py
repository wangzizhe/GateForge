from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_workspace_style_probe_v0_67_0 import (
    DEFAULT_OUT_DIR,
    DEFAULT_TASKS,
    DEFAULT_RUN_PROFILE,
    RUN_PROFILES,
    run_workspace_style_probe,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the transparent Modelica workspace runner."
    )
    parser.add_argument("--tasks", type=Path, default=DEFAULT_TASKS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-steps", type=int, default=10)
    parser.add_argument("--max-token-budget", type=int, default=32000)
    parser.add_argument("--planner-backend", default="auto")
    parser.add_argument("--per-case-timeout-sec", type=int, default=0)
    parser.add_argument("--summary-version", default="v0.67.0")
    parser.add_argument(
        "--run-profile",
        choices=sorted(RUN_PROFILES),
        default=DEFAULT_RUN_PROFILE,
        help="Named run profile. Explicit CLI flags override profile defaults.",
    )
    args = parser.parse_args()
    profile = RUN_PROFILES.get(str(args.run_profile), {})
    if profile:
        if args.max_steps == parser.get_default("max_steps"):
            args.max_steps = int(profile.get("max_steps", args.max_steps))
        if args.max_token_budget == parser.get_default("max_token_budget"):
            args.max_token_budget = int(profile.get("max_token_budget", args.max_token_budget))
        if args.per_case_timeout_sec == parser.get_default("per_case_timeout_sec"):
            args.per_case_timeout_sec = int(profile.get("per_case_timeout_sec", args.per_case_timeout_sec))
    summary = run_workspace_style_probe(
        tasks_path=args.tasks,
        out_dir=args.out_dir,
        case_ids=list(args.case_id or []),
        limit=args.limit,
        max_steps=args.max_steps,
        max_token_budget=args.max_token_budget,
        planner_backend=args.planner_backend,
        per_case_timeout_sec=args.per_case_timeout_sec,
        summary_version=args.summary_version,
        run_profile=str(args.run_profile),
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
