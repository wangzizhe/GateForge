from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_json


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RELAYER = REPO_ROOT / "artifacts" / "benchmark_v1_relayer_v0_52_0" / "summary.json"
DEFAULT_MEDIUM_ADMISSION = REPO_ROOT / "artifacts" / "medium_candidate_admission_v0_55_0" / "summary.json"
DEFAULT_POSITIVE_SOLVABILITY = REPO_ROOT / "artifacts" / "benchmark_positive_solvability_v0_53_0" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "benchmark_split_plan_v0_56_0"


def _split_half(case_ids: list[str]) -> tuple[list[str], list[str]]:
    ordered = sorted(set(case_ids))
    midpoint = len(ordered) // 2
    return ordered[:midpoint], ordered[midpoint:]


def build_benchmark_split_plan(
    *,
    relayer_summary: dict[str, Any],
    medium_admission_summary: dict[str, Any],
    positive_solvability_summary: dict[str, Any],
    version: str = "v0.56.0",
) -> dict[str, Any]:
    layer_case_ids = relayer_summary.get("layer_case_ids") if isinstance(relayer_summary.get("layer_case_ids"), dict) else {}
    easy_cases = sorted(str(case_id) for case_id in layer_case_ids.get("easy", []) or [])
    hard_cases = sorted(str(case_id) for case_id in layer_case_ids.get("hard", []) or [])
    medium_cases = sorted(str(case_id) for case_id in medium_admission_summary.get("admitted_case_ids") or [])
    easy_dev, easy_holdout = _split_half(easy_cases)
    medium_dev, medium_holdout = _split_half(medium_cases)
    hard_dev, hard_holdout = _split_half(hard_cases)

    train_candidate: list[str] = []
    dev = sorted(easy_dev + medium_dev + hard_dev)
    holdout = sorted(easy_holdout + medium_holdout + hard_holdout)
    overlaps = sorted(set(train_candidate) & set(dev) | set(train_candidate) & set(holdout) | set(dev) & set(holdout))
    gaps: list[str] = []
    if not medium_cases:
        gaps.append("missing_medium_cases")
    if not easy_cases:
        gaps.append("missing_easy_cases")
    if not hard_cases:
        gaps.append("missing_hard_cases")
    if overlaps:
        gaps.append("split_overlap_detected")
    if int(positive_solvability_summary.get("missing_positive_source_count") or 0) > 0:
        gaps.append("hard_positive_solvability_incomplete")
    if not train_candidate:
        gaps.append("training_split_empty_until_positive_labels")
    readiness_status = "benchmark_split_provisional" if gaps else "benchmark_split_ready"
    return {
        "version": version,
        "analysis_scope": "benchmark_split_plan",
        "status": "REVIEW" if gaps else "PASS",
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "artifact_complete": True,
        "readiness_status": readiness_status,
        "split_case_ids": {
            "train_candidate": train_candidate,
            "dev": dev,
            "holdout": holdout,
        },
        "split_counts": {
            "train_candidate": len(train_candidate),
            "dev": len(dev),
            "holdout": len(holdout),
        },
        "layer_counts": {
            "easy": len(easy_cases),
            "medium": len(medium_cases),
            "hard": len(hard_cases),
        },
        "holdout_policy": {
            "may_drive_agent_tuning": False,
            "may_enter_training": False,
            "may_be_used_for_final_external_comparison": True,
            "hidden_oracle_prompt_visible": False,
        },
        "dev_policy": {
            "may_drive_agent_tuning": True,
            "may_enter_training": False,
            "intended_use": "benchmark_iteration_and_agent_debug",
        },
        "train_candidate_policy": {
            "requires_positive_labels_before_use": True,
            "negative_only_trajectories_are_not_repair_policy_training_data": True,
        },
        "gaps": gaps,
        "overlap_case_ids": overlaps,
        "next_actions": [
            "rerun_dev_and_holdout_medium_candidates_under_current_provider",
            "add_sanity_pack",
            "fill_positive_labels_before_training_split_is_populated",
        ],
    }


def write_benchmark_split_plan_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for split, case_ids in summary["split_case_ids"].items():
        (out_dir / f"{split}_case_ids.txt").write_text("\n".join(case_ids) + ("\n" if case_ids else ""), encoding="utf-8")


def run_benchmark_split_plan(
    *,
    relayer_path: Path = DEFAULT_RELAYER,
    medium_admission_path: Path = DEFAULT_MEDIUM_ADMISSION,
    positive_solvability_path: Path = DEFAULT_POSITIVE_SOLVABILITY,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_benchmark_split_plan(
        relayer_summary=load_json(relayer_path),
        medium_admission_summary=load_json(medium_admission_path),
        positive_solvability_summary=load_json(positive_solvability_path),
    )
    write_benchmark_split_plan_outputs(out_dir=out_dir, summary=summary)
    return summary
