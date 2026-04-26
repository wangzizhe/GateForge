#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_capability_slice_audit_v0_27_11 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    DEFAULT_RESULTS,
    DEFAULT_SLICE_PLAN,
    run_capability_slice_audit,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit v0.27.10 capability slice under the current DeepSeek harness.")
    parser.add_argument("--slice-plan", default=str(DEFAULT_SLICE_PLAN))
    parser.add_argument("--results", default=str(DEFAULT_RESULTS))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    summary = run_capability_slice_audit(
        slice_plan_path=Path(args.slice_plan),
        results_path=Path(args.results),
        out_dir=Path(args.out_dir),
    )
    print(
        "status={status} decision={decision} cases={audited_case_count} pass={pass_count} "
        "failure_signal={failure_signal_count}".format(**summary)
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
