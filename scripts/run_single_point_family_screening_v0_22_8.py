#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_single_point_family_screening_v0_22_8 import (
    DEFAULT_ADMISSION_PATH,
    DEFAULT_OUT_DIR,
    run_family_generalization_screening,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.22.8 single-point family live screening.")
    parser.add_argument("--admission-path", default=str(DEFAULT_ADMISSION_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--max-rounds", type=int, default=8)
    parser.add_argument("--timeout-sec", type=int, default=420)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    report = run_family_generalization_screening(
        admission_path=Path(args.admission_path),
        out_dir=Path(args.out_dir),
        max_rounds=max(1, int(args.max_rounds)),
        timeout_sec=max(1, int(args.timeout_sec)),
        limit=args.limit,
    )
    agg = report["aggregate"]
    print(
        "cases={total_cases} pass={pass_count} true_multi={multi_turn_useful_count} "
        "quality={sample_quality_counts} strict={strict_no_auxiliary_packs}".format(**agg)
    )
    return 0 if agg["total_cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
