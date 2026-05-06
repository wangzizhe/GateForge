from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIFFICULTY = REPO_ROOT / "artifacts" / "full_registry_baseline_v0_70_1_summary" / "case_difficulty.jsonl"
DEFAULT_TASKS = REPO_ROOT / "artifacts" / "full_registry_baseline_v0_70_0" / "tasks.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "benchmark_expansion_v0_71_0"
DEFAULT_NON_CONNECTOR_OUT_DIR = REPO_ROOT / "artifacts" / "non_connector_seed_candidates_v0_71_1"
DEFAULT_HARDER_NON_CONNECTOR_OUT_DIR = REPO_ROOT / "artifacts" / "harder_non_connector_seed_candidates_v0_71_4"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def ease_bucket(row: dict[str, Any]) -> str:
    if row.get("baseline_status") != "easy_or_solved":
        return "not_solved"
    token_used = int(row.get("token_used") or 0)
    candidate_count = int(row.get("candidate_count") or 0)
    if candidate_count <= 2 and token_used <= 32_000:
        return "trivial_or_low_medium"
    if candidate_count <= 4 and token_used <= 64_000:
        return "medium_solved"
    return "expensive_solved"


def infer_easy_reason(task: dict[str, Any], difficulty_row: dict[str, Any]) -> str:
    text = " ".join(
        [
            str(task.get("title") or ""),
            str(task.get("description") or ""),
            " ".join(str(item) for item in task.get("constraints") or []),
        ]
    ).lower()
    model_text = str(task.get("initial_model") or "").lower()
    if "missing equation" in text or "duplicate equation" in text:
        return "localized_equation_edit"
    if "wrong connect" in text or "wrong connector" in text:
        return "localized_connection_edit"
    if "parameter" in text or "conditional" in text or "if " in model_text:
        return "conditional_or_parameter_pattern_too_direct"
    if "replaceable" in text or "partial" in text or "constrainedby" in model_text:
        return "replaceable_contract_pattern_too_direct"
    if "probe" in text or "adapter" in text or "sensor" in text:
        return "probe_or_adapter_pattern_too_direct"
    if int(difficulty_row.get("candidate_count") or 0) <= 2:
        return "few_candidate_direct_fix"
    return "solved_without_clear_boundary"


def build_solved_case_ease_audit(
    *,
    difficulty_path: Path = DEFAULT_DIFFICULTY,
    tasks_path: Path = DEFAULT_TASKS,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    difficulty_rows = load_jsonl(difficulty_path)
    tasks_by_case = {str(row.get("case_id") or ""): row for row in load_jsonl(tasks_path)}
    audit_rows: list[dict[str, Any]] = []
    for row in difficulty_rows:
        case_id = str(row.get("case_id") or "")
        task = tasks_by_case.get(case_id, {})
        bucket = ease_bucket(row)
        reason = infer_easy_reason(task, row) if bucket != "not_solved" else "not_solved"
        audit_rows.append(
            {
                "case_id": case_id,
                "family": str(row.get("family") or ""),
                "baseline_status": str(row.get("baseline_status") or ""),
                "ease_bucket": bucket,
                "easy_reason": reason,
                "candidate_count": int(row.get("candidate_count") or 0),
                "token_used": int(row.get("token_used") or 0),
            }
        )
    bucket_counts = Counter(row["ease_bucket"] for row in audit_rows)
    reason_counts = Counter(row["easy_reason"] for row in audit_rows if row["ease_bucket"] != "not_solved")
    family_bucket_counts: dict[str, dict[str, int]] = defaultdict(dict)
    for row in audit_rows:
        family = row["family"]
        bucket = row["ease_bucket"]
        family_bucket_counts[family][bucket] = family_bucket_counts[family].get(bucket, 0) + 1
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "case_ease_audit.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in audit_rows),
        encoding="utf-8",
    )
    summary = {
        "version": "v0.71.0",
        "analysis_scope": "solved_case_ease_audit",
        "status": "PASS" if audit_rows else "REVIEW",
        "artifact_complete": bool(audit_rows),
        "case_count": len(audit_rows),
        "solved_case_count": sum(1 for row in audit_rows if row["ease_bucket"] != "not_solved"),
        "not_solved_case_count": sum(1 for row in audit_rows if row["ease_bucket"] == "not_solved"),
        "ease_bucket_counts": dict(sorted(bucket_counts.items())),
        "easy_reason_counts": dict(sorted(reason_counts.items())),
        "family_bucket_counts": {
            family: dict(sorted(counts.items())) for family, counts in sorted(family_bucket_counts.items())
        },
        "expensive_solved_case_ids": [
            row["case_id"] for row in audit_rows if row["ease_bucket"] == "expensive_solved"
        ],
        "medium_solved_case_ids": [row["case_id"] for row in audit_rows if row["ease_bucket"] == "medium_solved"],
        "benchmark_layer_recommendation": {
            "trivial_or_low_medium": "regression_sanity_layer",
            "medium_solved": "medium_regression_layer",
            "expensive_solved": "candidate_medium_hard_source_pool",
            "not_solved": "repeatability_or_hard_layer",
        },
        "next_family_targets": [
            "conditional_parameter_structure",
            "replaceable_partial_contract",
            "reusable_contract_adapter",
            "general_model_check_structural",
        ],
    }
    write_json(out_dir / "summary.json", summary)
    return summary


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
        "registry_bundle": "v0.71_non_connector_candidates",
    }


def build_non_connector_seed_candidates(
    *,
    out_dir: Path = DEFAULT_NON_CONNECTOR_OUT_DIR,
) -> dict[str, Any]:
    tasks = [
        _task(
            case_id="cond_param_01_mode_observer_contract",
            family="conditional_parameter_structure",
            title="Repair mode-dependent observer contract",
            description=(
                "A mode-dependent observer refactor was partially applied. Restore a compileable and simulatable "
                "model while preserving both raw and filtered observation paths."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep the mode parameter and both observation variables.",
                "Preserve the observer workflow rather than deleting inactive-path state.",
            ],
            initial_model="""
model CondParamModeObserverContract
  parameter Boolean useFiltered = false;
  Real raw;
  Real filtered;
  Real observed;
equation
  raw = sin(time);
  if useFiltered then
    der(filtered) = raw - filtered;
    observed = filtered;
  else
    observed = raw;
  end if;
end CondParamModeObserverContract;
""",
        ),
        _task(
            case_id="cond_param_02_array_mode_projection",
            family="conditional_parameter_structure",
            title="Repair mode-dependent array projection",
            description=(
                "A mode switch was introduced into an array projection workflow. Restore a compileable and "
                "simulatable model while keeping the array-level observation interface meaningful."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep the array dimensions and mode parameter.",
                "Do not replace the array workflow with a scalar-only shortcut.",
            ],
            initial_model="""
model CondParamArrayModeProjection
  parameter Integer n = 4;
  parameter Boolean fullProjection = false;
  Real branch[n];
  Real observed[n];
equation
  for i in 1:n loop
    branch[i] = i * time;
  end for;
  if fullProjection then
    for i in 1:n loop
      observed[i] = branch[i];
    end for;
  else
    for i in 1:n - 1 loop
      observed[i] = branch[i];
    end for;
  end if;
end CondParamArrayModeProjection;
""",
        ),
        _task(
            case_id="replaceable_partial_01_signal_law_contract",
            family="replaceable_partial_contract",
            title="Repair replaceable signal-law contract",
            description=(
                "A replaceable signal-law abstraction was introduced during a control refactor. Restore a "
                "compileable and simulatable model while preserving the replaceable law boundary."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep the replaceable model and constrained boundary.",
                "Preserve both command and response signals.",
            ],
            initial_model="""
model ReplaceablePartialSignalLawContract
  partial model LawBase
    input Real u;
    output Real y;
  end LawBase;
  model GainLaw
    extends LawBase;
    parameter Real k = 2;
  equation
  end GainLaw;
  replaceable model Law = GainLaw constrainedby LawBase;
  Law law;
  Real command;
  Real response;
equation
  command = sin(time);
  law.u = command;
  response = law.y;
end ReplaceablePartialSignalLawContract;
""",
        ),
        _task(
            case_id="replaceable_partial_02_state_estimator_contract",
            family="replaceable_partial_contract",
            title="Repair replaceable state-estimator contract",
            description=(
                "A replaceable estimator implementation was migrated under a partial contract. Restore a "
                "compileable and simulatable model while keeping the estimator abstraction intact."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep the replaceable estimator implementation.",
                "Preserve the estimated state and residual outputs.",
            ],
            initial_model="""
model ReplaceablePartialStateEstimatorContract
  partial model EstimatorBase
    input Real measurement;
    output Real estimate;
    output Real residual;
  end EstimatorBase;
  model FirstOrderEstimator
    extends EstimatorBase;
    parameter Real alpha = 0.4;
  equation
    estimate = alpha * measurement;
  end FirstOrderEstimator;
  replaceable model Estimator = FirstOrderEstimator constrainedby EstimatorBase;
  Estimator estimator;
  Real measured;
  Real estimate;
  Real residual;
equation
  measured = 1 + sin(time);
  estimator.measurement = measured;
  estimate = estimator.estimate;
  residual = estimator.residual;
end ReplaceablePartialStateEstimatorContract;
""",
        ),
        _task(
            case_id="reusable_adapter_01_dual_output_contract",
            family="reusable_contract_adapter",
            title="Repair reusable dual-output adapter contract",
            description=(
                "A reusable signal adapter was split out of a monitoring workflow. Restore a compileable and "
                "simulatable model while preserving both adapter outputs."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep the reusable adapter component.",
                "Do not remove either adapter output from the workflow.",
            ],
            initial_model="""
model ReusableAdapterDualOutputContract
  model SignalAdapter
    input Real u;
    output Real y;
    output Real dy;
  equation
    y = 2 * u;
  end SignalAdapter;
  SignalAdapter adapter;
  Real command;
  Real scaled;
  Real rate;
equation
  command = sin(time);
  adapter.u = command;
  scaled = adapter.y;
  rate = adapter.dy;
end ReusableAdapterDualOutputContract;
""",
        ),
        _task(
            case_id="reusable_adapter_02_matrix_projection_contract",
            family="reusable_contract_adapter",
            title="Repair reusable matrix projection adapter",
            description=(
                "A reusable projection adapter was introduced for a small matrix signal workflow. Restore a "
                "compileable and simulatable model while keeping the adapter boundary reusable."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep the matrix-shaped adapter interface.",
                "Preserve all projected outputs.",
            ],
            initial_model="""
model ReusableAdapterMatrixProjectionContract
  model MatrixProjection
    input Real u[2,2];
    output Real rowSum[2];
    output Real colSum[2];
  equation
    for i in 1:2 loop
      rowSum[i] = u[i,1] + u[i,2];
    end for;
  end MatrixProjection;
  MatrixProjection projection;
  Real source[2,2];
  Real rowSignal[2];
  Real colSignal[2];
equation
  for i in 1:2 loop
    for j in 1:2 loop
      source[i,j] = i + j * time;
      projection.u[i,j] = source[i,j];
    end for;
    rowSignal[i] = projection.rowSum[i];
    colSignal[i] = projection.colSum[i];
  end for;
end ReusableAdapterMatrixProjectionContract;
""",
        ),
        _task(
            case_id="structural_hierarchy_01_inherited_monitor_contract",
            family="general_model_check_structural",
            title="Repair inherited monitor contract",
            description=(
                "A monitor base class was factored out during a hierarchy refactor. Restore a compileable and "
                "simulatable model while preserving the inherited monitor interface."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep the inheritance structure.",
                "Preserve both inherited monitor outputs.",
            ],
            initial_model="""
model StructuralHierarchyInheritedMonitorContract
  partial model MonitorBase
    input Real u;
    output Real level;
    output Real trend;
  end MonitorBase;
  model BasicMonitor
    extends MonitorBase;
  equation
    level = u;
  end BasicMonitor;
  BasicMonitor monitor;
  Real inputSignal;
  Real levelSignal;
  Real trendSignal;
equation
  inputSignal = sin(time);
  monitor.u = inputSignal;
  levelSignal = monitor.level;
  trendSignal = monitor.trend;
end StructuralHierarchyInheritedMonitorContract;
""",
        ),
        _task(
            case_id="structural_hierarchy_02_arrayed_inherited_projection",
            family="general_model_check_structural",
            title="Repair arrayed inherited projection contract",
            description=(
                "An inherited projection component was arrayed during a hierarchy refactor. Restore a "
                "compileable and simulatable model while preserving the arrayed projection workflow."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep the arrayed inherited component.",
                "Preserve all exported projection signals.",
            ],
            initial_model="""
model StructuralHierarchyArrayedInheritedProjection
  partial model ProjectionBase
    input Real u;
    output Real y;
    output Real quality;
  end ProjectionBase;
  model LinearProjection
    extends ProjectionBase;
    parameter Real gain = 1.5;
  equation
    y = gain * u;
  end LinearProjection;
  LinearProjection projection[3];
  Real source[3];
  Real y[3];
  Real quality[3];
equation
  for i in 1:3 loop
    source[i] = i * sin(time);
    projection[i].u = source[i];
    y[i] = projection[i].y;
    quality[i] = projection[i].quality;
  end for;
end StructuralHierarchyArrayedInheritedProjection;
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
        "version": "v0.71.1",
        "analysis_scope": "non_connector_seed_candidate_build",
        "status": "PASS",
        "artifact_complete": True,
        "task_count": len(tasks),
        "tasks_path": str(tasks_path),
        "family_counts": dict(sorted(family_counts.items())),
        "case_ids": [str(task["case_id"]) for task in tasks],
        "scope_note": (
            "These are candidate benchmark seeds. They require OMC admission and baseline calibration before "
            "they can be used as benchmark evidence."
        ),
    }
    write_json(out_dir / "summary.json", summary)
    return summary


def build_harder_non_connector_seed_candidates(
    *,
    out_dir: Path = DEFAULT_HARDER_NON_CONNECTOR_OUT_DIR,
) -> dict[str, Any]:
    tasks = [
        _task(
            case_id="cond_param_harder_01_nested_mode_estimator_array",
            family="conditional_parameter_structure",
            title="Repair nested mode estimator array",
            description=(
                "A nested mode estimator was arrayed during a workflow refactor. Restore a compileable and "
                "simulatable model while preserving both mode paths and all estimator outputs."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep the nested mode parameters.",
                "Keep all estimator arrays and exported signals.",
                "Do not collapse the workflow to a single scalar signal.",
            ],
            initial_model="""
model CondParamHarderNestedModeEstimatorArray
  parameter Integer n = 3;
  parameter Boolean useDynamic = false;
  parameter Boolean exposeResidual = true;
  Real raw[n];
  Real filtered[n];
  Real estimate[n];
  Real residual[n];
equation
  for i in 1:n loop
    raw[i] = i * sin(time);
    if useDynamic then
      der(filtered[i]) = raw[i] - filtered[i];
      estimate[i] = filtered[i];
    else
      estimate[i] = raw[i];
    end if;
    if exposeResidual then
      residual[i] = raw[i] - estimate[i];
    end if;
  end for;
end CondParamHarderNestedModeEstimatorArray;
""",
        ),
        _task(
            case_id="replaceable_partial_harder_01_arrayed_dual_contract",
            family="replaceable_partial_contract",
            title="Repair arrayed replaceable dual contract",
            description=(
                "A replaceable dual-output law was arrayed under a partial contract. Restore a compileable and "
                "simulatable model while preserving the replaceable boundary and arrayed outputs."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep the replaceable model constrained by the partial base.",
                "Preserve both exported outputs for every array element.",
            ],
            initial_model="""
model ReplaceablePartialHarderArrayedDualContract
  partial model LawBase
    input Real u;
    output Real y;
    output Real quality;
  end LawBase;
  model AffineLaw
    extends LawBase;
    parameter Real gain = 1.5;
    parameter Real bias = 0.2;
  equation
    y = gain * u + bias;
  end AffineLaw;
  replaceable model Law = AffineLaw constrainedby LawBase;
  Law law[4];
  Real command[4];
  Real response[4];
  Real quality[4];
equation
  for i in 1:4 loop
    command[i] = i * sin(time);
    law[i].u = command[i];
    response[i] = law[i].y;
    quality[i] = law[i].quality;
  end for;
end ReplaceablePartialHarderArrayedDualContract;
""",
        ),
        _task(
            case_id="reusable_adapter_harder_01_cascaded_projection_contract",
            family="reusable_contract_adapter",
            title="Repair cascaded reusable projection contract",
            description=(
                "A reusable projection adapter was cascaded through a monitoring workflow. Restore a compileable "
                "and simulatable model while keeping both adapter stages and all exported signals."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep both adapter stages.",
                "Preserve the row, column, and diagnostic projection signals.",
            ],
            initial_model="""
model ReusableAdapterHarderCascadedProjectionContract
  model ProjectionAdapter
    input Real u[2,2];
    output Real rowSum[2];
    output Real colSum[2];
    output Real diagnostic[2];
  equation
    for i in 1:2 loop
      rowSum[i] = u[i,1] + u[i,2];
    end for;
  end ProjectionAdapter;
  ProjectionAdapter first;
  ProjectionAdapter second;
  Real source[2,2];
  Real rowSignal[2];
  Real colSignal[2];
  Real diagnosticSignal[2];
equation
  for i in 1:2 loop
    for j in 1:2 loop
      source[i,j] = i + j * sin(time);
      first.u[i,j] = source[i,j];
      second.u[i,j] = first.rowSum[i] + j;
    end for;
    rowSignal[i] = second.rowSum[i];
    colSignal[i] = second.colSum[i];
    diagnosticSignal[i] = second.diagnostic[i];
  end for;
end ReusableAdapterHarderCascadedProjectionContract;
""",
        ),
        _task(
            case_id="structural_hierarchy_harder_01_redeclare_monitor_array",
            family="general_model_check_structural",
            title="Repair redeclared monitor array hierarchy",
            description=(
                "A monitor hierarchy was redeclared and arrayed during a structural refactor. Restore a "
                "compileable and simulatable model while preserving the inherited monitor contract."
            ),
            constraints=[
                "Keep model name unchanged.",
                "Keep the inherited monitor hierarchy.",
                "Keep the arrayed monitor workflow and all exported quality signals.",
            ],
            initial_model="""
model StructuralHierarchyHarderRedeclareMonitorArray
  partial model MonitorBase
    input Real u;
    output Real level;
    output Real trend;
    output Real quality;
  end MonitorBase;
  model WindowMonitor
    extends MonitorBase;
    parameter Real scale = 1;
  equation
    level = scale * u;
    trend = u - level;
  end WindowMonitor;
  replaceable model Monitor = WindowMonitor constrainedby MonitorBase;
  Monitor monitor[3];
  Real inputSignal[3];
  Real levelSignal[3];
  Real trendSignal[3];
  Real qualitySignal[3];
equation
  for i in 1:3 loop
    inputSignal[i] = i * cos(time);
    monitor[i].u = inputSignal[i];
    levelSignal[i] = monitor[i].level;
    trendSignal[i] = monitor[i].trend;
    qualitySignal[i] = monitor[i].quality;
  end for;
end StructuralHierarchyHarderRedeclareMonitorArray;
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
        "version": "v0.71.4",
        "analysis_scope": "harder_non_connector_seed_candidate_build",
        "status": "PASS",
        "artifact_complete": True,
        "task_count": len(tasks),
        "tasks_path": str(tasks_path),
        "family_counts": dict(sorted(family_counts.items())),
        "case_ids": [str(task["case_id"]) for task in tasks],
        "scope_note": (
            "These candidates intentionally increase contract breadth within one workflow refactor. They still "
            "require admission and baseline calibration before benchmark use."
        ),
    }
    write_json(out_dir / "summary.json", summary)
    return summary
