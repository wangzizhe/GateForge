from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from gateforge.agent_modelica_repeatability_protocol_v0_24_0 import (
    PROTOCOL_VERSION,
    build_candidate_rows,
    build_family_rows,
    load_jsonl,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SEED_REGISTRY_PATH = REPO_ROOT / "artifacts" / "seed_registry_v0_23_1" / "seed_registry.jsonl"
DEFAULT_TRAJECTORY_PATH = REPO_ROOT / "artifacts" / "trajectory_schema_v0_23_2" / "normalized_trajectories.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "unified_repeatability_runner_v0_24_1"
ARTIFACT_CONTRACT_VERSION = "runner_artifact_contract_v1"
RunnerExecutor = Callable[[dict[str, Any], Path], dict[str, Any]]


def select_seed_rows(
    seeds: list[dict[str, Any]],
    *,
    family: str | None = None,
    policy: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    selected = [
        row
        for row in seeds
        if (family is None or row.get("mutation_family") == family)
        and (policy is None or row.get("registry_policy") == policy)
    ]
    selected = sorted(selected, key=lambda row: str(row.get("seed_id") or row.get("candidate_id") or ""))
    if limit is not None:
        selected = selected[: max(0, int(limit))]
    return selected


def build_repeat_plan(
    seeds: list[dict[str, Any]],
    *,
    repeat_count: int,
    max_rounds: int,
    timeout_sec: int,
) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for repeat_index in range(1, max(0, int(repeat_count)) + 1):
        for seed in seeds:
            seed_id = str(seed.get("seed_id") or seed.get("candidate_id") or "")
            plan.append(
                {
                    "run_id": f"v0.24.1_repeat_{repeat_index:02d}",
                    "repeat_index": repeat_index,
                    "seed_id": seed_id,
                    "candidate_id": seed_id,
                    "mutation_family": str(seed.get("mutation_family") or "unknown"),
                    "source_model": str(seed.get("source_model") or "unknown"),
                    "max_rounds": int(max_rounds),
                    "timeout_sec": int(timeout_sec),
                    "routing_allowed": False,
                }
            )
    return plan


def dry_run_observation(plan_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "trajectory_schema_v1",
        "run_id": str(plan_row["run_id"]),
        "case_id": str(plan_row["candidate_id"]),
        "candidate_id": str(plan_row["candidate_id"]),
        "model_profile": "dry_run_no_model_call",
        "mutation_family": str(plan_row.get("mutation_family") or "unknown"),
        "source_complexity_class": "unknown",
        "executor_attempt_count": 0,
        "repair_round_count": 0,
        "validation_round_count": 0,
        "feedback_sequence": [],
        "final_verdict": "DRY_RUN",
        "termination": "dry_run",
        "legacy_sample_quality": "not_executed",
        "trajectory_class": "not_multi_turn",
        "true_multi_turn": False,
        "provider_failure": False,
        "oracle_failure": False,
        "raw_output_ref": None,
        "patch_application_status": "not_executed",
        "budget_metadata": {
            "max_rounds": int(plan_row["max_rounds"]),
            "timeout_sec": int(plan_row["timeout_sec"]),
        },
        "source_artifact": "generated_by_unified_repeatability_runner_dry_run",
    }


def normalize_executor_payload(plan_row: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    row = dict(payload)
    row.setdefault("schema_version", "trajectory_schema_v1")
    row.setdefault("run_id", str(plan_row["run_id"]))
    row.setdefault("case_id", str(plan_row["candidate_id"]))
    row.setdefault("candidate_id", str(plan_row["candidate_id"]))
    row.setdefault("mutation_family", str(plan_row.get("mutation_family") or "unknown"))
    row.setdefault("executor_attempt_count", 0)
    row.setdefault("repair_round_count", 0)
    row.setdefault("validation_round_count", 0)
    row.setdefault("feedback_sequence", [])
    row.setdefault("final_verdict", "UNKNOWN")
    row.setdefault("trajectory_class", "not_multi_turn")
    row.setdefault("true_multi_turn", row.get("trajectory_class") == "multi_turn_useful")
    row.setdefault("provider_failure", False)
    row.setdefault("oracle_failure", False)
    row.setdefault("budget_metadata", {"max_rounds": int(plan_row["max_rounds"]), "timeout_sec": int(plan_row["timeout_sec"])})
    return row


def build_manifest(
    *,
    out_dir: Path,
    repeat_count: int,
    max_rounds: int,
    timeout_sec: int,
    dry_run: bool,
) -> dict[str, Any]:
    artifact_dir = str(out_dir.relative_to(REPO_ROOT)) if out_dir.is_relative_to(REPO_ROOT) else str(out_dir)
    return {
        "contract_version": ARTIFACT_CONTRACT_VERSION,
        "run_version": "v0.24.1",
        "artifact_dir": artifact_dir,
        "producer_script": "scripts/run_unified_repeatability_v0_24_1.py",
        "expected_files": [
            "manifest.json",
            "repeat_plan.jsonl",
            "repeat_observations.jsonl",
            "candidate_repeatability.jsonl",
            "family_repeatability.jsonl",
            "summary.json",
        ],
        "present_files": [
            "manifest.json",
            "repeat_plan.jsonl",
            "repeat_observations.jsonl",
            "candidate_repeatability.jsonl",
            "family_repeatability.jsonl",
            "summary.json",
        ],
        "missing_files": [],
        "summary_status": "PENDING",
        "environment_metadata": {
            "repo_root_recorded": "relative_only",
            "requires_private_assets": False,
        },
        "provider_metadata": {
            "provider": "not_applicable_dry_run" if dry_run else "executor_supplied",
            "model_profile": "dry_run_no_model_call" if dry_run else "executor_supplied",
        },
        "budget_metadata": {
            "repeat_count": int(repeat_count),
            "max_rounds": int(max_rounds),
            "timeout_sec": int(timeout_sec),
            "live_execution": not dry_run,
        },
    }


def run_unified_repeatability(
    *,
    seed_registry_path: Path = DEFAULT_SEED_REGISTRY_PATH,
    reference_trajectory_path: Path = DEFAULT_TRAJECTORY_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
    family: str | None = None,
    policy: str | None = None,
    limit: int | None = None,
    repeat_count: int = 1,
    max_rounds: int = 8,
    timeout_sec: int = 420,
    dry_run: bool = True,
    executor: RunnerExecutor | None = None,
) -> dict[str, Any]:
    seeds = load_jsonl(seed_registry_path)
    selected_seeds = select_seed_rows(seeds, family=family, policy=policy, limit=limit)
    plan = build_repeat_plan(
        selected_seeds,
        repeat_count=repeat_count,
        max_rounds=max_rounds,
        timeout_sec=timeout_sec,
    )
    reference = load_jsonl(reference_trajectory_path)
    selected_ids = {str(row.get("seed_id") or row.get("candidate_id") or "") for row in selected_seeds}
    observations = [
        row for row in reference if str(row.get("candidate_id") or row.get("case_id") or "") in selected_ids
    ]

    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for plan_row in plan:
        raw_path = raw_dir / f"{plan_row['candidate_id']}__repeat_{plan_row['repeat_index']:02d}.json"
        if dry_run or executor is None:
            payload = dry_run_observation(plan_row)
        else:
            payload = normalize_executor_payload(plan_row, executor(plan_row, raw_path))
        raw_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        observations.append(payload)

    candidate_rows = build_candidate_rows(seeds=selected_seeds, trajectories=observations)
    family_rows = build_family_rows(candidate_rows)
    manifest = build_manifest(
        out_dir=out_dir,
        repeat_count=repeat_count,
        max_rounds=max_rounds,
        timeout_sec=timeout_sec,
        dry_run=dry_run or executor is None,
    )
    status = "PASS" if selected_seeds and plan else "REVIEW"
    summary = {
        "version": "v0.24.1",
        "status": status,
        "analysis_scope": "unified_repeatability_runner",
        "protocol_version": PROTOCOL_VERSION,
        "dry_run": dry_run or executor is None,
        "selected_seed_count": len(selected_seeds),
        "reference_observation_count": len(observations) - len(plan),
        "new_observation_count": len(plan),
        "total_observation_count": len(observations),
        "candidate_count": len(candidate_rows),
        "family_count": len(family_rows),
        "selection": {
            "family": family,
            "policy": policy,
            "limit": limit,
        },
        "budget_metadata": {
            "repeat_count": int(repeat_count),
            "max_rounds": int(max_rounds),
            "timeout_sec": int(timeout_sec),
        },
        "discipline": {
            "executor_changes": "none",
            "deterministic_repair_added": False,
            "routing_allowed": False,
            "default_mode": "dry_run_no_model_call",
        },
        "conclusion": (
            "unified_repeatability_runner_ready_for_provider_noise_classifier"
            if status == "PASS"
            else "unified_repeatability_runner_needs_review"
        ),
    }
    manifest["summary_status"] = status
    write_outputs(
        out_dir=out_dir,
        manifest=manifest,
        plan=plan,
        observations=observations,
        candidate_rows=candidate_rows,
        family_rows=family_rows,
        summary=summary,
    )
    return summary


def write_outputs(
    *,
    out_dir: Path,
    manifest: dict[str, Any],
    plan: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    family_rows: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "repeat_plan.jsonl").open("w", encoding="utf-8") as fh:
        for row in plan:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    with (out_dir / "repeat_observations.jsonl").open("w", encoding="utf-8") as fh:
        for row in observations:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    with (out_dir / "candidate_repeatability.jsonl").open("w", encoding="utf-8") as fh:
        for row in candidate_rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    with (out_dir / "family_repeatability.jsonl").open("w", encoding="utf-8") as fh:
        for row in family_rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
