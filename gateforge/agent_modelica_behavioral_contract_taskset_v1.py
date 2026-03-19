from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_behavioral_contract_manifest_v1 import (
    ALLOWED_FAILURE_TYPES,
    SCHEMA_VERSION as MANIFEST_SCHEMA_VERSION,
    load_behavioral_contract_manifest,
    validate_behavioral_contract_manifest,
)
from .agent_modelica_multi_round_failure_taskset_v1 import _ratio
from .agent_modelica_unknown_library_taskset_v1 import (
    _assign_split,
    _build_source_meta,
    _copy_source_model,
    _default_md_path,
    _norm,
    _write_json,
    _write_text,
)
from .physics_contract_v0 import default_physics_contract_v0, evaluate_physics_contract_v0


SCHEMA_VERSION = "agent_modelica_behavioral_contract_taskset_v1"
DEFAULT_FAILURE_TYPES = ALLOWED_FAILURE_TYPES
FAILURE_METADATA = {
    "steady_state_target_violation": {
        "contract_family": "steady_state",
        "contract_metric_set": ["steady_state_error", "final_value", "target_value"],
        "expected_contract_failures": ["steady_state_error"],
        "expected_rounds_min": 2,
        "baseline_metrics": {"steady_state_error": 0.01, "final_value": 0.99, "target_value": 1.0},
        "candidate_metrics": {"steady_state_error": 0.18, "final_value": 0.82, "target_value": 1.0},
        "invariants": [{"type": "range", "metric": "steady_state_error", "max": 0.05}],
        "contract_fail_bucket": "steady_state_miss",
    },
    "transient_response_contract_violation": {
        "contract_family": "transient_response",
        "contract_metric_set": ["overshoot", "settling_time", "rise_time"],
        "expected_contract_failures": ["overshoot", "settling_time"],
        "expected_rounds_min": 2,
        "baseline_metrics": {"overshoot": 0.04, "settling_time": 1.3, "rise_time": 0.35},
        "candidate_metrics": {"overshoot": 0.22, "settling_time": 3.4, "rise_time": 0.52},
        "invariants": [
            {"type": "range", "metric": "overshoot", "max": 0.1},
            {"type": "range", "metric": "settling_time", "max": 2.0},
        ],
        "contract_fail_bucket": "overshoot_or_settling_violation",
    },
    "mode_transition_contract_violation": {
        "contract_family": "mode_transition",
        "contract_metric_set": ["transition_latency", "post_transition_error", "recovery_time"],
        "expected_contract_failures": ["transition_latency", "post_transition_error"],
        "expected_rounds_min": 3,
        "baseline_metrics": {"transition_latency": 0.08, "post_transition_error": 0.02, "recovery_time": 0.9},
        "candidate_metrics": {"transition_latency": 0.42, "post_transition_error": 0.18, "recovery_time": 2.8},
        "invariants": [
            {"type": "range", "metric": "transition_latency", "max": 0.2},
            {"type": "range", "metric": "post_transition_error", "max": 0.05},
        ],
        "contract_fail_bucket": "mode_transition_miss",
    },
}

BEHAVIORAL_MARKER_PREFIX = "gateforge_behavioral_contract_violation"


def _normalize_behavioral_source_model_text(source_text: str) -> str:
    text = str(source_text or "")
    # OpenModelica in our live lane rejects `freqHz` on this Sine source variant.
    # Normalize to `f` before copying the source model so source-restore remains valid.
    text = text.replace("Sine sine1(freqHz=", "Sine sine1(f=")
    return text


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
        raise ValueError(f"behavioral contract must fail for {failure_type}")
    return baseline_metrics, candidate_metrics, evaluation


def _rewrite_line_once(line: str, *, pattern: str, replacement: str, failure_type: str) -> tuple[str, bool]:
    import re

    updated, count = re.subn(pattern, replacement, line, count=1)
    if count <= 0:
        return line, False
    indent = line[: len(line) - len(line.lstrip())]
    marker = f"{indent}// {BEHAVIORAL_MARKER_PREFIX}:{failure_type}\n"
    return marker + updated, True


def _mutate_behavioral_model(source_text: str, failure_type: str) -> str:
    lower_source = str(source_text or "").lower()
    if "model switchb" in lower_source and "modelica.blocks.logical.switch" in lower_source:
        switch_patterns = {
            "steady_state_target_violation": [
                (r"\bk\s*=\s*0\.5(?:0+)?", "k=0.82"),
                (r"startTime\s*=\s*0\.3(?:0+)?", "startTime=0.45"),
            ],
            "transient_response_contract_violation": [
                (r"freqHz\s*=\s*1(?:\.0+)?", "freqHz=2.5"),
                (r"\bk\s*=\s*0\.5(?:0+)?", "k=1.25"),
            ],
            "mode_transition_contract_violation": [
                (r"startTime\s*=\s*0\.3(?:0+)?", "startTime=0.6"),
                (r"\bk\s*=\s*0\.5(?:0+)?", "k=0.4"),
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
                        break
                updated_lines.append(updated_line)
            mutated = "".join(updated_lines)
            if applied > 0:
                return mutated
    patterns_by_failure = {
        "steady_state_target_violation": [
            (r"height\s*=\s*1(?:\.0+)?", "height=0.82"),
            (r"b\s*=\s*\{1(?:\.0+)?\}", "b={0.82}"),
            (r"\bk\s*=\s*1(?:\.0+)?", "k=0.82"),
        ],
        "transient_response_contract_violation": [
            (r"width\s*=\s*40(?:\.0+)?", "width=85"),
            (r"period\s*=\s*0\.5(?:0+)?", "period=1.5"),
            (r"freqHz\s*=\s*1(?:\.0+)?", "freqHz=2.5"),
            (r"\bk\s*=\s*0\.5(?:0+)?", "k=1.25"),
        ],
        "mode_transition_contract_violation": [
            (r"startTime\s*=\s*0\.(?:1|2|3)(?:0+)?", "startTime=0.6"),
            (r"width\s*=\s*0\.4(?:0+)?", "width=0.8"),
            (r"period\s*=\s*1(?:\.0+)?", "period=1.8"),
            (r"\bk\s*=\s*1(?:\.0+)?", "k=0.4"),
            (r"\bT\s*=\s*0\.2(?:0+)?", "T=0.5"),
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
                updated_line = candidate
                seen_patterns.add(pattern)
                applied += 1
                break
        updated_lines.append(updated_line)
    mutated = "".join(updated_lines)
    if applied <= 0:
        return f"// {BEHAVIORAL_MARKER_PREFIX}:{failure_type}\n{mutated}"
    return mutated


def build_behavioral_contract_taskset(
    *,
    manifest_path: str,
    out_dir: str,
    failure_types: list[str],
    holdout_ratio: float,
    seed: str,
) -> dict:
    payload = load_behavioral_contract_manifest(manifest_path)
    libraries, manifest_reasons = validate_behavioral_contract_manifest(payload)
    manifest_real_path = _norm(payload.get("_manifest_path"))
    out_root = Path(out_dir)
    source_models_dir = out_root / "source_models"
    mutants_dir = out_root / "mutants"
    reasons = list(manifest_reasons)
    copied_source_paths: dict[str, str] = {}
    tasks: list[dict] = []
    counts_by_failure_type: dict[str, int] = {failure_type: 0 for failure_type in failure_types}
    counts_by_contract_family: dict[str, int] = {}
    counts_by_library: dict[str, int] = {}
    metric_coverage: dict[str, int] = {}

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
                source_text = _normalize_behavioral_source_model_text(
                    model_path.read_text(encoding="utf-8", errors="ignore")
                )
                if str(model_path) not in copied_source_paths:
                    _write_text(copied_source_path, source_text)
                    copied_source_paths[str(model_path)] = str(copied_source_path.resolve())
                mutated_path = mutants_dir / failure_type / f"{library_id}_{model_id}_{failure_type}.mo"
                mutated_text = _mutate_behavioral_model(source_text, failure_type)
                _write_text(mutated_path, mutated_text)
                baseline_metrics, candidate_metrics, evaluation = _task_contract_details(failure_type)
                findings = [str(item.get("metric") or "").strip() for item in (evaluation.get("findings") or []) if isinstance(item, dict)]
                expected_contract_failures = list(meta["expected_contract_failures"])
                for finding in findings:
                    if finding and finding not in expected_contract_failures:
                        expected_contract_failures.append(finding)
                for metric in meta["contract_metric_set"]:
                    metric_coverage[metric] = int(metric_coverage.get(metric, 0)) + 1
                task = {
                    "task_id": f"behavioral_contract_{library_id}_{model_id}_{failure_type}",
                    "failure_type": failure_type,
                    "expected_stage": "simulate",
                    "contract_family": meta["contract_family"],
                    "contract_metric_set": list(meta["contract_metric_set"]),
                    "expected_contract_failures": expected_contract_failures,
                    "expected_rounds_min": int(meta["expected_rounds_min"]),
                    "compile_pass_expected": True,
                    "simulate_pass_expected": True,
                    "contract_pass_expected": False,
                    "behavioral_mismatch_expected": True,
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
                counts_by_contract_family[meta["contract_family"]] = int(counts_by_contract_family.get(meta["contract_family"], 0)) + 1
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
        "mode": "behavioral_contract_frozen",
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "manifest_path": manifest_real_path,
        "total_tasks": len(tasks),
        "counts_by_failure_type": counts_by_failure_type,
        "counts_by_contract_family": counts_by_contract_family,
        "counts_by_library": counts_by_library,
        "contract_metric_coverage": metric_coverage,
        "compile_pass_expected_pct": _ratio(len([task for task in tasks if bool(task.get("compile_pass_expected"))]), len(tasks)),
        "simulate_pass_expected_pct": _ratio(len([task for task in tasks if bool(task.get("simulate_pass_expected"))]), len(tasks)),
        "contract_fail_expected_pct": _ratio(len([task for task in tasks if not bool(task.get("contract_pass_expected"))]), len(tasks)),
        "taskset_frozen_path": str((out_root / "taskset_frozen.json").resolve()),
        "taskset_unfrozen_path": str((out_root / "taskset_unfrozen.json").resolve()),
        "reasons": sorted(set(reasons)),
    }
    frozen_payload = {"schema_version": SCHEMA_VERSION, "mode": "behavioral_contract_frozen", "tasks": tasks}
    unfrozen_payload = {"schema_version": SCHEMA_VERSION, "mode": "behavioral_contract_unfrozen", "tasks": tasks}
    _write_json(out_root / "taskset_frozen.json", frozen_payload)
    _write_json(out_root / "taskset_unfrozen.json", unfrozen_payload)
    _write_json(out_root / "manifest.json", payload)
    _write_json(out_root / "summary.json", summary)
    markdown = [
        "# Behavioral Contract Taskset",
        "",
        f"- status: `{status}`",
        f"- total_tasks: `{len(tasks)}`",
        f"- counts_by_failure_type: `{json.dumps(counts_by_failure_type, sort_keys=True)}`",
        f"- counts_by_contract_family: `{json.dumps(counts_by_contract_family, sort_keys=True)}`",
        f"- contract_metric_coverage: `{json.dumps(metric_coverage, sort_keys=True)}`",
    ]
    Path(_default_md_path(str((out_root / "summary.json").resolve()))).write_text("\n".join(markdown) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "total_tasks": len(tasks), "counts_by_failure_type": counts_by_failure_type}))
    if status != "PASS":
        raise SystemExit(1)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build behavioral contract frozen taskset")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out-dir", default="artifacts/agent_modelica_behavioral_contract_taskset_v1")
    parser.add_argument("--failure-types", default=",".join(DEFAULT_FAILURE_TYPES))
    parser.add_argument("--holdout-ratio", type=float, default=0.15)
    parser.add_argument("--seed", default="agent_modelica_behavioral_contract_taskset_v1")
    args = parser.parse_args()
    failure_types = [item.strip().lower() for item in str(args.failure_types or "").split(",") if item.strip()]
    build_behavioral_contract_taskset(
        manifest_path=str(args.manifest),
        out_dir=str(args.out_dir),
        failure_types=failure_types,
        holdout_ratio=float(args.holdout_ratio),
        seed=str(args.seed),
    )


if __name__ == "__main__":
    main()
