#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_replay_harness_v0_24_5 import (
    DEFAULT_EXPECTED_CANDIDATE_PATH,
    DEFAULT_EXPECTED_FAMILY_PATH,
    DEFAULT_OUT_DIR,
    DEFAULT_SEED_REGISTRY_PATH,
    DEFAULT_TRAJECTORY_PATH,
    run_replay_harness,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.24.5 replay harness.")
    parser.add_argument("--seed-registry-path", default=str(DEFAULT_SEED_REGISTRY_PATH))
    parser.add_argument("--trajectory-path", default=str(DEFAULT_TRAJECTORY_PATH))
    parser.add_argument("--expected-candidate-path", default=str(DEFAULT_EXPECTED_CANDIDATE_PATH))
    parser.add_argument("--expected-family-path", default=str(DEFAULT_EXPECTED_FAMILY_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    summary = run_replay_harness(
        seed_registry_path=Path(args.seed_registry_path),
        trajectory_path=Path(args.trajectory_path),
        expected_candidate_path=Path(args.expected_candidate_path),
        expected_family_path=Path(args.expected_family_path),
        out_dir=Path(args.out_dir),
    )
    print(
        "status={status} candidates={candidate_count} families={family_count} "
        "candidate_diffs={candidate_diff_count} family_diffs={family_diff_count}".format(**summary)
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
