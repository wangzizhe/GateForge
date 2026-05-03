from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_json


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKBENCH = REPO_ROOT / "artifacts" / "hard_positive_workbench_v0_60_0" / "summary.json"
DEFAULT_ATTEMPTS = REPO_ROOT / "artifacts" / "hard_positive_candidate_attempts_v0_60_1" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hard_positive_resolution_plan_v0_60_2"


def classify_resolution_bucket(row: dict[str, Any]) -> str:
    strategy = str(row.get("reference_strategy") or "")
    case_id = str(row.get("case_id") or "")
    if case_id in {"sem_29_two_branch_probe_bus"}:
        return "near_miss_reference_queue"
    if strategy == "probe_flow_ownership_reference_repair_required":
        return "probe_flow_frontier_unresolved"
    if strategy == "adapter_contract_reference_repair_required":
        return "adapter_contract_frontier_unresolved"
    return "manual_frontier_unresolved"


def build_hard_positive_resolution_plan(
    *,
    workbench_summary: dict[str, Any],
    attempts_summary: dict[str, Any],
    version: str = "v0.60.2",
) -> dict[str, Any]:
    rows = []
    for row in workbench_summary.get("results") or []:
        bucket = classify_resolution_bucket(row)
        rows.append(
            {
                "case_id": str(row.get("case_id") or ""),
                "resolution_bucket": bucket,
                "reference_status": str(row.get("reference_status") or ""),
                "reference_strategy": str(row.get("reference_strategy") or ""),
            }
        )
    near_miss = sorted(row["case_id"] for row in rows if row["resolution_bucket"] == "near_miss_reference_queue")
    frontier = sorted(row["case_id"] for row in rows if row["resolution_bucket"] != "near_miss_reference_queue")
    return {
        "version": version,
        "analysis_scope": "hard_positive_resolution_plan",
        "status": "PASS" if rows else "REVIEW",
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "artifact_complete": True,
        "readiness_status": "hard_positive_resolution_plan_ready",
        "case_count": len(rows),
        "near_miss_reference_queue_count": len(near_miss),
        "frontier_unresolved_count": len(frontier),
        "near_miss_reference_queue_case_ids": near_miss,
        "frontier_unresolved_case_ids": frontier,
        "failed_simple_attempt_count": int(attempts_summary.get("failed_attempt_count") or 0),
        "results": sorted(rows, key=lambda item: item["case_id"]),
        "decision": "move_unverified_hard_cases_to_frontier_until_reference_repair_is_verified",
        "benchmark_policy": {
            "frontier_unresolved_counts_in_solvable_scoring": False,
            "frontier_unresolved_can_track_boundary": True,
            "near_miss_queue_requires_omc_verified_reference_before_hard_layer": True,
        },
        "next_actions": [
            "keep_6_verified_positive_cases_in_hard_solvable_pool",
            "move_8_unresolved_cases_to_frontier_layer",
            "try_deeper_manual_reference_repair_for_near_miss_case_only",
            "rebuild_split_and_closeout_after_frontier_demotion",
        ],
    }


def write_hard_positive_resolution_plan_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "frontier_unresolved_case_ids.txt").write_text(
        "\n".join(summary["frontier_unresolved_case_ids"]) + ("\n" if summary["frontier_unresolved_case_ids"] else ""),
        encoding="utf-8",
    )


def run_hard_positive_resolution_plan(
    *,
    workbench_path: Path = DEFAULT_WORKBENCH,
    attempts_path: Path = DEFAULT_ATTEMPTS,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_hard_positive_resolution_plan(
        workbench_summary=load_json(workbench_path),
        attempts_summary=load_json(attempts_path),
    )
    write_hard_positive_resolution_plan_outputs(out_dir=out_dir, summary=summary)
    return summary
