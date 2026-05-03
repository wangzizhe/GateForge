from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_json


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RELAYER = REPO_ROOT / "artifacts" / "benchmark_v1_relayer_v0_52_0" / "summary.json"
DEFAULT_MEDIUM = REPO_ROOT / "artifacts" / "medium_candidate_admission_v0_55_0" / "summary.json"
DEFAULT_POSITIVE = REPO_ROOT / "artifacts" / "positive_source_harvest_v0_59_0" / "summary.json"
DEFAULT_RESOLUTION = REPO_ROOT / "artifacts" / "hard_positive_resolution_plan_v0_60_2" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "benchmark_split_rebuild_v0_60_3"


def _split_half(case_ids: list[str]) -> tuple[list[str], list[str]]:
    ordered = sorted(set(case_ids))
    midpoint = len(ordered) // 2
    return ordered[:midpoint], ordered[midpoint:]


def build_benchmark_split_rebuild(
    *,
    relayer_summary: dict[str, Any],
    medium_summary: dict[str, Any],
    positive_summary: dict[str, Any],
    resolution_summary: dict[str, Any],
    version: str = "v0.60.3",
) -> dict[str, Any]:
    layer_case_ids = relayer_summary.get("layer_case_ids") if isinstance(relayer_summary.get("layer_case_ids"), dict) else {}
    easy_cases = sorted(str(case_id) for case_id in layer_case_ids.get("easy", []) or [])
    medium_cases = sorted(str(case_id) for case_id in medium_summary.get("admitted_case_ids") or [])
    hard_solvable = sorted(str(case_id) for case_id in positive_summary.get("positive_source_case_ids") or [])
    near_miss = sorted(str(case_id) for case_id in resolution_summary.get("near_miss_reference_queue_case_ids") or [])
    frontier = sorted(str(case_id) for case_id in resolution_summary.get("frontier_unresolved_case_ids") or [])

    easy_dev, easy_holdout = _split_half(easy_cases)
    medium_dev, medium_holdout = _split_half(medium_cases)
    hard_dev, hard_holdout = _split_half(hard_solvable)
    dev = sorted(easy_dev + medium_dev + hard_dev)
    holdout = sorted(easy_holdout + medium_holdout + hard_holdout)
    overlaps = sorted(set(dev) & set(holdout))
    blockers: list[str] = []
    if not easy_cases:
        blockers.append("missing_easy_layer")
    if not medium_cases:
        blockers.append("missing_medium_layer")
    if not hard_solvable:
        blockers.append("missing_hard_solvable_layer")
    if overlaps:
        blockers.append("split_overlap_detected")
    readiness_status = "benchmark_split_ready_for_solvable_scoring" if not blockers else "benchmark_split_rebuild_incomplete"
    return {
        "version": version,
        "analysis_scope": "benchmark_split_rebuild",
        "status": "PASS" if not blockers else "REVIEW",
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "artifact_complete": True,
        "readiness_status": readiness_status,
        "split_case_ids": {
            "train_candidate": [],
            "dev": dev,
            "holdout": holdout,
            "frontier": frontier,
            "near_miss_reference_queue": near_miss,
        },
        "split_counts": {
            "train_candidate": 0,
            "dev": len(dev),
            "holdout": len(holdout),
            "frontier": len(frontier),
            "near_miss_reference_queue": len(near_miss),
        },
        "layer_counts": {
            "easy": len(easy_cases),
            "medium": len(medium_cases),
            "hard_solvable": len(hard_solvable),
            "frontier": len(frontier),
            "near_miss_reference_queue": len(near_miss),
        },
        "blockers": blockers,
        "policy": {
            "frontier_counts_in_solvable_scoring": False,
            "near_miss_counts_in_solvable_scoring": False,
            "holdout_may_drive_agent_tuning": False,
            "train_candidate_empty_until_label_gate": True,
        },
    }


def write_benchmark_split_rebuild_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for split, case_ids in summary["split_case_ids"].items():
        (out_dir / f"{split}_case_ids.txt").write_text("\n".join(case_ids) + ("\n" if case_ids else ""), encoding="utf-8")


def run_benchmark_split_rebuild(
    *,
    relayer_path: Path = DEFAULT_RELAYER,
    medium_path: Path = DEFAULT_MEDIUM,
    positive_path: Path = DEFAULT_POSITIVE,
    resolution_path: Path = DEFAULT_RESOLUTION,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_benchmark_split_rebuild(
        relayer_summary=load_json(relayer_path),
        medium_summary=load_json(medium_path),
        positive_summary=load_json(positive_path),
        resolution_summary=load_json(resolution_path),
    )
    write_benchmark_split_rebuild_outputs(out_dir=out_dir, summary=summary)
    return summary
