#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_difficulty_calibration_v0_38_0 import (  # noqa: E402
    build_difficulty_calibration_summary,
)
from scripts.build_difficulty_calibration_v0_38_0 import load_gate_rows, load_jsonl  # noqa: E402


DEFAULT_REGISTRY = REPO_ROOT / "artifacts" / "hard_pool_registry_v0_37_12" / "registry.jsonl"
DEFAULT_GATE = REPO_ROOT / "artifacts" / "hard_pool_registry_v0_37_12" / "gate_summary.json"
DEFAULT_RESULTS = [REPO_ROOT / "artifacts" / "difficulty_baseline_v0_38_3_provider_retry" / "results.jsonl"]
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "difficulty_calibration_v0_38_3"


def load_run_evidence(paths: list[Path]) -> dict[str, dict[str, int]]:
    evidence: dict[str, dict[str, int]] = {}
    for path in paths:
        for row in load_jsonl(path):
            if str(row.get("provider_error") or "").strip():
                continue
            case_id = str(row.get("case_id") or "")
            if not case_id:
                continue
            counts = evidence.setdefault(case_id, {"pass_count": 0, "fail_count": 0})
            if row.get("final_verdict") == "PASS":
                counts["pass_count"] += 1
            else:
                counts["fail_count"] += 1
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="Update v0.38 difficulty calibration with baseline results.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--gate-summary", type=Path, default=DEFAULT_GATE)
    parser.add_argument("--results-jsonl", type=Path, action="append", default=None)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--version", default="v0.38.3")
    args = parser.parse_args()
    result_paths = args.results_jsonl if args.results_jsonl else DEFAULT_RESULTS

    summary = build_difficulty_calibration_summary(
        load_jsonl(args.registry),
        gate_rows=load_gate_rows(args.gate_summary),
        run_evidence_by_case=load_run_evidence(result_paths),
        version=args.version,
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": summary["status"], "bucket_counts": summary["bucket_counts"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
