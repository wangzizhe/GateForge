#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_hard_core_adjacent_difficulty_summary_v0_48_7 import run_hard_core_adjacent_difficulty_summary  # noqa: E402


def main() -> int:
    summary = run_hard_core_adjacent_difficulty_summary()
    print(
        json.dumps(
            {
                "status": summary["status"],
                "bucket_counts": summary["bucket_counts"],
                "hard_negative_candidate_case_ids": summary["hard_negative_candidate_case_ids"],
            },
            sort_keys=True,
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
