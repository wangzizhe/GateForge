from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_connector_balance_failure_analysis_v0_29_8 import (
    DEFAULT_BASE_RESULTS,
    DEFAULT_CASE_ID,
    DEFAULT_OUT_DIR,
    DEFAULT_STRUCTURAL_RESULTS,
    run_connector_balance_failure_analysis,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze persistent connector-balance failure traces.")
    parser.add_argument("--base-results", type=Path, default=DEFAULT_BASE_RESULTS)
    parser.add_argument("--structural-results", type=Path, default=DEFAULT_STRUCTURAL_RESULTS)
    parser.add_argument("--case-id", default=DEFAULT_CASE_ID)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    summary = run_connector_balance_failure_analysis(
        base_results_path=args.base_results,
        structural_results_path=args.structural_results,
        out_dir=args.out_dir,
        case_id=args.case_id,
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
