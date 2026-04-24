#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_adaptive_budget_v0_20_1 import DEFAULT_MULTI_C5_DIR  # noqa: E402
from gateforge.agent_modelica_candidate_diversity_v0_20_3 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    run_candidate_diversity_audit,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze v0.20.3 candidate diversity.")
    parser.add_argument("--multi-c5-dir", default=str(DEFAULT_MULTI_C5_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    summary = run_candidate_diversity_audit(
        multi_c5_dir=Path(args.multi_c5_dir),
        out_dir=Path(args.out_dir),
    )
    print(
        "status={status} rounds={rounds} avg_structural_unique={unique:.3f} top2_retention={top2:.3f} top4_retention={top4:.3f} recommendation={rec} out={out}".format(
            status=summary.get("status"),
            rounds=summary.get("round_count"),
            unique=float(summary.get("average_structural_uniqueness_rate") or 0.0),
            top2=float(summary.get("top2_simulate_round_retention") or 0.0),
            top4=float(summary.get("top4_simulate_round_retention") or 0.0),
            rec=summary.get("recommendation"),
            out=Path(args.out_dir),
        )
    )
    return 0 if summary.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
