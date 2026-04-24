#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_workflow_admission_audit_v0_21_2 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    run_workflow_admission_audit,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit v0.21.2 workflow-proximal admission.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    summary = run_workflow_admission_audit(out_dir=Path(args.out_dir))
    print(
        "status={status} audited={audited} main={main} blocked={blocked} decision={decision} out={out}".format(
            status=summary["status"],
            audited=summary["audited_candidate_count"],
            main=summary["main_admissible_count"],
            blocked=summary["blocked_from_main_benchmark_count"],
            decision=summary["benchmark_admission_decision"],
            out=Path(args.out_dir),
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
