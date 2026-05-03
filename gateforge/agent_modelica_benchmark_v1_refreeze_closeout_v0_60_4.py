from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_json


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SPLIT = REPO_ROOT / "artifacts" / "benchmark_split_rebuild_v0_60_3" / "summary.json"
DEFAULT_BUNDLE = REPO_ROOT / "artifacts" / "benchmark_external_bundle_v0_57_0" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "benchmark_v1_refreeze_closeout_v0_60_4"


def build_benchmark_v1_refreeze_closeout(
    *,
    split_summary: dict[str, Any],
    bundle_summary: dict[str, Any],
    version: str = "v0.60.4",
) -> dict[str, Any]:
    layer_counts = split_summary.get("layer_counts") if isinstance(split_summary.get("layer_counts"), dict) else {}
    blockers: list[str] = []
    if split_summary.get("status") != "PASS":
        blockers.append("split_rebuild_not_ready")
    if bundle_summary.get("status") != "PASS":
        blockers.append("external_bundle_not_ready")
    for layer in ("easy", "medium", "hard_solvable"):
        if int(layer_counts.get(layer) or 0) == 0:
            blockers.append(f"missing_{layer}_layer")
    freeze_ready = not blockers
    return {
        "version": version,
        "analysis_scope": "benchmark_v1_refreeze_closeout",
        "status": "PASS" if freeze_ready else "REVIEW",
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "artifact_complete": True,
        "readiness_status": "benchmark_v1_freeze_ready" if freeze_ready else "benchmark_v1_not_freeze_ready",
        "freeze_ready": freeze_ready,
        "blockers": blockers,
        "layer_counts": layer_counts,
        "split_counts": split_summary.get("split_counts") or {},
        "external_bundle_task_count": int(bundle_summary.get("task_count") or 0),
        "freeze_scope": {
            "solvable_scoring_layers": ["easy", "medium", "hard_solvable"],
            "frontier_layer_included_for_boundary_tracking": True,
            "frontier_counts_in_primary_score": False,
            "near_miss_counts_in_primary_score": False,
            "train_candidate_empty": True,
        },
        "decision": "freeze_benchmark_v1_solvable_scoring_substrate" if freeze_ready else "continue_blocker_resolution",
        "next_actions": [
            "regenerate_external_bundle_from_rebuilt_split",
            "run_current_provider_baseline_on_solvable_holdout",
            "only_after_that_run_external_agent_comparison",
        ],
    }


def write_benchmark_v1_refreeze_closeout_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_benchmark_v1_refreeze_closeout(
    *,
    split_path: Path = DEFAULT_SPLIT,
    bundle_path: Path = DEFAULT_BUNDLE,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_benchmark_v1_refreeze_closeout(
        split_summary=load_json(split_path),
        bundle_summary=load_json(bundle_path),
    )
    write_benchmark_v1_refreeze_closeout_outputs(out_dir=out_dir, summary=summary)
    return summary
