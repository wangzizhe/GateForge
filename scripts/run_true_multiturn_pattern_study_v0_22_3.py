#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_true_multiturn_pattern_study_v0_22_3 import (
    DEFAULT_AUDIT_PATH,
    DEFAULT_OUT_DIR,
    run_true_multiturn_pattern_study,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.22.3 true multi-turn pattern study.")
    parser.add_argument("--audit-path", default=str(DEFAULT_AUDIT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    summary = run_true_multiturn_pattern_study(
        audit_path=Path(args.audit_path),
        out_dir=Path(args.out_dir),
    )
    print(
        "status={status} true_multi={true_multi_case_count} mechanisms={mechanism_counts}".format(
            **summary
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
