#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_multicandidate_repeatability_summary_v0_29_20 import (
    DEFAULT_OUT_DIR,
    DEFAULT_RUN_DIRS,
    build_multicandidate_repeatability_summary,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize v0.29.20 multi-candidate repeatability results.")
    parser.add_argument("--run-dir", action="append", type=Path, default=[])
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    summary = build_multicandidate_repeatability_summary(
        run_dirs=list(args.run_dir or DEFAULT_RUN_DIRS),
        out_dir=args.out_dir,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
