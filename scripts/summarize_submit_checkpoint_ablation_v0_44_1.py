#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_submit_checkpoint_ablation_v0_44_1 import (  # noqa: E402
    DEFAULT_BASE_AUDIT,
    DEFAULT_CHECKPOINT_RESULTS,
    DEFAULT_OUT_DIR,
    run_submit_checkpoint_ablation_summary,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize the v0.44 submit-checkpoint ablation.")
    parser.add_argument("--base-audit", type=Path, default=DEFAULT_BASE_AUDIT)
    parser.add_argument("--checkpoint-results", type=Path, default=DEFAULT_CHECKPOINT_RESULTS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    summary = run_submit_checkpoint_ablation_summary(
        base_audit_path=args.base_audit,
        checkpoint_results_path=args.checkpoint_results,
        out_dir=args.out_dir,
    )
    print(
        json.dumps(
            {
                "status": summary["status"],
                "checkpoint_pass_count": summary["checkpoint_pass_count"],
                "target_case_count": summary["target_case_count"],
                "decision": summary["decision"],
            },
            sort_keys=True,
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

