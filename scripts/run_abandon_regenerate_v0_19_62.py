#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_abandon_regenerate_v0_19_62 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    DEFAULT_V060_INPUT_DIR,
    run_abandon_regenerate,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.19.62 abandon-regenerate audit.")
    parser.add_argument("--planner-backend", default="auto")
    parser.add_argument("--input-dir", default=str(DEFAULT_V060_INPUT_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--dry-run-fixture", action="store_true")
    parser.add_argument("--generation-cost", type=float, default=1.0)
    parser.add_argument("--repair-cost-multiplier", type=float, default=1.5)
    parser.add_argument("--min-no-improvement-rounds", type=int, default=1)
    args = parser.parse_args()
    summary = run_abandon_regenerate(
        planner_backend=args.planner_backend,
        input_dir=Path(args.input_dir),
        out_dir=Path(args.out_dir),
        dry_run_fixture=bool(args.dry_run_fixture),
        generation_cost=float(args.generation_cost),
        repair_cost_multiplier=float(args.repair_cost_multiplier),
        min_no_improvement_rounds=int(args.min_no_improvement_rounds),
    )
    print(
        "status={status} tasks={tasks} regen={regen} without={without_rate} with={with_rate} out={out}".format(
            status=summary.get("status"),
            tasks=summary.get("task_count"),
            regen=summary.get("abandon_trigger_count"),
            without_rate=summary.get("without_abandon_pass_rate"),
            with_rate=summary.get("with_abandon_pass_rate"),
            out=Path(args.out_dir),
        )
    )
    return 0 if summary.get("status") in {"PASS", "DRY_RUN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

