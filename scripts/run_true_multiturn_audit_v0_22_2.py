#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_true_multiturn_audit_v0_22_2 import (
    DEFAULT_OUT_DIR,
    DEFAULT_RUN_DIRS,
    run_true_multiturn_audit,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.22.2 true multi-turn offline audit.")
    parser.add_argument("--run-dir", action="append", default=None)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    run_dirs = [Path(item) for item in args.run_dir] if args.run_dir else list(DEFAULT_RUN_DIRS)
    summary = run_true_multiturn_audit(run_dirs=run_dirs, out_dir=Path(args.out_dir))
    print(
        "status={status} audited={audited_case_count} pass={pass_count} "
        "true_multi={true_multi_repair_pass_count} false_multiturn={false_multiturn_by_attempt_count}".format(
            **summary
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
