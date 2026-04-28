#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_semantic_rerun_summary_v0_29_14 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    build_semantic_rerun_summary,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize semantic narrow rerun stability.")
    parser.add_argument("--run-dir", type=Path, action="append", required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    summary = build_semantic_rerun_summary(run_dirs=list(args.run_dir), out_dir=args.out_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
