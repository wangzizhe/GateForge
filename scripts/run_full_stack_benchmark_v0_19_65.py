#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_full_stack_benchmark_v0_19_65 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    run_full_stack_benchmark,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.19.65 evidence-gated full stack benchmark summary.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    summary = run_full_stack_benchmark(out_dir=Path(args.out_dir))
    print(
        "status={status} baseline={baseline:.3f} stack={stack:.3f} success={success} out={out}".format(
            status=summary.get("status"),
            baseline=float((summary.get("baseline_arm") or {}).get("clean_pass_rate") or 0.0),
            stack=float((summary.get("full_stack_arm") or {}).get("clean_pass_rate") or 0.0),
            success=summary.get("success_criterion_met"),
            out=Path(args.out_dir),
        )
    )
    return 0 if summary.get("status") in {"PASS", "FAIL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

