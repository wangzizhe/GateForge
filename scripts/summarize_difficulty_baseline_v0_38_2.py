#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_difficulty_baseline_summary_v0_38_2 import (  # noqa: E402
    build_difficulty_baseline_summary,
    load_results_jsonl,
    write_difficulty_baseline_summary_outputs,
)


DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "difficulty_baseline_v0_38_2"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "difficulty_baseline_summary_v0_38_2"


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize v0.38.2 difficulty baseline evidence.")
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    rows = load_results_jsonl(args.run_dir / "results.jsonl")
    summary = build_difficulty_baseline_summary(rows)
    write_difficulty_baseline_summary_outputs(out_dir=args.out_dir, summary=summary)
    print(json.dumps({"status": summary["status"], "conclusion_allowed": summary["conclusion_allowed"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

