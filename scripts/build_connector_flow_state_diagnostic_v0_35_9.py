#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_benchmark_loader_v0_29_0 import load_and_validate_task  # noqa: E402
from gateforge.agent_modelica_connector_flow_family_expansion_v0_35_0 import (  # noqa: E402
    DEFAULT_TASK_ROOT,
    V0350_CASE_IDS,
)
from gateforge.agent_modelica_connector_flow_state_tool_v0_35_9 import connector_flow_state_diagnostic  # noqa: E402

DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "connector_flow_state_diagnostic_v0_35_9"


def build_summary(*, task_root: Path = DEFAULT_TASK_ROOT, out_dir: Path = DEFAULT_OUT_DIR) -> dict:
    rows = []
    for case_id in V0350_CASE_IDS:
        task, errors = load_and_validate_task(task_root / f"{case_id}.json")
        if task is None or errors:
            rows.append({"case_id": case_id, "status": "REVIEW", "errors": errors or ["task_missing"]})
            continue
        payload = json.loads(connector_flow_state_diagnostic(str(task.get("initial_model") or "")))
        rows.append(
            {
                "case_id": case_id,
                "status": "PASS",
                "connection_set_count": len(payload["connection_sets"]),
                "flow_owner_row_count": len(payload["flow_owner_rows"]),
                "unowned_measurement_component_count": len(payload["unowned_measurement_components"]),
                "diagnostic_only": payload["diagnostic_only"],
                "patch_generated": payload["patch_generated"],
                "candidate_selected": payload["candidate_selected"],
            }
        )
    summary = {
        "version": "v0.35.9",
        "status": "PASS" if rows and all(row["status"] == "PASS" for row in rows) else "REVIEW",
        "analysis_scope": "connector_flow_state_diagnostic",
        "case_count": len(rows),
        "rows": rows,
        "decision": "connector_flow_state_diagnostic_ready_for_live_ab" if rows and all(row["status"] == "PASS" for row in rows) else "connector_flow_state_diagnostic_needs_review",
        "discipline": {
            "deterministic_repair_added": False,
            "candidate_selection_added": False,
            "auto_submit_added": False,
            "wrapper_patch_generated": False,
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.35.9 connector flow state diagnostic summary.")
    parser.add_argument("--task-root", type=Path, default=DEFAULT_TASK_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    summary = build_summary(task_root=args.task_root, out_dir=args.out_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
