#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_contract_validator_v0_23_5 import (
    DEFAULT_OUT_DIR,
    build_contract_validation_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.23.5 contract validator.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    summary = build_contract_validation_report(out_dir=Path(args.out_dir))
    print(
        "status={status} datasets={dataset_counts} validation_errors={total_validation_error_count}".format(
            **summary
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
