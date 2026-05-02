#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_candidate_family_coverage_v0_46_0 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    DEFAULT_RESULTS,
    run_candidate_family_coverage,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit candidate family coverage for remaining semantic failures.")
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    summary = run_candidate_family_coverage(results_path=args.results, out_dir=args.out_dir)
    print(
        json.dumps(
            {
                "status": summary["status"],
                "family_counts": summary["family_counts"],
                "missing_family_counts": summary["missing_family_counts"],
            },
            sort_keys=True,
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

