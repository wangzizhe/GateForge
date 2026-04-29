#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_arrayed_connector_family_v0_32_3 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    DEFAULT_TASK_ROOT,
    build_arrayed_connector_family_summary,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.32.3 arrayed connector family audit.")
    parser.add_argument("--task-root", type=Path, default=DEFAULT_TASK_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    summary = build_arrayed_connector_family_summary(task_root=args.task_root, out_dir=args.out_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
