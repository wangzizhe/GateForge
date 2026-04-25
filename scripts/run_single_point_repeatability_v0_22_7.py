#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_single_point_repeatability_v0_22_7 import (
    DEFAULT_ADMISSION_PATH,
    DEFAULT_OUT_DIR,
    DEFAULT_REFERENCE_SUMMARY_PATH,
    run_single_point_repeatability,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.22.7 single-point complex repeatability audit.")
    parser.add_argument("--admission-path", default=str(DEFAULT_ADMISSION_PATH))
    parser.add_argument("--reference-summary", default=str(DEFAULT_REFERENCE_SUMMARY_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--repeat-count", type=int, default=1)
    parser.add_argument("--max-rounds", type=int, default=8)
    parser.add_argument("--timeout-sec", type=int, default=420)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    summary = run_single_point_repeatability(
        admission_path=Path(args.admission_path),
        reference_summary_path=Path(args.reference_summary),
        out_dir=Path(args.out_dir),
        repeat_count=max(0, int(args.repeat_count)),
        max_rounds=max(1, int(args.max_rounds)),
        timeout_sec=max(1, int(args.timeout_sec)),
        limit=args.limit,
    )
    print(
        "status={status} candidates={candidate_count} observations={observation_count} "
        "true_multi={true_multi_observation_count} stability={candidate_stability_counts}".format(**summary)
    )
    return 0 if summary["observation_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
