#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_arrayed_flow_profile_comparison_v0_35_32 import (
    build_arrayed_flow_profile_comparison,
)


def main() -> int:
    summary = build_arrayed_flow_profile_comparison()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
