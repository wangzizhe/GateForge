#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_positive_source_harvest_v0_59_0 import run_positive_source_harvest  # noqa: E402


def main() -> int:
    summary = run_positive_source_harvest()
    print(
        json.dumps(
            {
                "status": summary["status"],
                "readiness_status": summary["readiness_status"],
                "positive_source_case_count": summary["positive_source_case_count"],
                "missing_positive_source_count": summary["missing_positive_source_count"],
            },
            sort_keys=True,
        )
    )
    return 0 if summary["artifact_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
