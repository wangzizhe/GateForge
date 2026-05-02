#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_hard_core_expansion_slice_v0_39_0 import (  # noqa: E402
    DEFAULT_CALIBRATION,
    DEFAULT_OUT_DIR,
    run_hard_core_expansion_slice,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.39 hard-core expansion slice.")
    parser.add_argument("--calibration", type=Path, default=DEFAULT_CALIBRATION)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    summary = run_hard_core_expansion_slice(
        calibration_path=args.calibration,
        out_dir=args.out_dir,
        limit=args.limit,
    )
    print(json.dumps({"status": summary["status"], "selected_case_ids": summary["selected_case_ids"]}, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

