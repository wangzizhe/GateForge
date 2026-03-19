from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_behavioral_robustness_manifest_v1 import (
    ALLOWED_FAILURE_TYPES,
    SCHEMA_VERSION as MANIFEST_SCHEMA_VERSION,
    load_behavioral_robustness_manifest,
    validate_behavioral_robustness_manifest,
)
from .agent_modelica_behavioral_contract_taskset_v1 import _normalize_behavioral_source_model_text, _rewrite_line_once
from .agent_modelica_multi_round_failure_taskset_v1 import _ratio
from .agent_modelica_unknown_library_taskset_v1 import (
    _assign_split,
    _build_source_meta,
    _default_md_path,
    _norm,
    _write_json,
    _write_text,
)
from .physics_contract_v0 import default_physics_contract_v0, evaluate_physics_contract_v0


SCHEMA_VERSION = "agent_modelica_behavioral_robustness_taskset_v1"
DEFAULT_FAILURE_TYPES = ALLOWED_FAILURE_TYPES
ROBUSTNESS_MARKER_PREFIX = "gateforge_behavioral_robustness_violation"
FAILURE_METADATA = {
    "param_perturbation_robustness_violation": {
        "robustness_family": "param_perturbation",
        "contract_metric_set": ["gain_margin", "steady_state_error", "neighbor_case_error"],
        "expected_contract_failures": ["gain_margin", "neighbor_case_error"],
        "expected_rounds_min": 2,
        "scenario_matrix": [
            {"scenario_id": "nominal", "kind": "primary", "parameter_delta": 0.0},
            {"scenario_id": "param_plus_5pct", "kind": "neighbor", "parameter_delta": 0.05},
            {"scenario_id": "param_minus_5pct", "kind": "neighbor", "parameter_delta": -0.05},
        ],
        "baseline_metrics": {"gain_margin": 0.12, "steady_state_error": 0.02, "neighbor_case_error": 0.03},
        "candidate_metrics": {"gain_margin": 0.35, "steady_state_error": 0.11, "neighbor_case_error": 0.18},
        "invariants": [
            {"type": "range", "metric": "gain_margin", "max": 0.2},
            {"type": "range", "metric": "neighbor_case_error", "max": 0.06},
        ],
        "contract_fail_bucket": "param_sensitivity_miss",
    },
    "initial_condition_robustness_violation": {
        "robustness_family": "initial_condition",
        "contract_metric_set": ["ic_recovery_error", "ic_settling_time", "neighbor_case_error"],
        "expected_contract_failures": ["ic_recovery_error", "ic_settling_time"],
        "expected_rounds_min": 2,
        "scenario_matrix": [
            {"scenario_id": "nominal", "kind": "primary", "initial_condition_delta": 0.0},
            {"scenario_id": "ic_plus_small", "kind": "neighbor", "initial_condition_delta": 0.1},
            {"scenario_id": "ic_minus_small", "kind": "neighbor", "initial_condition_delta": -0.1},
        ],
        "baseline_metrics": {"ic_recovery_error": 0.03, "ic_settling_time": 1.0, "neighbor_case_error": 0.04},
        "candidate_metrics": {"ic_recovery_error": 0.19, "ic_settling_time": 2.9, "neighbor_case_error": 0.2},
        "invariants": [
            {"type": "range", "metric": "ic_recovery_error", "max": 0.08},
            {"type": "range", "metric": "ic_settling_time", "max": 1.5},
        ],
        "contract_fail_bucket": "initial_condition_miss",
    },
    "scenario_switch_robustness_violation": {
        "robustness_family": "scenario_switch",
        "contract_metric_set": ["scenario_switch_error", "post_switch_recovery", "neighbor_case_error"],
        "expected_contract_failures": ["scenario_switch_error", "post_switch_recovery"],
        "expected_rounds_min": 3,
        "scenario_matrix": [
            {"scenario_id": "nominal", "kind": "primary", "switch_case": "base"},
            {"scenario_id": "switch_case_fast", "kind": "neighbor", "switch_case": "fast"},
            {"scenario_id": "switch_case_slow", "kind": "neighbor", "switch_case": "slow"},
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
        raise ValueError(f"behavioral robustness contract must fail for {failure_type}")
    return baseline_metrics, candidate_metrics, evaluation


def _mutate_behavioral_robustness_model(source_text: str, failure_type: str) -> str:
    lower_source = str(source_text or "").lower()
    if "model switcha" in lower_source and "modelica.blocks.logical.switch" in lower_source:
        switch_patterns = {
            "param_perturbation_robustness_violation": [
                (r"width\s*=\s*40(?:\.0+)?", "width=62"),
                (r"period\s*=\s*0\.5(?:0+)?", "period=0.85"),
            ],
            "initial_condition_robustness_violation": [
                (r"width\s*=\s*40(?:\.0+)?", "width=18"),
                (r"period\s*=\s*0\.5(?:0+)?", "period=0.28"),
            ],
            "scenario_switch_robustness_violation": [
                (r"width\s*=\s*40(?:\.0+)?", "width=70"),
                (r"period\s*=\s*0\.5(?:0+)?", "period=1.1"),
            ],
        }
        patterns = switch_patterns.get(str(failure_type or "").strip().lower())
        if patterns:
            lines = str(source_text or "").splitlines(keepends=True)
            applied = 0
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
                        applied += 1
                updated_lines.append(updated_line)
            mutated = "".join(updated_lines)
            if applied > 0:
                return mutated.replace("gateforge_behavioral_contract_violation", ROBUSTNESS_MARKER_PREFIX)
    patterns_by_failure = {
        "param_perturbation_robustness_violation": [
            (r"\bk\s*=\s*0\.5(?:0+)?", "k=0.72"),
            (r"\bk\s*=\s*1(?:\.0+)?", "k=1.18"),
            (r"height\s*=\s*1(?:\.0+)?", "height=1.12"),
        ],
        "initial_condition_robustness_violation": [
            (r"startTime\s*=\s*0\.(?:1|2|3)(?:0+)?", "startTime=0.45"),
            (r"\bT\s*=\s*0\.2(?:0+)?", "T=0.5"),
            (r"offset\s*=\s*0(?:\.0+)?", "offset=0.2"),
        ],
        "scenario_switch_robustness_violation": [
            (r"width\s*=\s*40(?:\.0+)?", "width=75"),
            (r"period\s*=\s*0\.5(?:0+)?", "period=1.4"),
            (r"startTime\s*=\s*0\.(?:1|2|3)(?:0+)?", "startTime=0.6"),
            (r"\bk\s*=\s*1(?:\.0+)?", "k=0.6"),
        ],
    }
    patterns = patterns_by_failure.get(str(failure_type or "").strip().lower(), [])
    if not patterns:
        return source_text
    lines = str(source_text or "").splitlines(keepends=True)
    applied = 0
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
                updated_line = candidate.replace(ROBUSTNESS_MARKER_PREFIX, ROBUSTNESS_MARKER_PREFIX)
                seen_patterns.add(pattern)
                applied += 1
                break
        updated_lines.append(updated_line)
    mutated = "".join(updated_lines)
    if applied <= 0:
        return f"// {ROBUSTNESS_MARKER_PREFIX}:{failure_type}\n{mutated}"
    return mutated.replace("gateforge_behavioral_contract_violation", ROBUSTNESS_MARKER_PREFIX)


def build_behavioral_robustness_taskset(
    *,
    manifest_path: str,
    out_dir: str,
    failure_types: list[str],
    holdout_ratio: float,
    seed: str,
) -> dict:
    payload = load_behavioral_robustness_manifest(manifest_path)
    libraries, manifest_reasons = validate_behavioral_robustness_manifest(payload)
    manifest_real_path = _norm(payload.get("_manifest_path"))
    out_root = Path(out_dir)
    source_models_dir = out_root / "source_models"
    mutants_dir = out_root / "mutants"
    reasons = list(manifest_reasons)
    copied_source_paths: dict[str, str] = {}
    tasks: list[dict] = []
    counts_by_failure_type: dict[str, int] = {failure_type: 0 for failure_type in failure_types}
    counts_by_robustness_family: dict[str, int] = {}
    counts_by_library: dict[str, int] = {}
    scenario_count_distribution: dict[str, int] = {}

    for library in libraries:
        for model in [item for item in (library.get("allowed_models") or []) if isinstance(item, dict)]:
            preferred = [
                _norm(item).lower()
                for item in (model.get("preferred_failure_types") or failure_types)
                if _norm(item).lower() in failure_types
            ]
            for failure_type in preferred:
                meta = FAILURE_METADATA[failure_type]
                model_path = Path(_norm(model.get("model_path")))
                library_id = _norm(library.get("library_id")).lower()
                model_id = _norm(model.get("model_id")).lower()
                copied_source_path = source_models_dir / library_id / f"{model_id}.mo"
                source_text = _normalize_behavioral_source_model_text(model_path.read_text(encoding="utf-8", errors="ignore"))
                if str(model_path) not in copied_source_paths:
                    _write_text(copied_source_path, source_text)
                    copied_source_paths[str(model_path)] = str(copied_source_path.resolve())
                mutated_path = mutants_dir / failure_type / f"{library_id}_{model_id}_{failure_type}.mo"
                mutated_text = _mutate_behavioral_robustness_model(source_text, failure_type)
                _write_text(mutated_path, mutated_text)
                baseline_metrics, candidate_metrics, evaluation = _task_contract_details(failure_type)
                findings = [
                    str(item.get("metric") or "").strip()
                    for item in (evaluation.get("findings") or [])
                    if isinstance(item, dict)
                ]
                expected_contract_failures = list(meta["expected_contract_failures"])
                for finding in findings:
                    if finding and finding not in expected_contract_failures:
                        expected_contract_failures.append(finding)
                scenario_count = len(meta["scenario_matrix"])
                scenario_count_distribution[str(scenario_count)] = int(scenario_count_distribution.get(str(scenario_count), 0)) + 1
                task = {
                    "task_id": f"behavioral_robustness_{library_id}_{model_id}_{failure_type}",
                    "failure_type": failure_type,
                    "expected_stage": "simulate",
                    "robustness_family": meta["robustness_family"],
                    "contract_metric_set": list(meta["contract_metric_set"]),
                    "expected_contract_failures": expected_contract_failures,
                    "expected_rounds_min": int(meta["expected_rounds_min"]),
                    "compile_pass_expected": True,
                    "simulate_pass_expected": True,
                    "contract_pass_expected": False,
                    "pass_requirement": "all_scenarios",
                    "scenario_count": scenario_count,
                    "scenario_matrix": list(meta["scenario_matrix"]),
                    "contract_fail_bucket": meta["contract_fail_bucket"],
                    "source_library": library_id,
                    "domain": _norm(library.get("domain")).lower(),
                    "scale": _norm(model.get("scale_hint") or library.get("scale_hint") or "small").lower(),
                    "source_model_path": copied_source_paths[str(model_path)],
                    "mutated_model_path": str(mutated_path.resolve()),
                    "source_meta": _build_source_meta(manifest_real_path, library, model),
                    "baseline_metrics": baseline_metrics,
                    "candidate_metrics": candidate_metrics,
                    "contract_evaluation_preview": evaluation,
                    "physical_invariants": list(meta["invariants"]),
                    "repro_contract_stage": "simulate",
                }
                tasks.append(task)
                counts_by_failure_type[failure_type] = int(counts_by_failure_type.get(failure_type, 0)) + 1
                counts_by_robustness_family[meta["robustness_family"]] = int(
                    counts_by_robustness_family.get(meta["robustness_family"], 0)
                ) + 1
                counts_by_library[library_id] = int(counts_by_library.get(library_id, 0)) + 1

    tasks = sorted(tasks, key=lambda row: _norm(row.get("task_id")))
    for task in tasks:
        task["split"] = _assign_split(task, holdout_ratio=holdout_ratio, seed=seed)
    if tasks and not any(_norm(task.get("split")) == "holdout" for task in tasks):
        tasks[0]["split"] = "holdout"

    status = "PASS"
    if len(tasks) < 18:
        status = "FAIL"
        reasons.append("task_count_below_minimum")
    for failure_type in failure_types:
        if int(counts_by_failure_type.get(failure_type, 0)) < 6:
            status = "FAIL"
            reasons.append(f"failure_type_count_below_minimum:{failure_type}")

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "mode": "behavioral_robustness_frozen",
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "manifest_path": manifest_real_path,
        "total_tasks": len(tasks),
        "counts_by_failure_type": counts_by_failure_type,
        "counts_by_robustness_family": counts_by_robustness_family,
        "counts_by_library": counts_by_library,
        "scenario_count_distribution": scenario_count_distribution,
        "compile_pass_expected_pct": _ratio(len([task for task in tasks if bool(task.get("compile_pass_expected"))]), len(tasks)),
        "simulate_pass_expected_pct": _ratio(len([task for task in tasks if bool(task.get("simulate_pass_expected"))]), len(tasks)),
        "all_scenarios_fail_expected_pct": _ratio(len([task for task in tasks if not bool(task.get("contract_pass_expected"))]), len(tasks)),
        "taskset_frozen_path": str((out_root / "taskset_frozen.json").resolve()),
        "taskset_unfrozen_path": str((out_root / "taskset_unfrozen.json").resolve()),
        "reasons": sorted(set(reasons)),
    }
    frozen_payload = {"schema_version": SCHEMA_VERSION, "mode": "behavioral_robustness_frozen", "tasks": tasks}
    unfrozen_payload = {"schema_version": SCHEMA_VERSION, "mode": "behavioral_robustness_unfrozen", "tasks": tasks}
    _write_json(out_root / "taskset_frozen.json", frozen_payload)
    _write_json(out_root / "taskset_unfrozen.json", unfrozen_payload)
    _write_json(out_root / "manifest.json", payload)
    _write_json(out_root / "summary.json", summary)
    markdown = [
        "# Behavioral Robustness Taskset",
        "",
        f"- status: `{status}`",
        f"- total_tasks: `{len(tasks)}`",
        f"- counts_by_failure_type: `{json.dumps(counts_by_failure_type, sort_keys=True)}`",
        f"- counts_by_robustness_family: `{json.dumps(counts_by_robustness_family, sort_keys=True)}`",
        f"- scenario_count_distribution: `{json.dumps(scenario_count_distribution, sort_keys=True)}`",
    ]
    Path(_default_md_path(str((out_root / "summary.json").resolve()))).write_text("\n".join(markdown) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "total_tasks": len(tasks), "counts_by_failure_type": counts_by_failure_type}))
    if status != "PASS":
        raise SystemExit(1)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build behavioral robustness frozen taskset")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out-dir", default="artifacts/agent_modelica_behavioral_robustness_taskset_v1")
    parser.add_argument("--failure-types", default=",".join(DEFAULT_FAILURE_TYPES))
    parser.add_argument("--holdout-ratio", type=float, default=0.15)
    parser.add_argument("--seed", default="agent_modelica_behavioral_robustness_taskset_v1")
    args = parser.parse_args()
    failure_types = [item.strip().lower() for item in str(args.failure_types or "").split(",") if item.strip()]
    build_behavioral_robustness_taskset(
        manifest_path=str(args.manifest),
        out_dir=str(args.out_dir),
        failure_types=failure_types,
        holdout_ratio=float(args.holdout_ratio),
        seed=str(args.seed),
    )


if __name__ == "__main__":
    main()
