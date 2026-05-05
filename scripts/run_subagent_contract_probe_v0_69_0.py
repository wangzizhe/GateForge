from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_subagent_isolation_v0_69_0 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    run_subagent_contract_probe,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.69.0 sub-agent contract mock probe.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--mock-pass", action="store_true")
    args = parser.parse_args()

    outcome = None
    if args.mock_pass:
        outcome = {
            "subagent_verdict": "PASS",
            "submitted": True,
            "submitted_candidate_id": "candidate_1",
            "token_used": 100,
            "candidates": [
                {
                    "candidate_id": "candidate_1",
                    "model_text": "model M\nend M;\n",
                    "check_ok": True,
                    "simulate_ok": True,
                    "submitted": True,
                    "omc_output": "The simulation finished successfully.",
                }
            ],
        }

    summary = run_subagent_contract_probe(out_dir=args.out_dir, outcome=outcome)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
