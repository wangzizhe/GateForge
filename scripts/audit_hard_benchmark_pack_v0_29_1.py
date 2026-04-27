#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_hard_benchmark_gate_v0_29_1 import (
    DEFAULT_OUT_DIR,
    DEFAULT_TASK_ROOT,
    run_hard_benchmark_gate,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit hard benchmark candidates for boundary pressure.")
    parser.add_argument("--task-root", type=Path, default=DEFAULT_TASK_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--case-id-prefix", default="")
    args = parser.parse_args()

    summary = run_hard_benchmark_gate(
        task_root=args.task_root,
        out_dir=args.out_dir,
        case_id_prefix=args.case_id_prefix,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
