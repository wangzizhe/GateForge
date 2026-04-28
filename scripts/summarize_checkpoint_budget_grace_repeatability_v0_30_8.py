#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_checkpoint_budget_grace_repeatability_v0_30_8 import (
    DEFAULT_OUT_DIR,
    DEFAULT_RUN_DIRS,
    build_checkpoint_budget_grace_repeatability,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize v0.30.8 checkpoint budget grace repeatability.")
    parser.add_argument("--run-dir", action="append", nargs=2, metavar=("RUN_ID", "PATH"))
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    run_dirs = {run_id: Path(path) for run_id, path in args.run_dir} if args.run_dir else DEFAULT_RUN_DIRS
    summary = build_checkpoint_budget_grace_repeatability(run_dirs=run_dirs, out_dir=args.out_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
