from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "structural_ambiguity_seed_candidates_v0_72_0"


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
        "registry_bundle": "v0.72_structural_ambiguity_candidates",
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
