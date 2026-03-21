from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_behavioral_contract_taskset_v1 import _normalize_behavioral_source_model_text, _rewrite_line_once
from .agent_modelica_multi_round_failure_taskset_v1 import _ratio
from .agent_modelica_source_blind_multistep_manifest_v1 import (
    ALLOWED_FAILURE_TYPES,
    SCHEMA_VERSION as MANIFEST_SCHEMA_VERSION,
    load_source_blind_multistep_manifest,
    validate_source_blind_multistep_manifest,
)
from .agent_modelica_unknown_library_taskset_v1 import (
    _assign_split,
    _build_source_meta,
    _default_md_path,
    _norm,
    _write_json,
    _write_text,
)
from .physics_contract_v0 import default_physics_contract_v0, evaluate_physics_contract_v0


SCHEMA_VERSION = "agent_modelica_source_blind_multistep_taskset_v1"
MULTISTEP_MARKER_PREFIX = "gateforge_source_blind_multistep_violation"
DEFAULT_REALISM_VERSION = "v3"
DEFAULT_FAILURE_TYPES = ALLOWED_FAILURE_TYPES
FAILURE_METADATA = {
    "stability_then_behavior": {
        "multi_step_family": "stability_then_behavior",
        "realism_version": "v3",
        "contract_metric_set": ["stability_margin", "behavior_error", "neighbor_case_error"],
        "expected_failure_sequence": ["stability_margin_miss", "behavior_contract_miss"],
        "stage_2_branches": [
            {"branch": "behavior_timing_branch", "fail_bucket": "behavior_contract_miss", "trap": False},
            {"branch": "neighbor_overfit_trap", "fail_bucket": "single_case_only", "trap": True},
        ],
        "preferred_stage_2_branch": "behavior_timing_branch",
        "trap_stage_2_branch": "neighbor_overfit_trap",
        "expected_rounds_min": 2,
        "scenario_matrix": [
            {"scenario_id": "nominal", "kind": "primary", "mode": "stability_gate"},
            {"scenario_id": "neighbor_a", "kind": "neighbor", "mode": "behavior_followup_a"},
            {"scenario_id": "neighbor_b", "kind": "neighbor", "mode": "behavior_followup_b"},
        ],
        "baseline_metrics": {"stability_margin": 0.05, "behavior_error": 0.02, "neighbor_case_error": 0.03},
        "candidate_metrics": {"stability_margin": 0.28, "behavior_error": 0.19, "neighbor_case_error": 0.15},
        "invariants": [
            {"type": "range", "metric": "stability_margin", "max": 0.12},
            {"type": "range", "metric": "behavior_error", "max": 0.08},
        ],
        "contract_fail_bucket": "stability_margin_miss",
    },
    "behavior_then_robustness": {
        "multi_step_family": "behavior_then_robustness",
        "realism_version": "v3",
        "contract_metric_set": ["steady_state_error", "neighbor_case_error", "robustness_error"],
        "expected_failure_sequence": ["behavior_contract_miss", "single_case_only"],
        "stage_2_branches": [
            {"branch": "neighbor_robustness_branch", "fail_bucket": "single_case_only", "trap": False},
            {"branch": "nominal_overfit_trap", "fail_bucket": "behavior_contract_miss", "trap": True},
        ],
        "preferred_stage_2_branch": "neighbor_robustness_branch",
        "trap_stage_2_branch": "nominal_overfit_trap",
        "expected_rounds_min": 2,
        "scenario_matrix": [
            {"scenario_id": "nominal", "kind": "primary", "mode": "behavior_gate"},
            {"scenario_id": "neighbor_a", "kind": "neighbor", "mode": "robustness_followup_a"},
            {"scenario_id": "neighbor_b", "kind": "neighbor", "mode": "robustness_followup_b"},
        ],
        "baseline_metrics": {"steady_state_error": 0.03, "neighbor_case_error": 0.03, "robustness_error": 0.04},
        "candidate_metrics": {"steady_state_error": 0.17, "neighbor_case_error": 0.21, "robustness_error": 0.18},
        "invariants": [
            {"type": "range", "metric": "steady_state_error", "max": 0.08},
            {"type": "range", "metric": "neighbor_case_error", "max": 0.09},
        ],
        "contract_fail_bucket": "single_case_only",
    },
    "switch_then_recovery": {
        "multi_step_family": "switch_then_recovery",
        "realism_version": "v3",
        "contract_metric_set": ["scenario_switch_error", "post_switch_recovery", "neighbor_case_error"],
        "expected_failure_sequence": ["scenario_switch_miss", "post_switch_recovery_miss"],
        "stage_2_branches": [
            {"branch": "post_switch_recovery_branch", "fail_bucket": "post_switch_recovery_miss", "trap": False},
            {"branch": "recovery_overfit_trap", "fail_bucket": "single_case_only", "trap": True},
        ],
        "preferred_stage_2_branch": "post_switch_recovery_branch",
        "trap_stage_2_branch": "recovery_overfit_trap",
        "expected_rounds_min": 3,
        "scenario_matrix": [
            {"scenario_id": "nominal", "kind": "primary", "mode": "switch_gate"},
            {"scenario_id": "neighbor_a", "kind": "neighbor", "mode": "recovery_followup_a"},
            {"scenario_id": "neighbor_b", "kind": "neighbor", "mode": "recovery_followup_b"},
        ],
        "baseline_metrics": {"scenario_switch_error": 0.04, "post_switch_recovery": 0.9, "neighbor_case_error": 0.03},
        "candidate_metrics": {"scenario_switch_error": 0.23, "post_switch_recovery": 2.7, "neighbor_case_error": 0.17},
        "invariants": [
            {"type": "range", "metric": "scenario_switch_error", "max": 0.08},
            {"type": "range", "metric": "post_switch_recovery", "max": 1.6},
        ],
        "contract_fail_bucket": "scenario_switch_miss",
    },
}

V4_ALLOWED_MODELS_BY_FAILURE = {
    "stability_then_behavior": {"planta", "plant_a", "plantb", "plant_b"},
    "behavior_then_robustness": {"switcha", "switch_a", "switchb", "switch_b"},
    "switch_then_recovery": {"hybrida", "hybrid_a", "hybridb", "hybrid_b"},
}
V4_LLM_FORCING_PROFILES = {
    "stability_then_behavior": "coupled_stage_unlock_then_behavior_branch",
    "behavior_then_robustness": "branch_ambiguity_then_neighbor_robustness",
    "switch_then_recovery": "trap_escape_then_recovery_resolution",
}
V4_LLM_TRIGGER_REASONS = {
    "stability_then_behavior": "same_stage_2_branch_stall",
    "behavior_then_robustness": "branch_diagnosis_unknown_or_candidate_pool_exhausted",
    "switch_then_recovery": "trap_escape_no_progress",
}


def _build_contract(invariants: list[dict]) -> dict:
    contract = default_physics_contract_v0()
    contract["physical_invariants"] = [dict(item) for item in invariants if isinstance(item, dict)]
    return contract


def _task_contract_details(failure_type: str) -> tuple[dict, dict, dict]:
    meta = FAILURE_METADATA[failure_type]
    baseline_metrics = dict(meta["baseline_metrics"])
    candidate_metrics = dict(meta["candidate_metrics"])
    contract = _build_contract(meta["invariants"])
    evaluation = evaluate_physics_contract_v0(
        contract=contract,
        task_invariants=[],
        baseline_metrics=baseline_metrics,
        candidate_metrics=candidate_metrics,
        scale=None,
    )
    if bool(evaluation.get("pass")):
        raise ValueError(f"source-blind multi-step contract must fail for {failure_type}")
    return baseline_metrics, candidate_metrics, evaluation


def _prepend_multistep_markers(
    source_text: str,
    *,
    failure_type: str,
    realism_version: str,
    llm_forcing: bool,
    llm_forcing_profile: str,
    llm_trigger_reason: str,
) -> str:
    prefix_lines = [f"// {MULTISTEP_MARKER_PREFIX}:{failure_type}"]
    if str(realism_version or "").strip():
        prefix_lines.append(f"// gateforge_source_blind_multistep_realism_version:{realism_version}")
    if llm_forcing:
        prefix_lines.append("// gateforge_source_blind_multistep_llm_forcing:1")
        if str(llm_forcing_profile or "").strip():
            prefix_lines.append(f"// gateforge_source_blind_multistep_llm_profile:{llm_forcing_profile}")
        if str(llm_trigger_reason or "").strip():
            prefix_lines.append(f"// gateforge_source_blind_multistep_llm_trigger:{llm_trigger_reason}")
    return "\n".join(prefix_lines) + "\n" + str(source_text or "").lstrip()


def _mutate_source_blind_multistep_model(
    source_text: str,
    failure_type: str,
    *,
    realism_version: str = DEFAULT_REALISM_VERSION,
) -> str:
    lower_source = str(source_text or "").lower()
    if "model plantb" in lower_source:
        plantb_patterns = {
            "stability_then_behavior": [
                (r"height\s*=\s*1(?:\.0+)?", "height=1.2"),
                (r"duration\s*=\s*0\.5(?:0+)?", "duration=1.1"),
                (r"startTime\s*=\s*0\.2(?:0+)?", "startTime=0.8"),
            ],
            "switch_then_recovery": [
                (r"duration\s*=\s*0\.5(?:0+)?", "duration=1.1"),
                (r"startTime\s*=\s*0\.2(?:0+)?", "startTime=0.6"),
            ],
        }
        patterns = plantb_patterns.get(str(failure_type or "").strip().lower())
        if patterns:
            lines = str(source_text or "").splitlines(keepends=True)
            seen_patterns: set[str] = set()
            updated_lines: list[str] = []
            for line in lines:
                updated_line = line
                for pattern, replacement in patterns:
                    if pattern in seen_patterns:
                        continue
                    candidate, changed = _rewrite_line_once(
                        updated_line,
                        pattern=pattern,
                        replacement=replacement,
                        failure_type=failure_type,
                    )
                    if changed:
                        updated_line = candidate
                        seen_patterns.add(pattern)
                updated_lines.append(updated_line)
            mutated = "".join(updated_lines)
            return _prepend_multistep_markers(
                mutated,
                failure_type=failure_type,
                realism_version=realism_version,
                llm_forcing=str(realism_version or "").strip().lower() == "v4",
                llm_forcing_profile=V4_LLM_FORCING_PROFILES.get(str(failure_type or "").strip().lower(), ""),
                llm_trigger_reason=V4_LLM_TRIGGER_REASONS.get(str(failure_type or "").strip().lower(), ""),
            )
    if "model switchb" in lower_source:
        switchb_patterns = {
            "behavior_then_robustness": [
                (r"startTime\s*=\s*0\.3(?:0+)?", "startTime=0.75"),
                (r"freqHz\s*=\s*1(?:\.0+)?", "freqHz=1.6"),
                (r"\bk\s*=\s*0\.5(?:0+)?", "k=0.82"),
            ],
        }
        patterns = switchb_patterns.get(str(failure_type or "").strip().lower())
        if patterns:
            lines = str(source_text or "").splitlines(keepends=True)
            seen_patterns: set[str] = set()
            updated_lines: list[str] = []
            for line in lines:
                updated_line = line
                for pattern, replacement in patterns:
                    if pattern in seen_patterns:
                        continue
                    candidate, changed = _rewrite_line_once(
                        updated_line,
                        pattern=pattern,
                        replacement=replacement,
                        failure_type=failure_type,
                    )
                    if changed:
                        updated_line = candidate
                        seen_patterns.add(pattern)
                updated_lines.append(updated_line)
            mutated = "".join(updated_lines)
            return _prepend_multistep_markers(
                mutated,
                failure_type=failure_type,
                realism_version=realism_version,
                llm_forcing=str(realism_version or "").strip().lower() == "v4",
                llm_forcing_profile=V4_LLM_FORCING_PROFILES.get(str(failure_type or "").strip().lower(), ""),
                llm_trigger_reason=V4_LLM_TRIGGER_REASONS.get(str(failure_type or "").strip().lower(), ""),
            )
    if "model switcha" in lower_source:
        switcha_patterns = {
            "stability_then_behavior": [
                (r"\bk\s*=\s*1(?:\.0+)?", "k=1.18"),
                (r"width\s*=\s*40(?:\.0+)?", "width=62"),
                (r"period\s*=\s*0\.5(?:0+)?", "period=0.85"),
            ],
        }
        patterns = switcha_patterns.get(str(failure_type or "").strip().lower())
        if patterns:
            lines = str(source_text or "").splitlines(keepends=True)
            seen_patterns: set[str] = set()
            updated_lines: list[str] = []
            for line in lines:
                updated_line = line
                for pattern, replacement in patterns:
                    if pattern in seen_patterns:
                        continue
                    candidate, changed = _rewrite_line_once(
                        updated_line,
                        pattern=pattern,
                        replacement=replacement,
                        failure_type=failure_type,
                    )
                    if changed:
                        updated_line = candidate
                        seen_patterns.add(pattern)
                updated_lines.append(updated_line)
            mutated = "".join(updated_lines)
            return _prepend_multistep_markers(
                mutated,
                failure_type=failure_type,
                realism_version=realism_version,
                llm_forcing=str(realism_version or "").strip().lower() == "v4",
                llm_forcing_profile=V4_LLM_FORCING_PROFILES.get(str(failure_type or "").strip().lower(), ""),
                llm_trigger_reason=V4_LLM_TRIGGER_REASONS.get(str(failure_type or "").strip().lower(), ""),
            )
    if "model hybridb" in lower_source:
        hybridb_patterns = {
            "switch_then_recovery": [
                (r"width\s*=\s*0\.4(?:0+)?", "width=0.75"),
                (r"startTime\s*=\s*0\.1(?:0+)?", "startTime=0.6"),
                (r"\bT\s*=\s*0\.2(?:0+)?", "T=0.5"),
                (r"\bk\s*=\s*1(?:\.0+)?", "k=0.6"),
            ],
        }
        patterns = hybridb_patterns.get(str(failure_type or "").strip().lower())
        if patterns:
            lines = str(source_text or "").splitlines(keepends=True)
            seen_patterns: set[str] = set()
            updated_lines: list[str] = []
            for line in lines:
                updated_line = line
                for pattern, replacement in patterns:
                    if pattern in seen_patterns:
                        continue
                    candidate, changed = _rewrite_line_once(
                        updated_line,
                        pattern=pattern,
                        replacement=replacement,
                        failure_type=failure_type,
                    )
                    if changed:
                        updated_line = candidate
                        seen_patterns.add(pattern)
                updated_lines.append(updated_line)
            mutated = "".join(updated_lines)
            return _prepend_multistep_markers(
                mutated,
                failure_type=failure_type,
                realism_version=realism_version,
                llm_forcing=str(realism_version or "").strip().lower() == "v4",
                llm_forcing_profile=V4_LLM_FORCING_PROFILES.get(str(failure_type or "").strip().lower(), ""),
                llm_trigger_reason=V4_LLM_TRIGGER_REASONS.get(str(failure_type or "").strip().lower(), ""),
            )
    patterns_by_failure = {
        "stability_then_behavior": [
            (r"\bk\s*=\s*1(?:\.0+)?", "k=1.18"),
            (r"height\s*=\s*1(?:\.0+)?", "height=1.12"),
            (r"startTime\s*=\s*0\.(?:1|2|3)(?:0+)?", "startTime=0.45"),
        ],
        "behavior_then_robustness": [
            (r"width\s*=\s*40(?:\.0+)?", "width=62"),
            (r"period\s*=\s*0\.5(?:0+)?", "period=0.85"),
            (r"offset\s*=\s*0(?:\.0+)?", "offset=0.2"),
        ],
        "switch_then_recovery": [
            (r"startTime\s*=\s*0\.(?:1|2|3)(?:0+)?", "startTime=0.6"),
            (r"\bk\s*=\s*1(?:\.0+)?", "k=0.6"),
            (r"width\s*=\s*40(?:\.0+)?", "width=75"),
            (r"period\s*=\s*0\.5(?:0+)?", "period=1.4"),
        ],
    }
    patterns = patterns_by_failure.get(str(failure_type or "").strip().lower(), [])
    if not patterns:
        return source_text
    lines = str(source_text or "").splitlines(keepends=True)
    seen_patterns: set[str] = set()
    updated_lines: list[str] = []
    applied = 0
    for line in lines:
        updated_line = line
        for pattern, replacement in patterns:
            if pattern in seen_patterns:
                continue
            candidate, changed = _rewrite_line_once(
                updated_line,
                pattern=pattern,
                replacement=replacement,
                failure_type=failure_type,
            )
            if changed:
                updated_line = candidate
                seen_patterns.add(pattern)
                applied += 1
        updated_lines.append(updated_line)
    mutated = "".join(updated_lines)
    if applied <= 0:
        mutated = str(source_text or "")
    return _prepend_multistep_markers(
        mutated,
        failure_type=failure_type,
        realism_version=realism_version,
        llm_forcing=str(realism_version or "").strip().lower() == "v4",
        llm_forcing_profile=V4_LLM_FORCING_PROFILES.get(str(failure_type or "").strip().lower(), ""),
        llm_trigger_reason=V4_LLM_TRIGGER_REASONS.get(str(failure_type or "").strip().lower(), ""),
    )


def build_source_blind_multistep_taskset(
    *,
    manifest_path: str,
    out_dir: str,
    failure_types: list[str],
    holdout_ratio: float,
    seed: str,
    realism_version: str = DEFAULT_REALISM_VERSION,
) -> dict:
    payload = load_source_blind_multistep_manifest(manifest_path)
    libraries, manifest_reasons = validate_source_blind_multistep_manifest(payload)
    manifest_real_path = _norm(payload.get("_manifest_path"))
    out_root = Path(out_dir)
    source_models_dir = out_root / "source_models"
    mutants_dir = out_root / "mutants"
    reasons = list(manifest_reasons)
    copied_source_paths: dict[str, str] = {}
    tasks: list[dict] = []
    counts_by_failure_type: dict[str, int] = {failure_type: 0 for failure_type in failure_types}
    counts_by_multistep_family: dict[str, int] = {}
    counts_by_library: dict[str, int] = {}
    scenario_count_distribution: dict[str, int] = {}

    for library in libraries:
        for model in [item for item in (library.get("allowed_models") or []) if isinstance(item, dict)]:
            for failure_type in failure_types:
                meta = FAILURE_METADATA[failure_type]
                model_path = Path(_norm(model.get("model_path")))
                library_id = _norm(library.get("library_id")).lower()
                model_id = _norm(model.get("model_id")).lower()
                if str(realism_version or "").strip().lower() == "v4":
                    allowed_models = V4_ALLOWED_MODELS_BY_FAILURE.get(failure_type, set())
                    if allowed_models and model_id not in allowed_models:
                        continue
                copied_source_path = source_models_dir / library_id / f"{model_id}.mo"
                source_text = _normalize_behavioral_source_model_text(model_path.read_text(encoding="utf-8", errors="ignore"))
                if str(model_path) not in copied_source_paths:
                    _write_text(copied_source_path, source_text)
                    copied_source_paths[str(model_path)] = str(copied_source_path.resolve())
                mutated_path = mutants_dir / failure_type / f"{library_id}_{model_id}_{failure_type}.mo"
                mutated_text = _mutate_source_blind_multistep_model(
                    source_text,
                    failure_type,
                    realism_version=realism_version,
                )
                _write_text(mutated_path, mutated_text)
                baseline_metrics, candidate_metrics, evaluation = _task_contract_details(failure_type)
                findings = [
                    str(item.get("metric") or "").strip()
                    for item in (evaluation.get("findings") or [])
                    if isinstance(item, dict)
                ]
                scenario_count = len(meta["scenario_matrix"])
                scenario_count_distribution[str(scenario_count)] = int(scenario_count_distribution.get(str(scenario_count), 0)) + 1
                expected_contract_failures = list(meta["expected_failure_sequence"])
                for finding in findings:
                    if finding and finding not in expected_contract_failures:
                        expected_contract_failures.append(finding)
                task = {
                    "task_id": f"source_blind_multistep_{library_id}_{model_id}_{failure_type}",
                    "failure_type": failure_type,
                    "expected_stage": "simulate",
                    "multi_step_family": meta["multi_step_family"],
                    "realism_version": str(realism_version or meta.get("realism_version") or "v1"),
                    "llm_forcing": bool(str(realism_version or "").strip().lower() == "v4"),
                    "llm_forcing_profile": (
                        V4_LLM_FORCING_PROFILES.get(failure_type, "")
                        if str(realism_version or "").strip().lower() == "v4"
                        else ""
                    ),
                    "llm_trigger_reason": (
                        V4_LLM_TRIGGER_REASONS.get(failure_type, "")
                        if str(realism_version or "").strip().lower() == "v4"
                        else ""
                    ),
                    "contract_metric_set": list(meta["contract_metric_set"]),
                    "expected_failure_sequence": list(meta["expected_failure_sequence"]),
                    "expected_contract_failures": expected_contract_failures,
                    "stage_2_branches": [dict(item) for item in meta.get("stage_2_branches", []) if isinstance(item, dict)],
                    "preferred_stage_2_branch": str(meta.get("preferred_stage_2_branch") or ""),
                    "trap_stage_2_branch": str(meta.get("trap_stage_2_branch") or ""),
                    "expected_rounds_min": int(meta["expected_rounds_min"]),
                    "scenario_count": scenario_count,
                    "scenario_matrix": [dict(item) for item in meta["scenario_matrix"]],
                    "pass_requirement": "all_scenarios",
                    "compile_pass_expected": True,
                    "simulate_pass_expected": True,
                    "contract_pass_expected": False,
                    "behavioral_mismatch_expected": True,
                    "source_model_path": str(copied_source_path.resolve()),
                    "mutated_model_path": str(mutated_path.resolve()),
                    "source_library": _norm(library.get("source_library")),
                    "source_package_name": _norm(library.get("package_name")),
                    "source_library_model_path": _norm(model.get("model_path")),
                    "source_qualified_model_name": _norm(model.get("qualified_model_name")),
                    "source_md_path": _default_md_path(model_path),
                    "manifest_path": manifest_real_path,
                    "source_meta": _build_source_meta(manifest_real_path, library, model),
                    "baseline_metrics": baseline_metrics,
                    "candidate_metrics": candidate_metrics,
                    "physics_contract_evaluation": evaluation,
                    "contract_fail_bucket": meta["contract_fail_bucket"],
                }
                task["split"] = _assign_split(task, holdout_ratio=holdout_ratio, seed=seed)
                tasks.append(task)
                counts_by_failure_type[failure_type] = int(counts_by_failure_type.get(failure_type, 0)) + 1
                family = meta["multi_step_family"]
                counts_by_multistep_family[family] = int(counts_by_multistep_family.get(family, 0)) + 1
                counts_by_library[library_id] = int(counts_by_library.get(library_id, 0)) + 1

    taskset_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_path": manifest_real_path,
        "task_count": len(tasks),
        "tasks": tasks,
    }
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if tasks else "FAIL",
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "manifest_path": manifest_real_path,
        "total_tasks": len(tasks),
        "counts_by_failure_type": counts_by_failure_type,
        "counts_by_multistep_family": counts_by_multistep_family,
        "counts_by_library": counts_by_library,
        "scenario_count_distribution": scenario_count_distribution,
        "holdout_ratio": holdout_ratio,
        "split_seed": seed,
        "realism_version": str(realism_version or DEFAULT_REALISM_VERSION),
        "taskset_frozen_path": str((out_root / "taskset_frozen.json").resolve()),
        "reasons": sorted(set(reasons)),
    }
    _write_json(out_root / "taskset_frozen.json", taskset_payload)
    _write_json(out_root / "summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build source-blind multi-step taskset")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--failure-types", default=",".join(DEFAULT_FAILURE_TYPES))
    parser.add_argument("--holdout-ratio", type=float, default=0.15)
    parser.add_argument("--seed", default="agent_modelica_source_blind_multistep_taskset_v1")
    parser.add_argument("--realism-version", default=DEFAULT_REALISM_VERSION)
    args = parser.parse_args()

    failure_types = [
        _norm(item).lower()
        for item in str(args.failure_types or "").split(",")
        if _norm(item).lower() in DEFAULT_FAILURE_TYPES
    ]
    if not failure_types:
        raise SystemExit("no valid failure types selected")
    summary = build_source_blind_multistep_taskset(
        manifest_path=args.manifest,
        out_dir=args.out_dir,
        failure_types=failure_types,
        holdout_ratio=float(args.holdout_ratio),
        seed=str(args.seed or "agent_modelica_source_blind_multistep_taskset_v1"),
        realism_version=str(args.realism_version or DEFAULT_REALISM_VERSION),
    )
    print(
        json.dumps(
            {
                "status": summary.get("status"),
                "total_tasks": summary.get("total_tasks"),
                "counts_by_failure_type": summary.get("counts_by_failure_type"),
            }
        )
    )
    if str(summary.get("status")) != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
