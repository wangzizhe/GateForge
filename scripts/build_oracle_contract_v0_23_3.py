#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_oracle_contract_v0_23_3 import (
    DEFAULT_OUT_DIR,
    DEFAULT_TRAJECTORY_PATH,
    build_oracle_contract_index,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.23.3 oracle contract index.")
    parser.add_argument("--trajectory-path", default=str(DEFAULT_TRAJECTORY_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    summary = build_oracle_contract_index(
        trajectory_path=Path(args.trajectory_path),
        out_dir=Path(args.out_dir),
    )
    print(
        "status={status} events={oracle_event_count} statuses={oracle_status_counts} "
        "validation_errors={validation_error_count}".format(**summary)
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
