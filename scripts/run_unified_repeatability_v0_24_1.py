#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_unified_repeatability_runner_v0_24_1 import (
    DEFAULT_OUT_DIR,
    DEFAULT_SEED_REGISTRY_PATH,
    DEFAULT_TRAJECTORY_PATH,
    run_unified_repeatability,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.24.1 unified repeatability runner.")
    parser.add_argument("--seed-registry-path", default=str(DEFAULT_SEED_REGISTRY_PATH))
    parser.add_argument("--reference-trajectory-path", default=str(DEFAULT_TRAJECTORY_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--family")
    parser.add_argument("--policy")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--repeat-count", type=int, default=1)
    parser.add_argument("--max-rounds", type=int, default=8)
    parser.add_argument("--timeout-sec", type=int, default=420)
    parser.add_argument("--execute", action="store_true", help="Reserved for caller-supplied executor integrations.")
    args = parser.parse_args()

    summary = run_unified_repeatability(
        seed_registry_path=Path(args.seed_registry_path),
        reference_trajectory_path=Path(args.reference_trajectory_path),
        out_dir=Path(args.out_dir),
        family=args.family,
        policy=args.policy,
        limit=args.limit,
        repeat_count=args.repeat_count,
        max_rounds=args.max_rounds,
        timeout_sec=args.timeout_sec,
        dry_run=not args.execute,
    )
    print(
        "status={status} dry_run={dry_run} seeds={selected_seed_count} "
        "new_observations={new_observation_count} candidates={candidate_count}".format(**summary)
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
