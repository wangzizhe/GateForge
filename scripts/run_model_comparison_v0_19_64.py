#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_model_comparison_v0_19_64 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    run_model_comparison,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.19.64 multi-model generation comparison.")
    parser.add_argument("--model-profiles", default="")
    parser.add_argument("--max-tasks", type=int, default=6)
    parser.add_argument("--task-id", default="")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--dry-run-fixture", action="store_true")
    args = parser.parse_args()

    summary = run_model_comparison(
        out_dir=Path(args.out_dir),
        model_profiles=args.model_profiles,
        task_id=args.task_id,
        max_tasks=args.max_tasks,
        dry_run_fixture=bool(args.dry_run_fixture),
    )
    print(
        "status={status} completed={completed} blocked={blocked} success={success} out={out}".format(
            status=summary.get("status"),
            completed=",".join(summary.get("completed_profiles") or []),
            blocked=summary.get("blocked_profile_count"),
            success=summary.get("success_criterion_met"),
            out=Path(args.out_dir),
        )
    )
    return 0 if summary.get("status") in {"PASS", "DRY_RUN", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

