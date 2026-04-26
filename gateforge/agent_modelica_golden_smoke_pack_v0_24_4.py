from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from gateforge.agent_modelica_contract_validator_v0_23_5 import (
    validate_seed_registry_row,
)
from gateforge.agent_modelica_oracle_contract_v0_23_3 import validate_oracle_event
from gateforge.agent_modelica_provider_noise_classifier_v0_24_2 import build_noise_rows
from gateforge.agent_modelica_runner_artifact_contract_v0_23_4 import validate_artifact_manifest
from gateforge.agent_modelica_trajectory_schema_v0_23_2 import validate_normalized_trajectory


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "golden_smoke_pack_v0_24_4"


def build_smoke_seed_rows() -> list[dict[str, Any]]:
    base = {
        "source_model": "SmokeModel",
        "mutation_family": "smoke_family",
        "mutation_intent": "smoke_fixture",
        "failure_type": "SMOKE",
        "source_complexity_class": "small",
        "omc_admission_status": "fixture",
        "live_screening_status": "fixture",
        "public_status": "public_fixture",
        "artifact_references": ["artifacts/golden_smoke_pack_v0_24_4/summary.json"],
        "routing_allowed": False,
    }
    rows = []
    for seed_id, policy, repeatability_class in (
        ("smoke_pass", "benchmark_positive_candidate", "stable_true_multi"),
        ("smoke_fail", "hard_negative_candidate", "stable_dead_end"),
        ("smoke_provider_noise", "research_unstable_candidate", "provider_noisy"),
        ("smoke_infra_noise", "research_unstable_candidate", "infra_noisy"),
    ):
        row = dict(base)
        row.update(
            {
                "seed_id": seed_id,
                "candidate_id": seed_id,
                "repeatability_class": repeatability_class,
                "registry_policy": policy,
                "observation_count": 1,
                "true_multi_observation_count": 1 if seed_id == "smoke_pass" else 0,
                "repair_round_counts": [2] if seed_id == "smoke_pass" else [0],
                "observed_quality": "multi_turn_useful" if seed_id == "smoke_pass" else "fixture_non_success",
            }
        )
        rows.append(row)
    return rows


def build_smoke_trajectories() -> list[dict[str, Any]]:
    return [
        {
            "schema_version": "trajectory_schema_v1",
            "run_id": "smoke_run",
            "case_id": "smoke_pass",
            "candidate_id": "smoke_pass",
            "model_profile": "smoke_fixture",
            "mutation_family": "smoke_family",
            "source_complexity_class": "small",
            "executor_attempt_count": 3,
            "repair_round_count": 2,
            "validation_round_count": 1,
            "feedback_sequence": ["model_check_error", "model_check_error", "none"],
            "final_verdict": "PASS",
            "termination": "success",
            "legacy_sample_quality": "multi_turn_useful",
            "trajectory_class": "multi_turn_useful",
            "true_multi_turn": True,
            "provider_failure": False,
            "oracle_failure": False,
            "raw_output_ref": None,
            "patch_application_status": "fixture",
            "budget_metadata": {"max_rounds": 4, "timeout_sec": 180},
            "source_artifact": "golden_smoke_fixture",
        },
        {
            "schema_version": "trajectory_schema_v1",
            "run_id": "smoke_run",
            "case_id": "smoke_fail",
            "candidate_id": "smoke_fail",
            "model_profile": "smoke_fixture",
            "mutation_family": "smoke_family",
            "source_complexity_class": "small",
            "executor_attempt_count": 4,
            "repair_round_count": 3,
            "validation_round_count": 1,
            "feedback_sequence": ["model_check_error", "model_check_error", "model_check_error"],
            "final_verdict": "FAILED",
            "termination": "max_rounds",
            "legacy_sample_quality": "dead_end_hard",
            "trajectory_class": "multi_turn_failed_or_dead_end",
            "true_multi_turn": False,
            "provider_failure": False,
            "oracle_failure": False,
            "raw_output_ref": None,
            "patch_application_status": "fixture",
            "budget_metadata": {"max_rounds": 4, "timeout_sec": 180},
            "source_artifact": "golden_smoke_fixture",
        },
        {
            "schema_version": "trajectory_schema_v1",
            "run_id": "smoke_run",
            "case_id": "smoke_provider_noise",
            "candidate_id": "smoke_provider_noise",
            "model_profile": "smoke_fixture",
            "mutation_family": "smoke_family",
            "source_complexity_class": "small",
            "executor_attempt_count": 1,
            "repair_round_count": 0,
            "validation_round_count": 0,
            "feedback_sequence": ["503 service unavailable"],
            "final_verdict": "PROVIDER_ERROR",
            "termination": "provider_503",
            "legacy_sample_quality": "provider_noise",
            "trajectory_class": "not_multi_turn",
            "true_multi_turn": False,
            "provider_failure": True,
            "oracle_failure": False,
            "raw_output_ref": None,
            "patch_application_status": "not_executed",
            "budget_metadata": {"max_rounds": 4, "timeout_sec": 180},
            "source_artifact": "golden_smoke_fixture",
        },
        {
            "schema_version": "trajectory_schema_v1",
            "run_id": "smoke_run",
            "case_id": "smoke_infra_noise",
            "candidate_id": "smoke_infra_noise",
            "model_profile": "smoke_fixture",
            "mutation_family": "smoke_family",
            "source_complexity_class": "small",
            "executor_attempt_count": 1,
            "repair_round_count": 0,
            "validation_round_count": 0,
            "feedback_sequence": ["Class Modelica not found in scope"],
            "final_verdict": "INFRA_ERROR",
            "termination": "infra_msl_load_error",
            "legacy_sample_quality": "infra_noise",
            "trajectory_class": "not_multi_turn",
            "true_multi_turn": False,
            "provider_failure": False,
            "oracle_failure": True,
            "raw_output_ref": None,
            "patch_application_status": "not_executed",
            "budget_metadata": {"max_rounds": 4, "timeout_sec": 180},
            "source_artifact": "golden_smoke_fixture",
        },
    ]


def build_smoke_oracle_events(trajectories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in trajectories:
        for index, feedback in enumerate(row["feedback_sequence"], start=1):
            status = "model_check_pass" if feedback == "none" else "model_check_error"
            if row.get("provider_failure"):
                status = "provider_error"
            if row.get("oracle_failure"):
                status = "infra_error"
            events.append(
                {
                    "contract_version": "oracle_contract_v1",
                    "run_id": row["run_id"],
                    "case_id": row["case_id"],
                    "candidate_id": row["candidate_id"],
                    "oracle_type": "model_check",
                    "round_index": index,
                    "status": status,
                    "raw_feedback": str(feedback),
                    "repair_hint_allowed": False,
                    "deterministic_repair_allowed": False,
                    "source_trajectory_class": row["trajectory_class"],
                }
            )
    return events


def build_smoke_manifest(out_dir: Path) -> dict[str, Any]:
    artifact_dir = str(out_dir.relative_to(REPO_ROOT)) if out_dir.is_relative_to(REPO_ROOT) else out_dir.name
    return {
        "contract_version": "runner_artifact_contract_v1",
        "run_version": "v0.24.4",
        "artifact_dir": artifact_dir,
        "producer_script": "scripts/build_golden_smoke_pack_v0_24_4.py",
        "expected_files": [
            "seed_registry.jsonl",
            "normalized_trajectories.jsonl",
            "oracle_events.jsonl",
            "noise_rows.jsonl",
            "manifest.json",
            "summary.json",
        ],
        "present_files": [
            "seed_registry.jsonl",
            "normalized_trajectories.jsonl",
            "oracle_events.jsonl",
            "noise_rows.jsonl",
            "manifest.json",
            "summary.json",
        ],
        "missing_files": [],
        "summary_status": "PASS",
        "environment_metadata": {"requires_private_assets": False, "repo_root_recorded": "relative_only"},
        "provider_metadata": {"provider": "fixture", "model_profile": "smoke_fixture"},
        "budget_metadata": {"repeat_count": 1, "max_rounds": 4, "timeout_sec": 180, "live_execution": False},
    }


def build_golden_smoke_pack(*, out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    seed_rows = build_smoke_seed_rows()
    trajectories = build_smoke_trajectories()
    oracle_events = build_smoke_oracle_events(trajectories)
    noise_rows = build_noise_rows(trajectories, source_artifact="artifacts/golden_smoke_pack_v0_24_4/normalized_trajectories.jsonl")
    manifest = build_smoke_manifest(out_dir)

    validation_errors: list[dict[str, Any]] = []
    for index, row in enumerate(seed_rows):
        if errors := validate_seed_registry_row(row):
            validation_errors.append({"dataset": "seed_registry", "row_index": index, "errors": errors})
    for index, row in enumerate(trajectories):
        if errors := validate_normalized_trajectory(row):
            validation_errors.append({"dataset": "trajectories", "row_index": index, "errors": errors})
    for index, row in enumerate(oracle_events):
        if errors := validate_oracle_event(row):
            validation_errors.append({"dataset": "oracle_events", "row_index": index, "errors": errors})
    if errors := validate_artifact_manifest(manifest):
        validation_errors.append({"dataset": "manifest", "row_index": 0, "errors": errors})

    noise_counts = Counter(row["noise_class"] for row in noise_rows)
    required_noise = {"llm_success", "llm_or_task_failure", "provider_failure", "infra_or_oracle_failure"}
    missing_noise_classes = sorted(required_noise - set(noise_counts))
    status = "PASS" if not validation_errors and not missing_noise_classes else "REVIEW"
    summary = {
        "version": "v0.24.4",
        "status": status,
        "analysis_scope": "golden_smoke_pack",
        "seed_count": len(seed_rows),
        "trajectory_count": len(trajectories),
        "oracle_event_count": len(oracle_events),
        "noise_class_counts": dict(sorted(noise_counts.items())),
        "missing_required_noise_classes": missing_noise_classes,
        "validation_error_count": len(validation_errors),
        "private_asset_required": False,
        "discipline": {
            "executor_changes": "none",
            "deterministic_repair_added": False,
            "fixture_only": True,
            "ci_safe": True,
        },
        "conclusion": (
            "golden_smoke_pack_ready_for_replay_harness"
            if status == "PASS"
            else "golden_smoke_pack_needs_review"
        ),
    }
    write_outputs(
        out_dir=out_dir,
        seed_rows=seed_rows,
        trajectories=trajectories,
        oracle_events=oracle_events,
        noise_rows=noise_rows,
        manifest=manifest,
        validation_errors=validation_errors,
        summary=summary,
    )
    return summary


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def write_outputs(
    *,
    out_dir: Path,
    seed_rows: list[dict[str, Any]],
    trajectories: list[dict[str, Any]],
    oracle_events: list[dict[str, Any]],
    noise_rows: list[dict[str, Any]],
    manifest: dict[str, Any],
    validation_errors: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out_dir / "seed_registry.jsonl", seed_rows)
    _write_jsonl(out_dir / "normalized_trajectories.jsonl", trajectories)
    _write_jsonl(out_dir / "oracle_events.jsonl", oracle_events)
    _write_jsonl(out_dir / "noise_rows.jsonl", noise_rows)
    _write_jsonl(out_dir / "validation_errors.jsonl", validation_errors)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
