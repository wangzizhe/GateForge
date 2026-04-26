#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_deepseek_slice_review_v0_27_2 import (  # noqa: E402
    DEFAULT_INPUT_RESULTS,
    DEFAULT_OUT_DIR,
    run_deepseek_slice_review,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Review v0.27.1 DeepSeek source-backed slice trajectories.")
    parser.add_argument("--input-results", default=str(DEFAULT_INPUT_RESULTS))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    summary = run_deepseek_slice_review(
        input_results=Path(args.input_results),
        out_dir=Path(args.out_dir),
    )
    print(
        "status={status} decision={decision} cases={case_count} pass={pass_count} "
        "true_multi={true_multi_turn_count} repeated_failure={repeated_failure_signature}".format(**summary)
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
