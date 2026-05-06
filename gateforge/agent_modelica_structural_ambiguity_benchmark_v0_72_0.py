from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "structural_ambiguity_seed_candidates_v0_72_0"
DEFAULT_VARIANT_OUT_DIR = REPO_ROOT / "artifacts" / "structural_ambiguity_variants_v0_73_4"
DEFAULT_SECOND_GEN_OUT_DIR = REPO_ROOT / "artifacts" / "structural_ambiguity_second_gen_v0_74_1"
DEFAULT_MEDIUM_HARD_PACK_OUT_DIR = REPO_ROOT / "artifacts" / "structural_ambiguity_medium_hard_pack_v0_75_5"
DEFAULT_STABLE_PATTERN_EXPANSION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "structural_ambiguity_stable_pattern_expansion_v0_76_0"
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _task(
    *,
    case_id: str,
    family: str,
    title: str,
    description: str,
    constraints: list[str],
    initial_model: str,
    stop_time: float = 0.1,
    intervals: int = 100,
    registry_bundle: str = "v0.72_structural_ambiguity_candidates",
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "task_type": "repair",
        "title": title,
        "difficulty": "candidate_medium_hard",
        "source_backed": False,
        "description": description,
        "constraints": constraints,
        "initial_model": initial_model.strip() + "\n",
        "submission_format": "Return the final repaired Modelica model text.",
        "verification": {"check_model": True, "simulate": {"stop_time": stop_time, "intervals": intervals}},
        "verification_command": "Run model check first, then simulation when model check succeeds.",
        "dataset_split": "holdout",
        "registry_family": family,
        "registry_bundle": registry_bundle,
    }


def build_structural_ambiguity_seed_candidates(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    tasks = [
        _task(
            case_id="balanced_singularity_01_duplicate_observer_constraint",
            family="balanced_structural_singularity",
            title="Repair duplicate observer constraint singularity",
            description=(
                "An observer refactor introduced redundant aggregate constraints. Restore a compileable and "
                "simulatable model while preserving the total signal and differential observation workflow."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep both component signals and the observed difference.",
                "Do not remove the observation workflow.",
            ],
            initial_model="""
model BalancedSingularityDuplicateObserverConstraint
  Real x;
  Real y;
  Real total;
  Real observed;
equation
  total = 1 + time;
  x + y = total;
  2 * x + 2 * y = 2 * total;
  observed = x - y;
end BalancedSingularityDuplicateObserverConstraint;
""",
        ),
        _task(
            case_id="balanced_singularity_02_array_projection_rank_loss",
            family="balanced_structural_singularity",
            title="Repair array projection rank loss",
            description=(
                "An array projection was refactored into summary and contrast signals. Restore a compileable and "
                "simulatable model while keeping the array projection intent."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep the three-element state array.",
                "Preserve both summary and contrast signals.",
            ],
            initial_model="""
model BalancedSingularityArrayProjectionRankLoss
  Real state[3];
  Real summary;
  Real contrast;
equation
  state[1] + state[2] + state[3] = 1 + time;
  2 * state[1] + 2 * state[2] + 2 * state[3] = 2 + 2 * time;
  summary = state[1] + state[2] + state[3];
  contrast = state[1] - state[3];
end BalancedSingularityArrayProjectionRankLoss;
""",
        ),
        _task(
            case_id="mixed_constraint_01_residual_projection_conflict",
            family="mixed_over_under_constraint",
            title="Repair residual projection conflict",
            description=(
                "A residual projection refactor mixed aggregate and element-level constraints. Restore a "
                "compileable and simulatable model while preserving residual and aggregate outputs."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep the residual array and aggregate output.",
                "Preserve the projection workflow rather than deleting residual signals.",
            ],
            initial_model="""
model MixedConstraintResidualProjectionConflict
  parameter Integer n = 3;
  Real source[n];
  Real estimate[n];
  Real residual[n];
  Real aggregate;
equation
  for i in 1:n loop
    source[i] = i * sin(time);
    estimate[i] = source[i];
  end for;
  residual[1] = source[1] - estimate[1];
  residual[2] = source[2] - estimate[2];
  aggregate = residual[1] + residual[2] + residual[3];
  aggregate = 0;
  residual[1] + residual[2] = 0;
end MixedConstraintResidualProjectionConflict;
""",
        ),
        _task(
            case_id="mixed_constraint_02_mode_residual_conflict",
            family="mixed_over_under_constraint",
            title="Repair mode residual conflict",
            description=(
                "A mode-specific residual workflow was partially migrated. Restore a compileable and simulatable "
                "model while preserving raw, filtered, observed, and residual signals."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep the mode parameter and all four workflow signals.",
                "Do not collapse the mode workflow into a single direct assignment.",
            ],
            initial_model="""
model MixedConstraintModeResidualConflict
  parameter Boolean useFiltered = false;
  Real raw;
  Real filtered;
  Real observed;
  Real residual;
equation
  raw = sin(time);
  if useFiltered then
    der(filtered) = raw - filtered;
    observed = filtered;
    residual = raw - observed;
  else
    observed = raw;
    residual = filtered - observed;
  end if;
  residual = raw - observed;
end MixedConstraintModeResidualConflict;
""",
        ),
        _task(
            case_id="redeclare_boundary_01_incompatible_monitor_contract",
            family="redeclare_contract_boundary",
            title="Repair incompatible redeclared monitor contract",
            description=(
                "A monitor implementation was redeclared under a broader contract during a hierarchy refactor. "
                "Restore a compileable and simulatable model while preserving level, trend, and quality outputs."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep the replaceable monitor boundary.",
                "Preserve all exported monitor signals.",
            ],
            initial_model="""
model RedeclareBoundaryIncompatibleMonitorContract
  partial model MonitorBase
    input Real u;
    output Real level;
    output Real trend;
    output Real quality;
  end MonitorBase;
  model LevelTrendMonitor
    extends MonitorBase;
  equation
    level = u;
    trend = der(u);
  end LevelTrendMonitor;
  replaceable model Monitor = LevelTrendMonitor constrainedby MonitorBase;
  Monitor monitor;
  Real signal;
  Real levelSignal;
  Real trendSignal;
  Real qualitySignal;
equation
  signal = sin(time);
  monitor.u = signal;
  levelSignal = monitor.level;
  trendSignal = monitor.trend;
  qualitySignal = monitor.quality;
end RedeclareBoundaryIncompatibleMonitorContract;
""",
        ),
        _task(
            case_id="redeclare_boundary_02_arrayed_quality_contract",
            family="redeclare_contract_boundary",
            title="Repair arrayed quality contract boundary",
            description=(
                "An arrayed quality estimator was redeclared under a reusable contract. Restore a compileable and "
                "simulatable model while keeping the estimator array and quality outputs."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep the arrayed replaceable estimator.",
                "Preserve estimate, residual, and quality arrays.",
            ],
            initial_model="""
model RedeclareBoundaryArrayedQualityContract
  partial model EstimatorBase
    input Real measurement;
    output Real estimate;
    output Real residual;
    output Real quality;
  end EstimatorBase;
  model ResidualEstimator
    extends EstimatorBase;
    parameter Real alpha = 0.5;
  equation
    estimate = alpha * measurement;
    residual = measurement - estimate;
  end ResidualEstimator;
  replaceable model Estimator = ResidualEstimator constrainedby EstimatorBase;
  Estimator estimator[3];
  Real measurement[3];
  Real estimate[3];
  Real residual[3];
  Real quality[3];
equation
  for i in 1:3 loop
    measurement[i] = i + sin(time);
    estimator[i].measurement = measurement[i];
    estimate[i] = estimator[i].estimate;
    residual[i] = estimator[i].residual;
    quality[i] = estimator[i].quality;
  end for;
end RedeclareBoundaryArrayedQualityContract;
""",
        ),
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    tasks_path = out_dir / "tasks.jsonl"
    tasks_path.write_text(
        "".join(json.dumps(task, sort_keys=True) + "\n" for task in tasks),
        encoding="utf-8",
    )
    family_counts = Counter(str(task["registry_family"]) for task in tasks)
    summary = {
        "version": "v0.72.0",
        "analysis_scope": "structural_ambiguity_seed_candidate_build",
        "status": "PASS",
        "artifact_complete": True,
        "task_count": len(tasks),
        "tasks_path": str(tasks_path),
        "family_counts": dict(sorted(family_counts.items())),
        "case_ids": [str(task["case_id"]) for task in tasks],
        "scope_note": (
            "These candidates intentionally avoid direct missing-output-only construction. They still require OMC "
            "admission and live baseline calibration before benchmark use."
        ),
    }
    write_json(out_dir / "summary.json", summary)
    return summary


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def summarize_budget_calibration(
    *,
    result_paths_by_budget: dict[str, Path],
    out_dir: Path,
    summary_version: str = "v0.72.5",
) -> dict[str, Any]:
    by_case: dict[str, dict[str, dict[str, Any]]] = {}
    for budget_label, path in result_paths_by_budget.items():
        for row in load_jsonl(path):
            case_id = str(row.get("case_id") or "")
            by_case.setdefault(case_id, {})[str(budget_label)] = {
                "final_verdict": str(row.get("final_verdict") or ""),
                "submitted": bool(row.get("submitted")),
                "token_used": int(row.get("token_used") or 0),
                "candidate_count": len(row.get("candidate_files") or []),
                "provider_error": str(row.get("provider_error") or ""),
                "harness_timeout": bool(row.get("harness_timeout")),
            }
    rows: list[dict[str, Any]] = []
    for case_id, budget_rows in sorted(by_case.items()):
        pass_budgets = [
            budget
            for budget, row in budget_rows.items()
            if row["final_verdict"] == "PASS" and not row["provider_error"] and not row["harness_timeout"]
        ]
        fail_budgets = [
            budget
            for budget, row in budget_rows.items()
            if row["final_verdict"] != "PASS" and not row["provider_error"] and not row["harness_timeout"]
        ]
        if pass_budgets and fail_budgets:
            calibration_status = "budget_sensitive_medium_hard"
        elif pass_budgets:
            calibration_status = "solved_at_all_observed_budgets"
        elif fail_budgets:
            calibration_status = "failed_at_all_observed_budgets"
        else:
            calibration_status = "blocked_or_incomplete"
        rows.append(
            {
                "case_id": case_id,
                "calibration_status": calibration_status,
                "budget_results": budget_rows,
            }
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "budget_calibration_cases.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    status_counts = Counter(row["calibration_status"] for row in rows)
    summary = {
        "version": summary_version,
        "analysis_scope": "structural_ambiguity_budget_calibration",
        "status": "PASS" if rows else "REVIEW",
        "artifact_complete": bool(rows),
        "case_count": len(rows),
        "calibration_status_counts": dict(sorted(status_counts.items())),
        "budget_sensitive_case_ids": [
            row["case_id"] for row in rows if row["calibration_status"] == "budget_sensitive_medium_hard"
        ],
        "scope_note": (
            "Budget-sensitive cases are not yet formal hard benchmark seeds. They are medium-hard substrate "
            "candidates that need repeatability if used for capability comparisons."
        ),
    }
    write_json(out_dir / "summary.json", summary)
    return summary


def summarize_budget_repeatability(
    *,
    result_paths_by_run: dict[str, Path],
    out_dir: Path,
    summary_version: str = "v0.75.3",
) -> dict[str, Any]:
    by_case_budget: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for run_label, path in result_paths_by_run.items():
        budget_label = _canonical_budget_label(str(run_label))
        for row in load_jsonl(path):
            case_id = str(row.get("case_id") or "")
            if not case_id:
                continue
            by_case_budget.setdefault(case_id, {}).setdefault(budget_label, []).append(
                {
                    "run_label": str(run_label),
                    "final_verdict": str(row.get("final_verdict") or ""),
                    "provider_error": str(row.get("provider_error") or ""),
                    "harness_timeout": bool(row.get("harness_timeout")),
                    "submitted": bool(row.get("submitted")),
                    "token_used": int(row.get("token_used") or 0),
                    "candidate_count": len(row.get("candidate_files") or []),
                }
            )
    rows: list[dict[str, Any]] = []
    for case_id, budget_rows in sorted(by_case_budget.items()):
        budget_summaries: dict[str, dict[str, Any]] = {}
        has_unstable_budget = False
        clean_statuses: list[str] = []
        for budget_label, runs in sorted(budget_rows.items(), key=lambda item: _budget_sort_key(item[0])):
            clean_runs = [
                run for run in runs if not run["provider_error"] and not run["harness_timeout"]
            ]
            pass_count = sum(1 for run in clean_runs if run["final_verdict"] == "PASS")
            fail_count = sum(1 for run in clean_runs if run["final_verdict"] != "PASS")
            if pass_count and fail_count:
                budget_status = "unstable"
                has_unstable_budget = True
            elif pass_count:
                budget_status = "all_pass"
            elif fail_count:
                budget_status = "all_fail"
            else:
                budget_status = "blocked"
            clean_statuses.append(budget_status)
            budget_summaries[budget_label] = {
                "budget_status": budget_status,
                "run_count": len(runs),
                "clean_run_count": len(clean_runs),
                "pass_count": pass_count,
                "fail_count": fail_count,
                "blocked_count": len(runs) - len(clean_runs),
                "runs": runs,
            }
        if has_unstable_budget:
            repeatability_status = "unstable_medium_candidate"
        elif "all_fail" in clean_statuses and "all_pass" in clean_statuses:
            repeatability_status = "repeatable_budget_sensitive_medium_hard"
        elif clean_statuses and all(status == "all_pass" for status in clean_statuses):
            repeatability_status = "solved_at_all_clean_budgets"
        elif clean_statuses and all(status == "all_fail" for status in clean_statuses):
            repeatability_status = "failed_at_all_clean_budgets"
        else:
            repeatability_status = "blocked_or_incomplete"
        rows.append(
            {
                "case_id": case_id,
                "repeatability_status": repeatability_status,
                "budget_summaries": budget_summaries,
            }
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "budget_repeatability_cases.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    status_counts = Counter(row["repeatability_status"] for row in rows)
    summary = {
        "version": summary_version,
        "analysis_scope": "budget_repeatability_summary",
        "status": "PASS" if rows else "REVIEW",
        "artifact_complete": bool(rows),
        "case_count": len(rows),
        "repeatability_status_counts": dict(sorted(status_counts.items())),
        "repeatable_budget_sensitive_case_ids": [
            row["case_id"]
            for row in rows
            if row["repeatability_status"] == "repeatable_budget_sensitive_medium_hard"
        ],
        "unstable_case_ids": [
            row["case_id"] for row in rows if row["repeatability_status"] == "unstable_medium_candidate"
        ],
        "scope_note": (
            "This stricter repeatability summary groups repeated runs by canonical budget. A case is not "
            "repeatable medium-hard if the same budget contains both PASS and FAIL clean runs."
        ),
    }
    write_json(out_dir / "summary.json", summary)
    return summary


def build_medium_hard_pack(
    *,
    task_paths: list[Path],
    repeatability_summary_paths: list[Path],
    out_dir: Path = DEFAULT_MEDIUM_HARD_PACK_OUT_DIR,
    summary_version: str = "v0.75.5",
) -> dict[str, Any]:
    tasks_by_case: dict[str, dict[str, Any]] = {}
    for task_path in task_paths:
        for task in load_jsonl(task_path):
            case_id = str(task.get("case_id") or "")
            if case_id:
                tasks_by_case[case_id] = task
    repeatable_ids: set[str] = set()
    unstable_ids: set[str] = set()
    for summary_path in repeatability_summary_paths:
        if not summary_path.exists():
            continue
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        repeatable_ids.update(str(case_id) for case_id in payload.get("repeatable_budget_sensitive_case_ids") or [])
        unstable_ids.update(str(case_id) for case_id in payload.get("unstable_case_ids") or [])
    pack_tasks = [tasks_by_case[case_id] for case_id in sorted(repeatable_ids) if case_id in tasks_by_case]
    out_dir.mkdir(parents=True, exist_ok=True)
    tasks_path = out_dir / "tasks.jsonl"
    tasks_path.write_text(
        "".join(json.dumps(task, sort_keys=True) + "\n" for task in pack_tasks),
        encoding="utf-8",
    )
    family_counts = Counter(str(task.get("registry_family") or "") for task in pack_tasks)
    summary = {
        "version": summary_version,
        "analysis_scope": "structural_ambiguity_medium_hard_pack",
        "status": "PASS" if pack_tasks else "REVIEW",
        "artifact_complete": bool(pack_tasks) and len(pack_tasks) == len(repeatable_ids),
        "evidence_role": "formal_experiment",
        "conclusion_allowed": bool(pack_tasks) and len(pack_tasks) == len(repeatable_ids),
        "pack_task_count": len(pack_tasks),
        "tasks_path": str(tasks_path),
        "medium_hard_case_ids": [str(task.get("case_id") or "") for task in pack_tasks],
        "unstable_case_ids": sorted(unstable_ids - repeatable_ids),
        "family_counts": dict(sorted(family_counts.items())),
        "pack_policy": (
            "Only cases with strict repeatable budget-sensitive status are included. Same-budget PASS/FAIL cases "
            "remain unstable and are excluded."
        ),
        "benchmark_layer": "medium_hard_budget_sensitive",
    }
    write_json(out_dir / "summary.json", summary)
    return summary


def build_stable_pattern_expansion_variants(
    *,
    out_dir: Path = DEFAULT_STABLE_PATTERN_EXPANSION_OUT_DIR,
) -> dict[str, Any]:
    bundle = "v0.76_structural_ambiguity_stable_pattern_expansion"
    tasks = [
        _task(
            case_id="residual_projection_03_three_window_overlap_closure",
            family="residual_projection_closure_conflict",
            title="Repair three-window residual closure conflict",
            description=(
                "A residual projection workflow now has three overlapping windows and one aggregate closure. "
                "Restore a compileable and simulatable model while preserving residual, window, and aggregate signals."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep all five residual elements.",
                "Preserve all three window outputs and the aggregate output.",
            ],
            initial_model="""
model ResidualProjectionThreeWindowOverlapClosure
  Real source[5];
  Real estimate[5];
  Real residual[5];
  Real window[3];
  Real aggregate;
equation
  for i in 1:5 loop
    source[i] = i * sin(time);
    estimate[i] = source[i];
  end for;
  residual[1] = source[1] - estimate[1];
  residual[2] = source[2] - estimate[2];
  residual[3] = source[3] - estimate[3];
  window[1] = residual[1] + residual[2];
  window[2] = residual[2] + residual[3];
  window[3] = residual[3] + residual[4];
  aggregate = window[1] + window[2] + window[3] + residual[5];
  aggregate = 0;
  window[1] = 0;
end ResidualProjectionThreeWindowOverlapClosure;
""",
            registry_bundle=bundle,
        ),
        _task(
            case_id="residual_projection_04_nested_window_closure_conflict",
            family="residual_projection_closure_conflict",
            title="Repair nested window residual closure conflict",
            description=(
                "A nested residual projection combines local window closures with a global aggregate. Restore a "
                "compileable and simulatable model while preserving the nested residual workflow."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep the four-element residual workflow.",
                "Preserve local, bridge, and global outputs.",
            ],
            initial_model="""
model ResidualProjectionNestedWindowClosureConflict
  Real source[4];
  Real estimate[4];
  Real residual[4];
  Real local;
  Real bridge;
  Real global;
equation
  for i in 1:4 loop
    source[i] = i * cos(time);
    estimate[i] = source[i];
  end for;
  residual[1] = source[1] - estimate[1];
  residual[2] = source[2] - estimate[2];
  local = residual[1] + residual[2];
  bridge = local + residual[3];
  global = bridge + residual[4];
  global = 0;
  local = 0;
end ResidualProjectionNestedWindowClosureConflict;
""",
            registry_bundle=bundle,
        ),
        _task(
            case_id="residual_projection_05_dual_aggregate_closure_conflict",
            family="residual_projection_closure_conflict",
            title="Repair dual aggregate residual closure conflict",
            description=(
                "A residual projection exposes two aggregate outputs over shared residual elements. Restore a "
                "compileable and simulatable model while preserving both aggregate outputs."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep the shared residual projection.",
                "Preserve both aggregate outputs and the residual array.",
            ],
            initial_model="""
model ResidualProjectionDualAggregateClosureConflict
  Real source[4];
  Real estimate[4];
  Real residual[4];
  Real aggregateA;
  Real aggregateB;
equation
  for i in 1:4 loop
    source[i] = i + sin(time);
    estimate[i] = source[i];
  end for;
  residual[1] = source[1] - estimate[1];
  residual[2] = source[2] - estimate[2];
  aggregateA = residual[1] + residual[2] + residual[3];
  aggregateB = residual[2] + residual[3] + residual[4];
  aggregateA = 0;
  residual[1] + residual[2] = 0;
end ResidualProjectionDualAggregateClosureConflict;
""",
            registry_bundle=bundle,
        ),
        _task(
            case_id="mixed_constraint_03_segmented_residual_projection_conflict",
            family="mixed_over_under_constraint",
            title="Repair segmented residual projection conflict",
            description=(
                "A segmented residual projection mixes segment-level closures and an aggregate residual output. "
                "Restore a compileable and simulatable model while keeping the segment workflow."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep all segment outputs.",
                "Preserve the residual and aggregate projection workflow.",
            ],
            initial_model="""
model MixedConstraintSegmentedResidualProjectionConflict
  Real source[4];
  Real estimate[4];
  Real residual[4];
  Real segmentA;
  Real segmentB;
  Real aggregate;
equation
  for i in 1:4 loop
    source[i] = i * sin(time);
    estimate[i] = source[i];
  end for;
  residual[1] = source[1] - estimate[1];
  residual[2] = source[2] - estimate[2];
  segmentA = residual[1] + residual[2];
  segmentB = residual[3] + residual[4];
  aggregate = segmentA + segmentB;
  aggregate = 0;
  segmentA = 0;
end MixedConstraintSegmentedResidualProjectionConflict;
""",
            registry_bundle=bundle,
        ),
        _task(
            case_id="mixed_constraint_04_projection_delta_closure_conflict",
            family="mixed_over_under_constraint",
            title="Repair projection delta closure conflict",
            description=(
                "A projection refactor introduced delta outputs and aggregate closure equations over shared latent "
                "states. Restore a compileable and simulatable model while preserving both delta outputs."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep all latent states.",
                "Preserve total, delta, and aggregate outputs.",
            ],
            initial_model="""
model MixedConstraintProjectionDeltaClosureConflict
  Real state[4];
  Real total;
  Real deltaA;
  Real deltaB;
  Real aggregate;
equation
  state[1] + state[2] + state[3] + state[4] = 1 + time;
  2 * state[1] + 2 * state[2] + 2 * state[3] + 2 * state[4] = 2 + 2 * time;
  total = state[1] + state[2] + state[3] + state[4];
  deltaA = state[1] - state[3];
  deltaB = state[2] - state[4];
  aggregate = deltaA + deltaB;
  aggregate = 0;
end MixedConstraintProjectionDeltaClosureConflict;
""",
            registry_bundle=bundle,
        ),
        _task(
            case_id="mixed_constraint_05_window_balance_projection_conflict",
            family="mixed_over_under_constraint",
            title="Repair window balance projection conflict",
            description=(
                "A window balance projection combines duplicated balance equations with exposed observer outputs. "
                "Restore a compileable and simulatable model while keeping all observer outputs."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep all latent states.",
                "Preserve balance, skew, and observer outputs.",
            ],
            initial_model="""
model MixedConstraintWindowBalanceProjectionConflict
  Real state[3];
  Real balance;
  Real skew;
  Real observer;
equation
  state[1] + state[2] + state[3] = 1 + sin(time);
  4 * state[1] + 4 * state[2] + 4 * state[3] = 4 + 4 * sin(time);
  balance = state[1] + state[2] - state[3];
  skew = state[1] - 2 * state[2] + state[3];
  observer = balance + skew;
end MixedConstraintWindowBalanceProjectionConflict;
""",
            registry_bundle=bundle,
        ),
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    tasks_path = out_dir / "tasks.jsonl"
    tasks_path.write_text(
        "".join(json.dumps(task, sort_keys=True) + "\n" for task in tasks),
        encoding="utf-8",
    )
    family_counts = Counter(str(task["registry_family"]) for task in tasks)
    summary = {
        "version": "v0.76.0",
        "analysis_scope": "structural_ambiguity_stable_pattern_expansion_build",
        "status": "PASS",
        "artifact_complete": True,
        "task_count": len(tasks),
        "tasks_path": str(tasks_path),
        "family_counts": dict(sorted(family_counts.items())),
        "case_ids": [str(task["case_id"]) for task in tasks],
        "source_pattern_case_ids": [
            "mixed_constraint_01_residual_projection_conflict",
            "residual_projection_01_two_window_closure_conflict",
        ],
        "scope_note": (
            "These candidates expand only around stable strict medium-hard patterns. They require OMC admission, "
            "budget calibration, and strict repeatability before benchmark promotion."
        ),
    }
    write_json(out_dir / "summary.json", summary)
    return summary


def _canonical_budget_label(run_label: str) -> str:
    for token in str(run_label).split("_"):
        if token.endswith("k") and token[:-1].isdigit():
            return token
    return str(run_label)


def _budget_sort_key(budget_label: str) -> tuple[int, str]:
    if budget_label.endswith("k") and budget_label[:-1].isdigit():
        return (int(budget_label[:-1]), budget_label)
    return (10**9, budget_label)


def build_structural_ambiguity_variants(
    *,
    out_dir: Path = DEFAULT_VARIANT_OUT_DIR,
) -> dict[str, Any]:
    tasks = [
        _task(
            case_id="balanced_singularity_variant_01_weighted_projection_rank_loss",
            family="balanced_structural_singularity",
            title="Repair weighted projection rank loss",
            description=(
                "A weighted projection was refactored into total and contrast outputs. Restore a compileable and "
                "simulatable model while preserving the weighted projection workflow."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep all four state components.",
                "Preserve total, weighted, and contrast outputs.",
            ],
            initial_model="""
model BalancedSingularityVariantWeightedProjectionRankLoss
  Real state[4];
  Real total;
  Real weighted;
  Real contrast;
equation
  state[1] + state[2] + state[3] + state[4] = 1 + time;
  2 * state[1] + 2 * state[2] + 2 * state[3] + 2 * state[4] = 2 + 2 * time;
  total = state[1] + state[2] + state[3] + state[4];
  weighted = state[1] + 2 * state[2] + 3 * state[3] + 4 * state[4];
  contrast = state[1] - state[4];
end BalancedSingularityVariantWeightedProjectionRankLoss;
""",
        ),
        _task(
            case_id="balanced_singularity_variant_02_coupled_summary_rank_loss",
            family="balanced_structural_singularity",
            title="Repair coupled summary rank loss",
            description=(
                "A coupled summary workflow was introduced for two latent signals. Restore a compileable and "
                "simulatable model while preserving sum, scaled sum, and differential outputs."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep both latent signals.",
                "Preserve the three exported observation signals.",
            ],
            initial_model="""
model BalancedSingularityVariantCoupledSummaryRankLoss
  Real left;
  Real right;
  Real sumSignal;
  Real scaledSum;
  Real differenceSignal;
equation
  left + right = 1 + sin(time);
  3 * left + 3 * right = 3 + 3 * sin(time);
  sumSignal = left + right;
  scaledSum = 3 * left + 3 * right;
  differenceSignal = left - right;
end BalancedSingularityVariantCoupledSummaryRankLoss;
""",
        ),
        _task(
            case_id="mixed_constraint_variant_01_windowed_residual_conflict",
            family="mixed_over_under_constraint",
            title="Repair windowed residual projection conflict",
            description=(
                "A windowed residual projection mixed local and aggregate constraints. Restore a compileable and "
                "simulatable model while preserving all residual and window outputs."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep the four-element residual workflow.",
                "Preserve local residuals and window aggregate outputs.",
            ],
            initial_model="""
model MixedConstraintVariantWindowedResidualConflict
  parameter Integer n = 4;
  Real source[n];
  Real estimate[n];
  Real residual[n];
  Real windowA;
  Real windowB;
equation
  for i in 1:n loop
    source[i] = i * cos(time);
    estimate[i] = source[i];
  end for;
  residual[1] = source[1] - estimate[1];
  residual[2] = source[2] - estimate[2];
  residual[3] = source[3] - estimate[3];
  windowA = residual[1] + residual[2];
  windowB = residual[3] + residual[4];
  windowA = 0;
  residual[1] + residual[2] = 0;
end MixedConstraintVariantWindowedResidualConflict;
""",
        ),
        _task(
            case_id="mixed_constraint_variant_02_hierarchical_residual_conflict",
            family="mixed_over_under_constraint",
            title="Repair hierarchical residual projection conflict",
            description=(
                "A hierarchical residual projection introduced both element-level and aggregate constraints. "
                "Restore a compileable and simulatable model while preserving the hierarchy outputs."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep all residual hierarchy signals.",
                "Do not remove the aggregate projection workflow.",
            ],
            initial_model="""
model MixedConstraintVariantHierarchicalResidualConflict
  Real source[3];
  Real estimate[3];
  Real residual[3];
  Real localTotal;
  Real globalTotal;
equation
  for i in 1:3 loop
    source[i] = i + sin(time);
    estimate[i] = source[i];
  end for;
  residual[1] = source[1] - estimate[1];
  residual[2] = source[2] - estimate[2];
  localTotal = residual[1] + residual[2];
  globalTotal = localTotal + residual[3];
  globalTotal = 0;
  localTotal = 0;
end MixedConstraintVariantHierarchicalResidualConflict;
""",
        ),
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    tasks_path = out_dir / "tasks.jsonl"
    tasks_path.write_text(
        "".join(json.dumps(task, sort_keys=True) + "\n" for task in tasks),
        encoding="utf-8",
    )
    family_counts = Counter(str(task["registry_family"]) for task in tasks)
    summary = {
        "version": "v0.73.4",
        "analysis_scope": "structural_ambiguity_variant_build",
        "status": "PASS",
        "artifact_complete": True,
        "task_count": len(tasks),
        "tasks_path": str(tasks_path),
        "family_counts": dict(sorted(family_counts.items())),
        "case_ids": [str(task["case_id"]) for task in tasks],
        "scope_note": (
            "Variants extend the two budget-sensitive v0.72 patterns. They require admission, baseline, and "
            "budget calibration before benchmark use."
        ),
    }
    write_json(out_dir / "summary.json", summary)
    return summary


def build_second_generation_structural_ambiguity_variants(
    *,
    out_dir: Path = DEFAULT_SECOND_GEN_OUT_DIR,
) -> dict[str, Any]:
    tasks = [
        _task(
            case_id="projection_closure_01_four_state_two_observer_rank_loss",
            family="projection_closure_rank_loss",
            title="Repair four-state two-observer rank loss",
            description=(
                "A projection workflow exposes two observer signals from four latent states. Restore a compileable "
                "and simulatable model while preserving both observer signals and the latent-state workflow."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep the four latent states.",
                "Preserve both observer outputs.",
                "Do not collapse the latent-state workflow into direct observer assignments.",
            ],
            initial_model="""
model ProjectionClosureFourStateTwoObserverRankLoss
  Real state[4];
  Real total;
  Real weighted;
  Real observerA;
  Real observerB;
equation
  state[1] + state[2] + state[3] + state[4] = 1 + time;
  2 * state[1] + 2 * state[2] + 2 * state[3] + 2 * state[4] = 2 + 2 * time;
  total = state[1] + state[2] + state[3] + state[4];
  weighted = state[1] + 2 * state[2] + 3 * state[3] + 4 * state[4];
  observerA = state[1] - state[3];
  observerB = state[2] - state[4];
end ProjectionClosureFourStateTwoObserverRankLoss;
""",
        ),
        _task(
            case_id="projection_closure_02_three_state_redundant_summary",
            family="projection_closure_rank_loss",
            title="Repair three-state redundant summary projection",
            description=(
                "A three-state projection was refactored into redundant summary and two independent observations. "
                "Restore a compileable and simulatable model while preserving all observations."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep the three latent states.",
                "Preserve summary, contrast, and skew observations.",
            ],
            initial_model="""
model ProjectionClosureThreeStateRedundantSummary
  Real state[3];
  Real summary;
  Real contrast;
  Real skew;
equation
  state[1] + state[2] + state[3] = 1 + sin(time);
  3 * state[1] + 3 * state[2] + 3 * state[3] = 3 + 3 * sin(time);
  summary = state[1] + state[2] + state[3];
  contrast = state[1] - state[3];
  skew = state[1] - 2 * state[2] + state[3];
end ProjectionClosureThreeStateRedundantSummary;
""",
        ),
        _task(
            case_id="residual_projection_01_two_window_closure_conflict",
            family="residual_projection_closure_conflict",
            title="Repair two-window residual closure conflict",
            description=(
                "A residual projection workflow uses two overlapping windows and one aggregate closure. Restore a "
                "compileable and simulatable model while preserving residual, window, and aggregate signals."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep all residual elements.",
                "Preserve both window outputs and the aggregate output.",
            ],
            initial_model="""
model ResidualProjectionTwoWindowClosureConflict
  Real source[4];
  Real estimate[4];
  Real residual[4];
  Real windowA;
  Real windowB;
  Real aggregate;
equation
  for i in 1:4 loop
    source[i] = i * sin(time);
    estimate[i] = source[i];
  end for;
  residual[1] = source[1] - estimate[1];
  residual[2] = source[2] - estimate[2];
  windowA = residual[1] + residual[2];
  windowB = residual[2] + residual[3];
  aggregate = windowA + windowB + residual[4];
  aggregate = 0;
  windowA = 0;
end ResidualProjectionTwoWindowClosureConflict;
""",
        ),
        _task(
            case_id="residual_projection_02_nested_projection_conflict",
            family="residual_projection_closure_conflict",
            title="Repair nested residual projection conflict",
            description=(
                "A nested residual projection mixes local residual definitions with aggregate closure equations. "
                "Restore a compileable and simulatable model while keeping local and global residual outputs."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep the nested residual projection structure.",
                "Preserve local and global residual outputs.",
            ],
            initial_model="""
model ResidualProjectionNestedProjectionConflict
  Real source[3];
  Real estimate[3];
  Real residual[3];
  Real local[2];
  Real global;
equation
  for i in 1:3 loop
    source[i] = i + cos(time);
    estimate[i] = source[i];
  end for;
  residual[1] = source[1] - estimate[1];
  local[1] = residual[1] + residual[2];
  local[2] = residual[2] + residual[3];
  global = local[1] + local[2];
  global = 0;
  local[1] = 0;
end ResidualProjectionNestedProjectionConflict;
""",
        ),
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    tasks_path = out_dir / "tasks.jsonl"
    tasks_path.write_text(
        "".join(json.dumps(task, sort_keys=True) + "\n" for task in tasks),
        encoding="utf-8",
    )
    family_counts = Counter(str(task["registry_family"]) for task in tasks)
    summary = {
        "version": "v0.74.1",
        "analysis_scope": "second_generation_structural_ambiguity_variant_build",
        "status": "PASS",
        "artifact_complete": True,
        "task_count": len(tasks),
        "tasks_path": str(tasks_path),
        "family_counts": dict(sorted(family_counts.items())),
        "case_ids": [str(task["case_id"]) for task in tasks],
        "construction_hypothesis": (
            "Second-generation variants preserve the need for an additional independent projection/closure "
            "constraint after initial structural diagnosis."
        ),
    }
    write_json(out_dir / "summary.json", summary)
    return summary
