#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_training_substrate_quality_audit_v0_43_1 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    DEFAULT_RECORDS,
    run_training_substrate_quality_audit,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit v0.43 hard-core training substrate quality.")
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    summary = run_training_substrate_quality_audit(records_path=args.records, out_dir=args.out_dir)
    print(
        json.dumps(
            {
                "status": summary["status"],
                "quality_counts": summary["quality_counts"],
                "training_readiness": summary["training_readiness"],
            },
            sort_keys=True,
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

