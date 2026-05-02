#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_submit_decision_signal_audit_v0_43_2 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    DEFAULT_RECORDS,
    run_submit_decision_signal_audit,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit precise submit-decision success signals.")
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    summary = run_submit_decision_signal_audit(records_path=args.records, out_dir=args.out_dir)
    print(
        json.dumps(
            {
                "status": summary["status"],
                "successful_omc_evidence_record_count": summary["successful_omc_evidence_record_count"],
                "cases_with_successful_omc_evidence": summary["cases_with_successful_omc_evidence"],
                "decision": summary["decision"],
            },
            sort_keys=True,
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

