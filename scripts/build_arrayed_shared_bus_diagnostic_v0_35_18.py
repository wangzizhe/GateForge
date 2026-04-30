#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_arrayed_shared_bus_tool_v0_35_18 import arrayed_shared_bus_diagnostic

DEFAULT_CASE_PATH = (
    REPO_ROOT
    / "assets_private"
    / "benchmarks"
    / "agent_comparison_v1"
    / "tasks"
    / "repair"
    / "sem_22_arrayed_three_branch_probe_bus.json"
)
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "arrayed_shared_bus_diagnostic_v0_35_18"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.35.18 arrayed shared-bus diagnostic artifact.")
    parser.add_argument("--case-path", type=Path, default=DEFAULT_CASE_PATH)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    case_payload = json.loads(args.case_path.read_text(encoding="utf-8"))
    diagnostic = json.loads(arrayed_shared_bus_diagnostic(str(case_payload.get("initial_model") or "")))
    summary = {
        "version": "v0.35.18",
        "status": "PASS" if diagnostic.get("shared_bus_set_count", 0) > 0 else "REVIEW",
        "case_id": case_payload.get("case_id"),
        "analysis_scope": "arrayed_shared_bus_diagnostic",
        "shared_bus_set_count": diagnostic.get("shared_bus_set_count", 0),
        "diagnostic": diagnostic,
        "discipline": {
            "deterministic_repair_added": False,
            "candidate_selection_added": False,
            "auto_submit_added": False,
            "wrapper_patch_generated": False,
        },
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
