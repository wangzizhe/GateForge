#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_hard_core_adjacent_closeout_v0_48_9 import run_hard_core_adjacent_closeout  # noqa: E402


def main() -> int:
    summary = run_hard_core_adjacent_closeout()
    print(
        json.dumps(
            {
                "status": summary["status"],
                "new_hard_negative_candidate_count": summary["new_hard_negative_candidate_count"],
                "difficulty_bucket_counts": summary["difficulty_bucket_counts"],
            },
            sort_keys=True,
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
