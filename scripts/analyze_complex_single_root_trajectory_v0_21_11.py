#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_complex_single_root_trajectory_attribution_v0_21_11 import (
    DEFAULT_OUT_DIR,
    DEFAULT_RUN_DIRS,
    build_trajectory_attribution,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze strict complex single-root trajectories.")
    parser.add_argument(
        "--run-dir",
        action="append",
        default=None,
        help="Trajectory run directory. Can be supplied multiple times.",
    )
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    run_dirs = [Path(value) for value in args.run_dir] if args.run_dir else list(DEFAULT_RUN_DIRS)
    summary = build_trajectory_attribution(run_dirs=run_dirs, out_dir=Path(args.out_dir))
    print(
        "status={status} observations={obs} pass={passed}/{total} multiturn={multi} stability={stability} next={next_action}".format(
            status=summary["status"],
            obs=summary["case_observation_count"],
            passed=summary["pass_count"],
            total=summary["case_observation_count"],
            multi=summary["multiturn_pass_count"],
            stability=(summary.get("stability") or {}).get("stability_status"),
            next_action=summary["next_action"],
        )
    )
    return 0 if summary["case_observation_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
