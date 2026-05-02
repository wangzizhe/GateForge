#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_hard_core_training_substrate_v0_43_0 import (  # noqa: E402
    DEFAULT_CALIBRATION,
    DEFAULT_OUT_DIR,
    run_training_substrate_build,
)


DEFAULT_RESULT_PATHS = [
    REPO_ROOT / "artifacts" / "difficulty_baseline_v0_38_3_provider_retry" / "results.jsonl",
    REPO_ROOT / "artifacts" / "difficulty_repeatability_v0_38_4_hard_candidates" / "results.jsonl",
    REPO_ROOT / "artifacts" / "hard_core_expansion_baseline_v0_39_1" / "results.jsonl",
    REPO_ROOT / "artifacts" / "hard_core_expansion_repeatability_v0_39_2" / "results.jsonl",
    REPO_ROOT / "artifacts" / "hard_core_expansion_sem13_retry_v0_39_4" / "results.jsonl",
    REPO_ROOT / "artifacts" / "hard_core_expansion_baseline_v0_40_1" / "results.jsonl",
    REPO_ROOT / "artifacts" / "hard_core_expansion_repeatability_v0_40_2" / "results.jsonl",
    REPO_ROOT / "artifacts" / "hard_core_expansion_baseline_v0_41_1" / "results.jsonl",
    REPO_ROOT / "artifacts" / "hard_core_expansion_repeatability_v0_41_2" / "results.jsonl",
    REPO_ROOT / "artifacts" / "hard_core_generated_variant_baseline_v0_42_1" / "results.jsonl",
    REPO_ROOT / "artifacts" / "hard_core_generated_variant_repeatability_v0_42_2" / "results.jsonl",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.43 hard-core training trajectory substrate.")
    parser.add_argument("--calibration", type=Path, default=DEFAULT_CALIBRATION)
    parser.add_argument("--result-jsonl", type=Path, action="append", default=None)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--version", default="v0.43.0")
    args = parser.parse_args()
    result_paths = args.result_jsonl if args.result_jsonl else DEFAULT_RESULT_PATHS
    summary = run_training_substrate_build(
        calibration_path=args.calibration,
        result_paths=result_paths,
        out_dir=args.out_dir,
        version=args.version,
    )
    print(
        json.dumps(
            {
                "status": summary["status"],
                "hard_negative_case_count": summary["hard_negative_case_count"],
                "trajectory_record_count": summary["trajectory_record_count"],
                "repeatable_case_count": summary["repeatable_case_count"],
            },
            sort_keys=True,
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

