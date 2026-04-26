#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_harness_regression_ab_v0_26_4 import (
    DEFAULT_INPUT,
    DEFAULT_OUT_DIR,
    build_harness_regression_ab,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.26.4 harness regression A/B.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    summary = build_harness_regression_ab(input_path=Path(args.input), out_dir=Path(args.out_dir))
    print("status={status} decision={decision} trajectories={trajectory_count}".format(**summary))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
