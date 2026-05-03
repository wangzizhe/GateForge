from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_json


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SPEC = REPO_ROOT / "artifacts" / "benchmark_v1_spec_v0_51_0" / "summary.json"
DEFAULT_RELAYER = REPO_ROOT / "artifacts" / "benchmark_v1_relayer_v0_52_0" / "summary.json"
DEFAULT_SOLVABILITY = REPO_ROOT / "artifacts" / "benchmark_positive_solvability_v0_53_0" / "summary.json"
DEFAULT_MEDIUM = REPO_ROOT / "artifacts" / "medium_candidate_admission_v0_55_0" / "summary.json"
DEFAULT_SPLIT = REPO_ROOT / "artifacts" / "benchmark_split_plan_v0_56_0" / "summary.json"
DEFAULT_BUNDLE = REPO_ROOT / "artifacts" / "benchmark_external_bundle_v0_57_0" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "benchmark_v1_closeout_v0_58_0"


def build_benchmark_v1_closeout(
    *,
    spec_summary: dict[str, Any],
    relayer_summary: dict[str, Any],
    solvability_summary: dict[str, Any],
    medium_summary: dict[str, Any],
    split_summary: dict[str, Any],
    bundle_summary: dict[str, Any],
    version: str = "v0.58.0",
) -> dict[str, Any]:
    layer_counts = split_summary.get("layer_counts") if isinstance(split_summary.get("layer_counts"), dict) else {}
    blockers: list[str] = []
    if spec_summary.get("status") != "PASS":
        blockers.append("benchmark_spec_not_ready")
    if int(layer_counts.get("medium") or 0) == 0:
        blockers.append("medium_layer_missing")
    if int(layer_counts.get("hard") or 0) == 0:
        blockers.append("hard_layer_missing")
    if int(solvability_summary.get("missing_positive_source_count") or 0) > 0:
        blockers.append("hard_positive_solvability_incomplete")
    if split_summary.get("readiness_status") != "benchmark_split_ready":
        blockers.append("split_plan_provisional")
    if bundle_summary.get("status") != "PASS":
        blockers.append("external_bundle_not_ready")
    freeze_ready = not blockers
    return {
        "version": version,
        "analysis_scope": "benchmark_v1_closeout",
        "status": "PASS" if freeze_ready else "REVIEW",
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "artifact_complete": True,
        "readiness_status": "benchmark_v1_freeze_ready" if freeze_ready else "benchmark_v1_not_freeze_ready",
        "freeze_ready": freeze_ready,
        "blockers": sorted(set(blockers)),
        "layer_counts": layer_counts,
        "medium_admitted_count": int(medium_summary.get("admitted_count") or 0),
        "external_bundle_task_count": int(bundle_summary.get("task_count") or 0),
        "hard_positive_missing_count": int(solvability_summary.get("missing_positive_source_count") or 0),
        "decision": (
            "freeze_benchmark_v1"
            if freeze_ready
            else "continue_positive_solvability_and_sanity_completion_before_freeze"
        ),
        "usable_now": {
            "medium_candidate_review": int(medium_summary.get("admitted_count") or 0) > 0,
            "external_agent_pilot_bundle": bundle_summary.get("status") == "PASS",
            "hard_boundary_tracking": int(layer_counts.get("hard") or 0) > 0,
            "full_solvable_benchmark_scoring": freeze_ready,
            "training_data_release": False,
        },
        "next_actions": [
            "fill_positive_solvability_for_hard_pack",
            "add_small_sanity_pack",
            "rerun_medium_holdout_under_current_provider",
            "freeze_benchmark_v1_after_blockers_clear",
        ],
    }


def write_benchmark_v1_closeout_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_benchmark_v1_closeout(
    *,
    spec_path: Path = DEFAULT_SPEC,
    relayer_path: Path = DEFAULT_RELAYER,
    solvability_path: Path = DEFAULT_SOLVABILITY,
    medium_path: Path = DEFAULT_MEDIUM,
    split_path: Path = DEFAULT_SPLIT,
    bundle_path: Path = DEFAULT_BUNDLE,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_benchmark_v1_closeout(
        spec_summary=load_json(spec_path),
        relayer_summary=load_json(relayer_path),
        solvability_summary=load_json(solvability_path),
        medium_summary=load_json(medium_path),
        split_summary=load_json(split_path),
        bundle_summary=load_json(bundle_path),
    )
    write_benchmark_v1_closeout_outputs(out_dir=out_dir, summary=summary)
    return summary
