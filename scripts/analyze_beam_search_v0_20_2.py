#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_adaptive_budget_v0_20_1 import DEFAULT_MULTI_C5_DIR  # noqa: E402
from gateforge.agent_modelica_beam_search_v0_20_2 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    run_beam_replay,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze v0.20.2 beam selector offline replay.")
    parser.add_argument("--multi-c5-dir", default=str(DEFAULT_MULTI_C5_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--beam-width", type=int, default=2)
    args = parser.parse_args()

    summary = run_beam_replay(
        multi_c5_dir=Path(args.multi_c5_dir),
        out_dir=Path(args.out_dir),
        beam_width=args.beam_width,
    )
    print(
        "status={status} cases={cases} beam_width={beam} savings={savings} savings_rate={rate:.3f} sim_retention={sim:.3f} recommendation={rec} out={out}".format(
            status=summary.get("status"),
            cases=summary.get("case_count"),
            beam=summary.get("beam_width"),
            savings=summary.get("node_savings"),
            rate=float(summary.get("node_savings_rate") or 0.0),
            sim=float(summary.get("simulate_node_retention_rate") or 0.0),
            rec=summary.get("promotion_recommendation"),
            out=Path(args.out_dir),
        )
    )
    return 0 if summary.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
