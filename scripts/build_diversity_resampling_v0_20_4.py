#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_adaptive_budget_v0_20_1 import DEFAULT_MULTI_C5_DIR  # noqa: E402
from gateforge.agent_modelica_diversity_resampling_v0_20_4 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    run_diversity_resampling_profile,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.20.4 diversity-aware resampling profile.")
    parser.add_argument("--multi-c5-dir", default=str(DEFAULT_MULTI_C5_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    summary = run_diversity_resampling_profile(
        multi_c5_dir=Path(args.multi_c5_dir),
        out_dir=Path(args.out_dir),
    )
    print(
        "status={status} rounds={rounds} diversity={diversity} rate={rate:.3f} avg_structural_unique={unique:.3f} out={out}".format(
            status=summary.get("status"),
            rounds=summary.get("round_count"),
            diversity=summary.get("diversity_resample_count"),
            rate=float(summary.get("diversity_resample_rate") or 0.0),
            unique=float(summary.get("average_structural_uniqueness_rate") or 0.0),
            out=Path(args.out_dir),
        )
    )
    return 0 if summary.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
