from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "benchmark_v1_spec_v0_51_0"

DIFFICULTY_LAYERS: tuple[dict[str, Any], ...] = (
    {
        "layer": "sanity",
        "purpose": "verify_harness_and_basic_modelica_tooling",
        "target_pass_rate_band": [0.8, 1.0],
        "primary_comparison_weight": 0.0,
        "allows_all_agents_pass": True,
        "allows_all_agents_fail": False,
    },
    {
        "layer": "easy",
        "purpose": "detect_basic_agent_regressions",
        "target_pass_rate_band": [0.6, 0.9],
        "primary_comparison_weight": 0.1,
        "allows_all_agents_pass": True,
        "allows_all_agents_fail": False,
    },
    {
        "layer": "medium",
        "purpose": "separate_agent_capability_under_workflow_realistic_failures",
        "target_pass_rate_band": [0.2, 0.7],
        "primary_comparison_weight": 0.55,
        "allows_all_agents_pass": False,
        "allows_all_agents_fail": False,
    },
    {
        "layer": "hard",
        "purpose": "measure_known_hard_negative_boundary_progress",
        "target_pass_rate_band": [0.05, 0.35],
        "primary_comparison_weight": 0.3,
        "allows_all_agents_pass": False,
        "allows_all_agents_fail": True,
    },
    {
        "layer": "frontier",
        "purpose": "track_unsolved_modelica_semantic_boundary",
        "target_pass_rate_band": [0.0, 0.15],
        "primary_comparison_weight": 0.05,
        "allows_all_agents_pass": False,
        "allows_all_agents_fail": True,
    },
)

REQUIRED_TASK_FIELDS = (
    "case_id",
    "title",
    "visible_task_description",
    "constraints",
    "initial_model",
    "difficulty_layer",
    "source_backed",
    "model_check_first",
    "blind_lint_status",
    "admission_status",
    "dataset_split",
)

FORBIDDEN_PROMPT_FIELDS = (
    "hidden_oracle",
    "reference_repair",
    "reference_diff",
    "known_hard_for",
    "difficulty_bucket",
    "gateforge_internal_artifacts",
)

REQUIRED_RESULT_FIELDS = (
    "case_id",
    "agent_name",
    "llm_model",
    "difficulty_layer",
    "dataset_split",
    "final_verdict",
    "submitted",
    "provider_status",
    "omc_invocation_count",
    "failure_category",
)

FINAL_VERDICTS = (
    "PASS",
    "FAIL",
    "PROVIDER_ERROR",
    "INVALID_TASK",
    "TIMEOUT",
    "UNSUPPORTED_TOOL_USE",
)

FAILURE_CATEGORIES = (
    "none",
    "model_check_error",
    "simulation_error",
    "no_final_submission",
    "candidate_generation_failure",
    "provider_error",
    "invalid_task",
    "timeout",
    "unsupported_tool_use",
    "unknown",
)


def layer_names() -> list[str]:
    return [str(layer["layer"]) for layer in DIFFICULTY_LAYERS]


def validate_task_record(task: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_TASK_FIELDS:
        if field not in task:
            errors.append(f"missing:{field}")
    layer = str(task.get("difficulty_layer") or "")
    if layer and layer not in layer_names():
        errors.append(f"invalid_difficulty_layer:{layer}")
    split = str(task.get("dataset_split") or "")
    if split and split not in {"train_candidate", "dev", "holdout", "pilot"}:
        errors.append(f"invalid_dataset_split:{split}")
    if task.get("blind_lint_status") not in {None, "PASS"}:
        errors.append("blind_lint_status_must_pass")
    for field in FORBIDDEN_PROMPT_FIELDS:
        if field in task:
            errors.append(f"prompt_leak_field:{field}")
    return errors


def classify_result_for_scoring(result: dict[str, Any]) -> dict[str, Any]:
    verdict = str(result.get("final_verdict") or "")
    provider_status = str(result.get("provider_status") or "")
    if verdict == "PASS":
        score_bucket = "success"
        counts_as_capability_failure = False
    elif verdict in {"PROVIDER_ERROR", "UNSUPPORTED_TOOL_USE"} or provider_status in {
        "provider_unstable",
        "provider_blocked",
        "provider_unsupported_tool_use",
    }:
        score_bucket = "provider_excluded"
        counts_as_capability_failure = False
    elif verdict == "INVALID_TASK":
        score_bucket = "task_excluded"
        counts_as_capability_failure = False
    elif verdict == "TIMEOUT":
        score_bucket = "budget_failure"
        counts_as_capability_failure = True
    else:
        score_bucket = "capability_failure"
        counts_as_capability_failure = True
    return {
        "case_id": str(result.get("case_id") or ""),
        "final_verdict": verdict,
        "score_bucket": score_bucket,
        "counts_as_capability_failure": counts_as_capability_failure,
        "submitted": bool(result.get("submitted")),
    }


def validate_result_record(result: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_RESULT_FIELDS:
        if field not in result:
            errors.append(f"missing:{field}")
    verdict = str(result.get("final_verdict") or "")
    if verdict and verdict not in FINAL_VERDICTS:
        errors.append(f"invalid_final_verdict:{verdict}")
    category = str(result.get("failure_category") or "")
    if category and category not in FAILURE_CATEGORIES:
        errors.append(f"invalid_failure_category:{category}")
    layer = str(result.get("difficulty_layer") or "")
    if layer and layer not in layer_names():
        errors.append(f"invalid_difficulty_layer:{layer}")
    return errors


def build_benchmark_v1_spec(*, version: str = "v0.51.0") -> dict[str, Any]:
    primary_layers = [
        layer["layer"]
        for layer in DIFFICULTY_LAYERS
        if float(layer["primary_comparison_weight"]) > 0.0
    ]
    return {
        "version": version,
        "analysis_scope": "benchmark_v1_spec",
        "status": "PASS",
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "artifact_complete": True,
        "readiness_status": "benchmark_spec_ready",
        "difficulty_layers": list(DIFFICULTY_LAYERS),
        "primary_comparison_layers": primary_layers,
        "required_task_fields": list(REQUIRED_TASK_FIELDS),
        "forbidden_prompt_fields": list(FORBIDDEN_PROMPT_FIELDS),
        "required_result_fields": list(REQUIRED_RESULT_FIELDS),
        "final_verdicts": list(FINAL_VERDICTS),
        "failure_categories": list(FAILURE_CATEGORIES),
        "comparison_contract": {
            "same_case_pairing_required": True,
            "medium_layer_must_exist": True,
            "hard_pack_must_not_be_only_benchmark": True,
            "provider_errors_excluded_from_capability_failure": True,
            "invalid_tasks_excluded_from_capability_failure": True,
            "holdout_must_not_be_used_for_training_or_prompt_tuning": True,
        },
        "dataset_split_contract": {
            "train_candidate": "may_be_used_for_training_or_policy_development_after_positive_labels_exist",
            "dev": "may_be_used_for_agent_iteration_and_prompt_development",
            "holdout": "reserved_for_final_comparison_and_must_not_drive_agent_tuning",
            "pilot": "used_for_protocol_smoke_or_manual_external_agent_intake",
        },
    }


def write_benchmark_v1_spec_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_benchmark_v1_spec(*, out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    summary = build_benchmark_v1_spec()
    write_benchmark_v1_spec_outputs(out_dir=out_dir, summary=summary)
    return summary
