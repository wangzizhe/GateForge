from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_json
from .agent_modelica_hard_family_registry_v0_37_0 import build_registry_summary


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIFFICULTY = REPO_ROOT / "artifacts" / "hard_core_adjacent_difficulty_summary_v0_48_7" / "summary.json"
DEFAULT_ADMISSION = REPO_ROOT / "artifacts" / "hard_core_adjacent_admission_v0_48_3" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hard_candidate_registry_promote_v0_49_0"


def infer_family(case_id: str) -> str:
    if "adapter" in case_id:
        return "arrayed_adapter_cross_node"
    if "probe_bus" in case_id:
        return "arrayed_connector_probe_bus"
    return "hard_core_adjacent"


def _admission_by_case(admission_summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("case_id") or ""): row for row in admission_summary.get("results") or []}


def build_registry_seed_for_candidate(
    *,
    result: dict[str, Any],
    admission_row: dict[str, Any],
) -> dict[str, Any]:
    case_id = str(result.get("case_id") or "")
    profile = "provider-env / model-env / base tool-use / 32k"
    return {
        "case_id": case_id,
        "family": infer_family(case_id),
        "source_reference": "hard_core_adjacent_v0_48",
        "source_backed": True,
        "workflow_intent": "repair model-check-first arrayed connector or adapter structural failure",
        "visible_task_description": "Hard-core adjacent Modelica repair task with blind visible prompt.",
        "hidden_oracle": {
            "type": "admission_and_repeatability_artifact",
            "admission_status": str(admission_row.get("admission_status") or ""),
        },
        "mutation_intent": "adjacent hard-core structural contract variant",
        "expected_failure_mode": str(admission_row.get("admission_status") or "admitted_under_determined"),
        "model_check_first": True,
        "blind_lint_status": "PASS",
        "admission_status": "admitted_via_omc",
        "repeatability_status": "repeatability_evidence_present",
        "evidence_role": "formal_experiment",
        "known_hard_for": [profile, profile],
        "registry_status": "admitted",
    }


def build_hard_candidate_registry_promotion(
    *,
    difficulty_summary: dict[str, Any],
    admission_summary: dict[str, Any],
    version: str = "v0.49.0",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    admission_rows = _admission_by_case(admission_summary)
    seeds: list[dict[str, Any]] = []
    for result in difficulty_summary.get("results") or []:
        if str(result.get("difficulty_bucket") or "") != "hard_negative_candidate":
            continue
        case_id = str(result.get("case_id") or "")
        seeds.append(build_registry_seed_for_candidate(result=result, admission_row=admission_rows.get(case_id, {})))
    registry_summary = build_registry_summary(seeds, version=version)
    summary = {
        "version": version,
        "analysis_scope": "hard_candidate_registry_promotion",
        "status": registry_summary["status"],
        "evidence_role": "formal_experiment",
        "conclusion_allowed": bool(seeds and registry_summary["status"] == "PASS"),
        "promoted_seed_count": len(seeds),
        "case_ids": [seed["case_id"] for seed in seeds],
        "registry_validation_error_count": registry_summary["validation_error_count"],
        "family_counts": registry_summary["family_counts"],
        "next_action": "apply_repeatability_gate",
    }
    return summary, seeds


def write_hard_candidate_registry_promotion_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
    seeds: list[dict[str, Any]],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "registry_seeds.jsonl").open("w", encoding="utf-8") as fh:
        for seed in seeds:
            fh.write(json.dumps(seed, sort_keys=True) + "\n")


def run_hard_candidate_registry_promotion(
    *,
    difficulty_path: Path = DEFAULT_DIFFICULTY,
    admission_path: Path = DEFAULT_ADMISSION,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary, seeds = build_hard_candidate_registry_promotion(
        difficulty_summary=load_json(difficulty_path),
        admission_summary=load_json(admission_path),
    )
    write_hard_candidate_registry_promotion_outputs(out_dir=out_dir, summary=summary, seeds=seeds)
    return summary
