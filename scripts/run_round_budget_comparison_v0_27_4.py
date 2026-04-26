#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_round_budget_comparison_v0_27_4 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    DEFAULT_THREE_ROUND_RESULTS,
    DEFAULT_TWO_ROUND_RESULTS,
    run_round_budget_comparison,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare v0.27.1 two-round and v0.27.3 three-round DeepSeek artifacts.")
    parser.add_argument("--two-round-results", default=str(DEFAULT_TWO_ROUND_RESULTS))
    parser.add_argument("--three-round-results", default=str(DEFAULT_THREE_ROUND_RESULTS))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    summary = run_round_budget_comparison(
        two_round_results=Path(args.two_round_results),
        three_round_results=Path(args.three_round_results),
        out_dir=Path(args.out_dir),
    )
    print(
        "status={status} decision={decision} common={common_case_count} "
        "two_pass={two_round_pass_count} three_pass={three_round_pass_count} "
        "improved={improved_count} regressed={regressed_count} stalled={added_round_stall_count}".format(**summary)
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
