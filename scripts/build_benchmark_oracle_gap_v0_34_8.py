#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_benchmark_oracle_gap_v0_34_8 import (  # noqa: E402
    DEFAULT_BOUNDARY_ATTRIBUTION,
    DEFAULT_OUT_DIR,
    DEFAULT_TASK_PATH,
    build_benchmark_oracle_gap,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.34.8 benchmark oracle gap audit.")
    parser.add_argument("--task-path", type=Path, default=DEFAULT_TASK_PATH)
    parser.add_argument("--boundary-attribution", type=Path, default=DEFAULT_BOUNDARY_ATTRIBUTION)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    summary = build_benchmark_oracle_gap(
        task_path=args.task_path,
        boundary_attribution_path=args.boundary_attribution,
        out_dir=args.out_dir,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
