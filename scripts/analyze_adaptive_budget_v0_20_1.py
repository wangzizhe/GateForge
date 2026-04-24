#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_adaptive_budget_v0_20_1 import (  # noqa: E402
    DEFAULT_MULTI_C5_DIR,
    DEFAULT_OUT_DIR,
    run_adaptive_budget_replay,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze v0.20.1 adaptive budget offline replay.")
    parser.add_argument("--multi-c5-dir", default=str(DEFAULT_MULTI_C5_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    summary = run_adaptive_budget_replay(
        multi_c5_dir=Path(args.multi_c5_dir),
        out_dir=Path(args.out_dir),
    )
    print(
        "status={status} cases={cases} savings={savings} savings_rate={rate:.3f} sim_retention={sim:.3f} recommendation={rec} out={out}".format(
            status=summary.get("status"),
            cases=summary.get("case_count"),
            savings=summary.get("candidate_savings"),
            rate=float(summary.get("candidate_savings_rate") or 0.0),
            sim=float(summary.get("simulate_round_retention_rate") or 0.0),
            rec=summary.get("promotion_recommendation"),
            out=Path(args.out_dir),
        )
    )
    return 0 if summary.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
