#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_harness_inventory_audit_v0_23_0 import (
    DEFAULT_OUT_DIR,
    build_harness_inventory_audit,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.23.0 harness inventory audit.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    summary = build_harness_inventory_audit(out_dir=Path(args.out_dir))
    inventory = summary["file_inventory"]
    gaps = summary["contract_gap_report"]["gap_counts"]
    print(
        "status={status} modules={module_count} scripts={script_count} tests={test_count} "
        "summaries={summary_count} gaps={gaps}".format(
            status=summary["status"],
            module_count=inventory["module_count"],
            script_count=inventory["script_count"],
            test_count=inventory["test_count"],
            summary_count=inventory["summary_count"],
            gaps=gaps,
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
