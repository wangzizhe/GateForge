from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from gateforge.agent_modelica_generation_audit_v0_19_60 import classify_generation_failure
from gateforge.experiment_runner_shared import run_check_only_omc


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_INVENTORY_PATH = (
    REPO_ROOT / "artifacts" / "source_backed_family_pack_v0_21_5" / "source_inventory.jsonl"
)
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "engineering_mutation_probe_v0_22_0"

MODEL_NAME_RE = re.compile(r"\bmodel\s+([A-Za-z_][A-Za-z0-9_]*)\b")


@dataclass(frozen=True)
class MutationAttempt:
    target_text: str
    impact_points: list[str]
    changed: bool


@dataclass(frozen=True)
class MutationRecipe:
    pattern_id: str
    workflow_intent: str
    residual_shape: str
    mutator: Callable[[str], MutationAttempt]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def extract_model_name(model_text: str) -> str:
    match = MODEL_NAME_RE.search(str(model_text or ""))
    return "" if not match else match.group(1)


def _insert_before_equation(model_text: str, insertion: str) -> str:
    return re.sub(r"\bequation\b", insertion.rstrip() + "\nequation", model_text, count=1)


def _insert_after_equation(model_text: str, insertion: str) -> str:
    return re.sub(r"\bequation\b", "equation\n" + insertion.rstrip(), model_text, count=1)


def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "")).strip("_")
    return cleaned or "Model"


def mutate_measurement_abstraction_residual(model_text: str) -> MutationAttempt:
    pattern = re.compile(
        r"Modelica\.Electrical\.Analog\.Sensors\.VoltageSensor\s+([A-Za-z_][A-Za-z0-9_]*)\s*;"
    )
    match = pattern.search(model_text)
    if not match:
        return MutationAttempt(model_text, [], False)
    sensor_name = match.group(1)
    mutated = pattern.sub(
        f"Modelica.Electrical.Analog.Sensors.PowerSensor {sensor_name};",
        model_text,
        count=1,
    )
    mutated = _insert_before_equation(mutated, "  Real aggregatePower;")
    mutated = _insert_after_equation(mutated, f"  aggregatePower = {sensor_name}.power;")
    return MutationAttempt(
        mutated,
        [
            "measurement component was migrated from voltage sensing to aggregate power sensing",
            "old two-pin voltage sensor connections remain attached to the new component",
            "new aggregate signal references an interface that the old validation target did not require",
            "validation target still names the original measurement variable family",
        ],
        True,
    )


def mutate_conditional_measurement_residual(model_text: str) -> MutationAttempt:
    pattern = re.compile(
        r"Modelica\.Electrical\.Analog\.Sensors\.VoltageSensor\s+([A-Za-z_][A-Za-z0-9_]*)\s*;"
    )
    match = pattern.search(model_text)
    if not match:
        return MutationAttempt(model_text, [], False)
    sensor_name = match.group(1)
    optional_sensor_name = f"{sensor_name}Optional"
    mutated = pattern.sub(
        f"Modelica.Electrical.Analog.Sensors.VoltageSensor {optional_sensor_name} if enableMeasurement;",
        model_text,
        count=1,
    )
    mutated = _insert_before_equation(
        mutated,
        "  parameter Boolean enableMeasurement = false;\n  Real optionalMeasurement;",
    )
    mutated = _insert_after_equation(mutated, f"  optionalMeasurement = {optional_sensor_name}.v + measurementBias;")
    return MutationAttempt(
        mutated,
        [
            "measurement subsystem was made optional and renamed during the migration",
            "existing connect equations still reference the pre-migration component name",
            "new reporting equation references the renamed conditional component",
            "new reporting equation also references an unpropagated calibration bias",
        ],
        True,
    )


def mutate_parameter_lift_residual(model_text: str) -> MutationAttempt:
    pattern = re.compile(
        r"Modelica\.Electrical\.Analog\.Basic\.Resistor\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*R\s*=\s*([^)]+?)\s*\)"
    )
    match = pattern.search(model_text)
    if not match:
        return MutationAttempt(model_text, [], False)
    resistor_name = match.group(1)
    original_resistance = match.group(2).strip()
    mutated = pattern.sub(
        f"Modelica.Electrical.Analog.Basic.Resistor {resistor_name}(R=branchResistance[1])",
        model_text,
        count=1,
    )
    mutated = _insert_before_equation(
        mutated,
        f"  parameter Real branchResistance = {original_resistance};\n  Real branchLossEstimate;",
    )
    mutated = _insert_after_equation(
        mutated,
        f"  branchLossEstimate = branchResistance[1] * {resistor_name}.i;",
    )
    return MutationAttempt(
        mutated,
        [
            "scalar resistance modifier was partially lifted into a reusable parameter",
            "component modifier now indexes a scalar parameter as if it had been vectorized",
            "new diagnostic equation was added for the refactored branch",
            "diagnostic equation still assumes a component interface that was not reviewed",
        ],
        True,
    )


RECIPES = [
    MutationRecipe(
        pattern_id="measurement_abstraction_residual",
        workflow_intent="migrate a direct voltage measurement into a richer aggregate measurement",
        residual_shape="component_interface_changed_but_old_connections_and_targets_remain",
        mutator=mutate_measurement_abstraction_residual,
    ),
    MutationRecipe(
        pattern_id="conditional_measurement_residual",
        workflow_intent="make a measurement subsystem optional without finishing downstream guards",
        residual_shape="conditional_component_guard_not_propagated_to_connections_or_equations",
        mutator=mutate_conditional_measurement_residual,
    ),
    MutationRecipe(
        pattern_id="parameter_lift_residual",
        workflow_intent="lift a local component modifier into a reusable branch parameter",
        residual_shape="scalar_to_vector_refactor_started_but_not_completed",
        mutator=mutate_parameter_lift_residual,
    ),
]


def build_engineering_mutation_candidates(
    source_inventory: list[dict[str, Any]],
    *,
    limit: int = 12,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    usable_sources = [row for row in source_inventory if row.get("source_viability_status")]
    for source_row in usable_sources:
        source_path = Path(str(source_row.get("source_model_path") or ""))
        if not source_path.exists():
            continue
        source_text = source_path.read_text(encoding="utf-8")
        model_name = extract_model_name(source_text) or str(source_row.get("source_model_name") or "")
        if not model_name:
            continue
        for recipe in RECIPES:
            attempt = recipe.mutator(source_text)
            if not attempt.changed:
                continue
            index = len(rows) + 1
            rows.append(
                {
                    "candidate_id": f"v0220_{index:03d}_{recipe.pattern_id}_{_safe_id(model_name)}",
                    "source_model_path": str(source_path),
                    "source_model_name": model_name,
                    "source_viability_status": source_row.get("source_viability_status"),
                    "source_evidence_artifact": source_row.get("source_evidence_artifact"),
                    "source_evidence_case_id": source_row.get("source_evidence_case_id"),
                    "target_model_name": model_name,
                    "target_model_text": attempt.target_text,
                    "mutation_pattern": recipe.pattern_id,
                    "workflow_intent": recipe.workflow_intent,
                    "residual_shape": recipe.residual_shape,
                    "impact_points": attempt.impact_points,
                    "impact_point_count": len(attempt.impact_points),
                    "target_admission_status": "pending_omc_admission",
                    "benchmark_admission_status": "isolated_engineering_mutation_candidate_only",
                    "repair_eval_discipline": "agent_llm_omc_only_no_deterministic_repair",
                }
            )
            if len(rows) >= limit:
                return rows
    return rows


def admit_engineering_mutation_candidate(
    row: dict[str, Any],
    *,
    run_check: Callable[[str, str], tuple[bool, str]] = run_check_only_omc,
) -> dict[str, Any]:
    model_text = str(row.get("target_model_text") or "")
    if not model_text and row.get("target_model_path"):
        model_text = Path(str(row.get("target_model_path"))).read_text(encoding="utf-8")
    model_name = str(row.get("target_model_name") or row.get("source_model_name") or "")
    check_pass, omc_output = run_check(model_text, model_name)
    classification = classify_generation_failure(
        model_text=model_text,
        model_name=model_name,
        check_pass=bool(check_pass),
        simulate_pass=False,
        omc_output=omc_output,
    )
    bucket_id = str(classification.get("bucket_id") or "")
    admitted = bool(not check_pass and bucket_id not in {"", "PASS", "UNCLASSIFIED"})
    admitted_row = dict(row)
    admitted_row.update(
        {
            "target_check_pass": bool(check_pass),
            "target_bucket_id": bucket_id,
            "target_classification_source": classification.get("classification_source"),
            "target_evidence_excerpt": str(classification.get("evidence_excerpt") or omc_output or "")[:1000],
            "target_admission_status": (
                "admitted_engineering_mutation_failure" if admitted else "rejected_target_not_classified"
            ),
        }
    )
    return admitted_row


def summarize_engineering_mutation_probe(rows: list[dict[str, Any]]) -> dict[str, Any]:
    admitted = [row for row in rows if row.get("target_admission_status") == "admitted_engineering_mutation_failure"]
    pattern_counts = Counter(str(row.get("mutation_pattern") or "") for row in rows)
    admitted_pattern_counts = Counter(str(row.get("mutation_pattern") or "") for row in admitted)
    bucket_counts = Counter(str(row.get("target_bucket_id") or "") for row in admitted)
    impact_floor = min((int(row.get("impact_point_count") or 0) for row in rows), default=0)
    admission_rate = len(admitted) / len(rows) if rows else 0.0
    status = (
        "PASS"
        if len(rows) >= 9 and len(pattern_counts) >= 3 and impact_floor >= 3 and admission_rate >= 0.8
        else "REVIEW"
    )
    return {
        "version": "v0.22.0",
        "status": status,
        "candidate_count": len(rows),
        "admitted_count": len(admitted),
        "rejected_count": len(rows) - len(admitted),
        "admission_pass_rate": round(admission_rate, 6),
        "pattern_counts": dict(sorted(pattern_counts.items())),
        "admitted_pattern_counts": dict(sorted(admitted_pattern_counts.items())),
        "admitted_bucket_counts": dict(sorted(bucket_counts.items())),
        "minimum_impact_point_count": impact_floor,
        "benchmark_admission_status": "isolated_engineering_mutation_candidate_only",
        "repair_eval_discipline": "agent_llm_omc_only_no_deterministic_repair",
        "analysis_scope": "mutation_construction_and_omc_failure_admission_only",
        "next_action": (
            "run_multiturn_repair_screening_on_admitted_engineering_mutations"
            if status == "PASS"
            else "review_engineering_mutation_construction_before_live_screening"
        ),
        "conclusion": (
            "engineering_mutation_candidates_ready_for_multiturn_screening"
            if status == "PASS"
            else "engineering_mutation_candidates_need_review"
        ),
    }


def render_report(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# v0.22.0 Engineering Mutation Probe",
        "",
        f"- status: `{summary.get('status')}`",
        f"- candidate_count: `{summary.get('candidate_count')}`",
        f"- admitted_count: `{summary.get('admitted_count')}`",
        f"- admission_pass_rate: `{summary.get('admission_pass_rate')}`",
        f"- discipline: `{summary.get('repair_eval_discipline')}`",
        "",
        "## Patterns",
    ]
    for pattern, count in (summary.get("pattern_counts") or {}).items():
        lines.append(f"- `{pattern}`: `{count}`")
    lines.extend(["", "## Admitted Buckets"])
    for bucket, count in (summary.get("admitted_bucket_counts") or {}).items():
        lines.append(f"- `{bucket}`: `{count}`")
    lines.extend(["", "## Candidates"])
    for row in rows:
        lines.append(
            f"- `{row.get('candidate_id')}` pattern=`{row.get('mutation_pattern')}` "
            f"bucket=`{row.get('target_bucket_id')}` status=`{row.get('target_admission_status')}`"
        )
    return "\n".join(lines) + "\n"


def write_outputs(out_dir: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    models_dir = out_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    serializable_rows: list[dict[str, Any]] = []
    for row in rows:
        public_row = dict(row)
        model_text = str(public_row.pop("target_model_text", "") or "")
        model_path = models_dir / f"{row['candidate_id']}.mo"
        if model_text:
            model_path.write_text(model_text, encoding="utf-8")
        public_row["target_model_path"] = str(model_path)
        serializable_rows.append(public_row)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "engineering_candidates.jsonl").open("w", encoding="utf-8") as fh:
        for row in serializable_rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "REPORT.md").write_text(render_report(summary, serializable_rows), encoding="utf-8")


def run_engineering_mutation_probe(
    *,
    source_inventory_path: Path = DEFAULT_SOURCE_INVENTORY_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
    limit: int = 12,
    run_check: Callable[[str, str], tuple[bool, str]] = run_check_only_omc,
) -> dict[str, Any]:
    source_inventory = load_jsonl(source_inventory_path)
    candidates = build_engineering_mutation_candidates(source_inventory, limit=limit)
    rows = [admit_engineering_mutation_candidate(row, run_check=run_check) for row in candidates]
    summary = summarize_engineering_mutation_probe(rows)
    write_outputs(out_dir, rows, summary)
    return summary
