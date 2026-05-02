#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_difficulty_run_plan_v0_38_1 import build_difficulty_run_plan  # noqa: E402


DEFAULT_CALIBRATION = REPO_ROOT / "artifacts" / "difficulty_calibration_v0_38_0" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "difficulty_run_plan_v0_38_1"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.38.1 difficulty calibration run plan.")
    parser.add_argument("--calibration-summary", type=Path, default=DEFAULT_CALIBRATION)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--max-needs-baseline", type=int, default=12)
    args = parser.parse_args()

    payload = json.loads(args.calibration_summary.read_text(encoding="utf-8"))
    summary = build_difficulty_run_plan(payload, max_needs_baseline=args.max_needs_baseline)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": summary["status"], "planned_case_count": summary["planned_case_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

