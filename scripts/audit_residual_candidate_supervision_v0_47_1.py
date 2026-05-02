#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_residual_candidate_supervision_audit_v0_47_1 import (  # noqa: E402
    DEFAULT_EXAMPLES,
    DEFAULT_OUT_DIR,
    run_residual_candidate_supervision_audit,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit residual-to-candidate supervision readiness.")
    parser.add_argument("--examples", type=Path, default=DEFAULT_EXAMPLES)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    summary = run_residual_candidate_supervision_audit(examples_path=args.examples, out_dir=args.out_dir)
    print(
        json.dumps(
            {
                "status": summary["status"],
                "trainability_status": summary["trainability_status"],
                "negative_only_example_count": summary["negative_only_example_count"],
                "positive_supervision_example_count": summary["positive_supervision_example_count"],
            },
            sort_keys=True,
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
