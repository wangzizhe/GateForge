#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_candidate_critique_trigger_audit_v0_30_2 import (
    DEFAULT_OUT_DIR,
    DEFAULT_RUN_DIRS,
    build_candidate_critique_trigger_audit,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit v0.30.2 candidate critique trigger opportunities.")
    parser.add_argument("--run-dir", action="append", nargs=2, metavar=("VERSION", "PATH"))
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    run_dirs = {version: Path(path) for version, path in args.run_dir} if args.run_dir else DEFAULT_RUN_DIRS
    summary = build_candidate_critique_trigger_audit(run_dirs=run_dirs, out_dir=args.out_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
