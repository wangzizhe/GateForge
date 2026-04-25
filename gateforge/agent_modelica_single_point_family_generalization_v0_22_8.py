from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from gateforge.agent_modelica_generation_audit_v0_19_60 import classify_generation_failure
from gateforge.agent_modelica_single_point_complex_pack_v0_22_6 import (
    _insert_after_equation,
    _insert_before_equation,
    _safe_id,
    source_complexity_class,
)
from gateforge.agent_modelica_staged_residual_pack_v0_22_4 import (
    DEFAULT_SOURCE_INVENTORY_PATH,
    extract_model_name,
    load_jsonl,
)
from gateforge.experiment_runner_shared import run_check_only_omc


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "single_point_family_generalization_v0_22_8"

CAPACITOR_RE = re.compile(
    r"Modelica\.Electrical\.Analog\.Basic\.Capacitor\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*C\s*=\s*([^)]+?)\s*\)"
)
VOLTAGE_SENSOR_RE = re.compile(
    r"Modelica\.Electrical\.Analog\.Sensors\.VoltageSensor\s+([A-Za-z_][A-Za-z0-9_]*)\s*;"
)
SOURCE_RE = re.compile(
    r"Modelica\.Electrical\.Analog\.Sources\.(ConstantVoltage|StepVoltage|SineVoltage)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^;]+?)\)"
)


@dataclass(frozen=True)
class FamilyMutationAttempt:
    target_text: str
    mutation_pattern: str
    refactor_scope: str
    residual_chain: list[str]
    changed: bool


def mutate_capacitor_observability_refactor(model_text: str) -> FamilyMutationAttempt:
    match = CAPACITOR_RE.search(model_text)
    if not match:
        return FamilyMutationAttempt(model_text, "", "", [], False)
    capacitor_name = match.group(1)
    original_capacitance = match.group(2).strip()
    mutated = CAPACITOR_RE.sub(
        f"Modelica.Electrical.Analog.Basic.Capacitor {capacitor_name}(C={capacitor_name}Capacitance[1])",
        model_text,
        count=1,
    )
    mutated = _insert_before_equation(
        mutated,
        (
            f"  parameter Real {capacitor_name}Capacitance = {original_capacitance};\n"
            f"  Real {capacitor_name}ResidualCharge;"
        ),
    )
    mutated = _insert_after_equation(
        mutated,
        f"  {capacitor_name}ResidualCharge = {capacitor_name}.v + {capacitor_name}ResidualProbe;",
    )
    return FamilyMutationAttempt(
        mutated,
        "single_point_capacitor_observability_refactor",
        f"{capacitor_name}_observability_refactor",
        [
            "the same capacitor refactor changes a scalar capacitance parameter into an indexed access",
            "the same capacitor refactor adds a residual observation equation with a missing probe",
            "the residuals are tied to one capacitor observability workflow",
        ],
        True,
    )


def mutate_sensor_output_abstraction_refactor(model_text: str) -> FamilyMutationAttempt:
    match = VOLTAGE_SENSOR_RE.search(model_text)
    if not match:
        return FamilyMutationAttempt(model_text, "", "", [], False)
    sensor_name = match.group(1)
    mutated = VOLTAGE_SENSOR_RE.sub(
        f"Modelica.Electrical.Analog.Sensors.VoltageSensor {sensor_name};",
        model_text,
        count=1,
    )
    mutated = _insert_before_equation(
        mutated,
        f"  parameter Real {sensor_name}Scale = 1.0;\n  Real {sensor_name}AbstractedSignal;",
    )
    mutated = _insert_after_equation(
        mutated,
        f"  {sensor_name}AbstractedSignal = {sensor_name}Scale[1] * {sensor_name}.value + {sensor_name}ResidualProbe;",
    )
    return FamilyMutationAttempt(
        mutated,
        "single_point_sensor_output_abstraction_refactor",
        f"{sensor_name}_output_abstraction_refactor",
        [
            "the same sensor refactor introduces an indexed scalar gain",
            "the same sensor refactor uses an invalid generic sensor output field",
            "the same sensor refactor leaves a missing residual probe in the abstracted signal",
        ],
        True,
    )


def mutate_source_parameterization_refactor(model_text: str) -> FamilyMutationAttempt:
    match = SOURCE_RE.search(model_text)
    if not match:
        return FamilyMutationAttempt(model_text, "", "", [], False)
    source_type = match.group(1)
    source_name = match.group(2)
    args = match.group(3)
    mutated_args = re.sub(r"\bV\s*=\s*([^,\)]+)", f"V={source_name}Voltage[1]", args, count=1)
    if mutated_args == args:
        return FamilyMutationAttempt(model_text, "", "", [], False)
    mutated = SOURCE_RE.sub(
        f"Modelica.Electrical.Analog.Sources.{source_type} {source_name}({mutated_args})",
        model_text,
        count=1,
    )
    voltage_match = re.search(r"\bV\s*=\s*([^,\)]+)", args)
    original_voltage = voltage_match.group(1).strip() if voltage_match else "1.0"
    mutated = _insert_before_equation(
        mutated,
        f"  parameter Real {source_name}Voltage = {original_voltage};\n  Real {source_name}ResidualDrive;",
    )
    mutated = _insert_after_equation(
        mutated,
        f"  {source_name}ResidualDrive = {source_name}.v + {source_name}ResidualProbe;",
    )
    return FamilyMutationAttempt(
        mutated,
        "single_point_source_parameterization_refactor",
        f"{source_name}_parameterization_refactor",
        [
            "the same voltage source refactor changes scalar voltage parameterization into an indexed access",
            "the same source refactor adds a residual drive equation with a missing probe",
            "the residuals are tied to one source parameterization workflow",
        ],
        True,
    )


MUTATORS: list[Callable[[str], FamilyMutationAttempt]] = [
    mutate_capacitor_observability_refactor,
    mutate_sensor_output_abstraction_refactor,
    mutate_source_parameterization_refactor,
]


def build_family_generalization_candidates(
    source_inventory: list[dict[str, Any]],
    *,
    per_family_limit: int = 3,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    family_counts: Counter[str] = Counter()
    usable_sources = [row for row in source_inventory if row.get("source_viability_status")]
    for source_row in usable_sources:
        source_path = Path(str(source_row.get("source_model_path") or ""))
        if not source_path.exists():
            continue
        source_text = source_path.read_text(encoding="utf-8")
        model_name = extract_model_name(source_text) or str(source_row.get("source_model_name") or "")
        if not model_name:
            continue
        for mutator in MUTATORS:
            attempt = mutator(source_text)
            if not attempt.changed or family_counts[attempt.mutation_pattern] >= per_family_limit:
                continue
            family_counts[attempt.mutation_pattern] += 1
            index = len(rows) + 1
            rows.append(
                {
                    "candidate_id": (
                        f"v0228_{index:03d}_{attempt.mutation_pattern}_{_safe_id(model_name)}"
                    ),
                    "source_model_path": str(source_path),
                    "source_model_name": model_name,
                    "source_complexity_class": source_complexity_class(source_text),
                    "source_viability_status": source_row.get("source_viability_status"),
                    "source_evidence_artifact": source_row.get("source_evidence_artifact"),
                    "source_evidence_case_id": source_row.get("source_evidence_case_id"),
                    "target_model_name": model_name,
                    "target_model_text": attempt.target_text,
                    "mutation_pattern": attempt.mutation_pattern,
                    "single_point_refactor_scope": attempt.refactor_scope,
                    "residual_chain": attempt.residual_chain,
                    "residual_count": len(attempt.residual_chain),
                    "residual_coupling_rationale": (
                        "all introduced failures are tied to one component-level refactor scope"
                    ),
                    "target_admission_status": "pending_omc_admission",
                    "benchmark_admission_status": "isolated_single_point_family_candidate_only",
                    "repair_eval_discipline": "agent_llm_omc_only_no_deterministic_repair",
                }
            )
        if len(family_counts) == len(MUTATORS) and all(count >= per_family_limit for count in family_counts.values()):
            return rows
    return rows


def admit_family_generalization_candidate(
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
                "admitted_single_point_family_failure" if admitted else "rejected_target_not_classified"
            ),
        }
    )
    return admitted_row


def summarize_family_generalization_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    admitted = [row for row in rows if row.get("target_admission_status") == "admitted_single_point_family_failure"]
    pattern_counts = Counter(str(row.get("mutation_pattern") or "") for row in rows)
    admitted_pattern_counts = Counter(str(row.get("mutation_pattern") or "") for row in admitted)
    bucket_counts = Counter(str(row.get("target_bucket_id") or "") for row in admitted)
    admission_rate = len(admitted) / len(rows) if rows else 0.0
    min_residuals = min((int(row.get("residual_count") or 0) for row in rows), default=0)
    status = "PASS" if len(pattern_counts) >= 3 and min_residuals >= 2 and admission_rate >= 0.8 else "REVIEW"
    return {
        "version": "v0.22.8",
        "status": status,
        "candidate_count": len(rows),
        "admitted_count": len(admitted),
        "rejected_count": len(rows) - len(admitted),
        "admission_pass_rate": round(admission_rate, 6),
        "pattern_counts": dict(sorted(pattern_counts.items())),
        "admitted_pattern_counts": dict(sorted(admitted_pattern_counts.items())),
        "admitted_bucket_counts": dict(sorted(bucket_counts.items())),
        "minimum_residual_count": min_residuals,
        "analysis_scope": "single_point_complex_family_generalization_admission",
        "repair_eval_discipline": "agent_llm_omc_only_no_deterministic_repair",
        "next_action": "run_live_screening_per_family_with_true_multiturn_gate",
        "conclusion": (
            "single_point_family_generalization_ready_for_live_screening"
            if status == "PASS"
            else "single_point_family_generalization_needs_review"
        ),
    }


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
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "single_point_family_candidates.jsonl").open("w", encoding="utf-8") as fh:
        for row in serializable_rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def run_family_generalization_pack(
    *,
    source_inventory_path: Path = DEFAULT_SOURCE_INVENTORY_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
    per_family_limit: int = 3,
    run_check: Callable[[str, str], tuple[bool, str]] = run_check_only_omc,
) -> dict[str, Any]:
    source_inventory = load_jsonl(source_inventory_path)
    candidates = build_family_generalization_candidates(source_inventory, per_family_limit=per_family_limit)
    rows = [admit_family_generalization_candidate(row, run_check=run_check) for row in candidates]
    summary = summarize_family_generalization_pack(rows)
    write_outputs(out_dir, rows, summary)
    return summary
