#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_generation_audit_v0_19_60 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    run_generation_audit,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.19.60 NL-to-Modelica generation audit.")
    parser.add_argument("--planner-backend", default="auto")
    parser.add_argument("--max-tasks", type=int, default=0)
    parser.add_argument("--task-id", default="")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--dry-run-fixture", action="store_true")
    args = parser.parse_args()

    summary = run_generation_audit(
        planner_backend=args.planner_backend,
        out_dir=Path(args.out_dir),
        task_id=args.task_id,
        max_tasks=args.max_tasks,
        dry_run_fixture=bool(args.dry_run_fixture),
    )
    print(
        "status={status} tasks={tasks} pass={passes} d_pq={distance} out={out}".format(
            status=summary.get("status"),
            tasks=summary.get("task_count"),
            passes=summary.get("pass_count"),
            distance=summary.get("d_pq_total_variation"),
            out=Path(args.out_dir),
        )
    )
    return 0 if summary.get("status") in {"PASS", "DRY_RUN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

