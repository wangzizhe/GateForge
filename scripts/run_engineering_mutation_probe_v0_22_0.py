#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_engineering_mutation_probe_v0_22_0 import (
    DEFAULT_OUT_DIR,
    DEFAULT_SOURCE_INVENTORY_PATH,
    run_engineering_mutation_probe,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.22.0 engineering mutation construction probe.")
    parser.add_argument("--source-inventory", default=str(DEFAULT_SOURCE_INVENTORY_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()

    summary = run_engineering_mutation_probe(
        source_inventory_path=Path(args.source_inventory),
        out_dir=Path(args.out_dir),
        limit=max(0, int(args.limit)),
    )
    print(
        "status={status} candidates={candidate_count} admitted={admitted_count} "
        "rate={admission_pass_rate} conclusion={conclusion}".format(**summary)
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
