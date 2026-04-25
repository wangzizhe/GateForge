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
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "staged_residual_pack_v0_22_4"

MODEL_NAME_RE = re.compile(r"\bmodel\s+([A-Za-z_][A-Za-z0-9_]*)\b")


@dataclass(frozen=True)
class StagedMutationAttempt:
    target_text: str
    stage_residuals: list[str]
    changed: bool


@dataclass(frozen=True)
class StagedRecipe:
    pattern_id: str
    workflow_intent: str
    staging_hypothesis: str
    mutator: Callable[[str], StagedMutationAttempt]


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


def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "")).strip("_")
    return cleaned or "Model"


def _insert_before_equation(model_text: str, insertion: str) -> str:
    return re.sub(r"\bequation\b", insertion.rstrip() + "\nequation", model_text, count=1)


def _insert_after_equation(model_text: str, insertion: str) -> str:
    return re.sub(r"\bequation\b", "equation\n" + insertion.rstrip(), model_text, count=1)


def mutate_staged_parameter_and_phantom_residual(model_text: str) -> StagedMutationAttempt:
    pattern = re.compile(
        r"Modelica\.Electrical\.Analog\.Basic\.Resistor\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*R\s*=\s*([^)]+?)\s*\)"
    )
    match = pattern.search(model_text)
    if not match:
        return StagedMutationAttempt(model_text, [], False)
    resistor_name = match.group(1)
    original_resistance = match.group(2).strip()
    mutated = pattern.sub(
        f"Modelica.Electrical.Analog.Basic.Resistor {resistor_name}(R=branchResistance[1])",
        model_text,
        count=1,
    )
    mutated = _insert_before_equation(
        mutated,
        f"  parameter Real branchResistance = {original_resistance};\n  Real stagedLossEstimate;",
    )
    mutated = _insert_after_equation(
        mutated,
        f"  stagedLossEstimate = {resistor_name}.i + stagedLossPhantom;",
    )
    return StagedMutationAttempt(
        mutated,
        [
            "scalar parameter lift leaves an invalid indexed scalar reference",
            "a new diagnostic equation references a residual phantom signal",
            "first repair should fix the scalar/index mismatch before the residual symbol is fully exposed",
        ],
        True,
    )


def mutate_measurement_interface_then_constraint_residual(model_text: str) -> StagedMutationAttempt:
    pattern = re.compile(
        r"Modelica\.Electrical\.Analog\.Sensors\.VoltageSensor\s+([A-Za-z_][A-Za-z0-9_]*)\s*;"
    )
    match = pattern.search(model_text)
    if not match:
        return StagedMutationAttempt(model_text, [], False)
    sensor_name = match.group(1)
    mutated = pattern.sub(
        f"Modelica.Electrical.Analog.Sensors.PowerSensor {sensor_name};",
        model_text,
        count=1,
    )
    mutated = _insert_before_equation(mutated, "  Real stagedPower;")
    mutated = _insert_after_equation(
        mutated,
        f"  stagedPower = {sensor_name}.power;\n  assert(stagedPower < -1.0, \"staged residual constraint should be revisited after interface repair\");",
    )
    return StagedMutationAttempt(
        mutated,
        [
            "measurement interface migration breaks old voltage-sensor connector usage",
            "after interface repair the model still contains an intentionally stale behavioral constraint",
            "high-value screening requires model_check_error followed by simulate or constraint feedback",
        ],
        True,
    )


def mutate_structural_deficit_with_residual_symbol_exposure(model_text: str) -> StagedMutationAttempt:
    connect_pattern = re.compile(r"^\s*connect\(([^;]+)\);\s*$", re.MULTILINE)
    match = connect_pattern.search(model_text)
    if not match:
        return StagedMutationAttempt(model_text, [], False)
    mutated = connect_pattern.sub("  // staged residual removed one connection", model_text, count=1)
    mutated = _insert_before_equation(mutated, "  Real stagedBalanceProbe;")
    mutated = _insert_after_equation(mutated, "  stagedBalanceProbe = stagedResidualSymbol;")
    return StagedMutationAttempt(
        mutated,
        [
            "one existing connection is removed to create a structural deficit",
            "a residual probe equation references a symbol that is not yet propagated",
            "first repair should reduce structural deficit before the residual symbol becomes decisive",
        ],
        True,
    )


RECIPES = [
    StagedRecipe(
        pattern_id="staged_parameter_and_phantom_residual",
        workflow_intent="partially lift a component parameter while adding a downstream diagnostic signal",
        staging_hypothesis="first repair fixes parameter migration; second repair handles residual phantom signal",
        mutator=mutate_staged_parameter_and_phantom_residual,
    ),
    StagedRecipe(
        pattern_id="measurement_interface_then_behavioral_constraint_residual",
        workflow_intent="migrate a sensor interface while leaving a stale runtime constraint",
        staging_hypothesis="first repair fixes interface; second repair responds to constraint feedback",
        mutator=mutate_measurement_interface_then_constraint_residual,
    ),
    StagedRecipe(
        pattern_id="compound_structural_deficit_with_residual_symbol_exposure",
        workflow_intent="combine a structural connection residual with a downstream residual symbol",
        staging_hypothesis="first repair reduces structural deficit; second repair handles named residual exposure",
        mutator=mutate_structural_deficit_with_residual_symbol_exposure,
    ),
]


def build_staged_residual_candidates(
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
                    "candidate_id": f"v0224_{index:03d}_{recipe.pattern_id}_{_safe_id(model_name)}",
                    "source_model_path": str(source_path),
                    "source_model_name": model_name,
                    "source_viability_status": source_row.get("source_viability_status"),
                    "source_evidence_artifact": source_row.get("source_evidence_artifact"),
                    "source_evidence_case_id": source_row.get("source_evidence_case_id"),
                    "target_model_name": model_name,
                    "target_model_text": attempt.target_text,
                    "mutation_pattern": recipe.pattern_id,
                    "workflow_intent": recipe.workflow_intent,
                    "staging_hypothesis": recipe.staging_hypothesis,
                    "stage_residuals": attempt.stage_residuals,
                    "stage_residual_count": len(attempt.stage_residuals),
                    "target_admission_status": "pending_omc_admission",
                    "benchmark_admission_status": "isolated_staged_residual_candidate_only",
                    "repair_eval_discipline": "agent_llm_omc_only_no_deterministic_repair",
                }
            )
            if len(rows) >= limit:
                return rows
    return rows


def admit_staged_residual_candidate(
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
                "admitted_staged_residual_failure" if admitted else "rejected_target_not_classified"
            ),
        }
    )
    return admitted_row


def summarize_staged_residual_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    admitted = [row for row in rows if row.get("target_admission_status") == "admitted_staged_residual_failure"]
    pattern_counts = Counter(str(row.get("mutation_pattern") or "") for row in rows)
    admitted_pattern_counts = Counter(str(row.get("mutation_pattern") or "") for row in admitted)
    bucket_counts = Counter(str(row.get("target_bucket_id") or "") for row in admitted)
    admission_rate = len(admitted) / len(rows) if rows else 0.0
    min_residuals = min((int(row.get("stage_residual_count") or 0) for row in rows), default=0)
    status = (
        "PASS"
        if len(rows) >= 9 and len(pattern_counts) >= 3 and min_residuals >= 2 and admission_rate >= 0.8
        else "REVIEW"
    )
    return {
        "version": "v0.22.4",
        "status": status,
        "candidate_count": len(rows),
        "admitted_count": len(admitted),
        "rejected_count": len(rows) - len(admitted),
        "admission_pass_rate": round(admission_rate, 6),
        "pattern_counts": dict(sorted(pattern_counts.items())),
        "admitted_pattern_counts": dict(sorted(admitted_pattern_counts.items())),
        "admitted_bucket_counts": dict(sorted(bucket_counts.items())),
        "minimum_stage_residual_count": min_residuals,
        "analysis_scope": "staged_residual_construction_and_omc_admission_only",
        "repair_eval_discipline": "agent_llm_omc_only_no_deterministic_repair",
        "next_action": "run_true_multiturn_screening_with_repair_round_count_gate",
        "conclusion": (
            "staged_residual_candidates_ready_for_true_multiturn_screening"
            if status == "PASS"
            else "staged_residual_candidates_need_review"
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
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "staged_candidates.jsonl").open("w", encoding="utf-8") as fh:
        for row in serializable_rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def run_staged_residual_pack(
    *,
    source_inventory_path: Path = DEFAULT_SOURCE_INVENTORY_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
    limit: int = 12,
    run_check: Callable[[str, str], tuple[bool, str]] = run_check_only_omc,
) -> dict[str, Any]:
    source_inventory = load_jsonl(source_inventory_path)
    candidates = build_staged_residual_candidates(source_inventory, limit=limit)
    rows = [admit_staged_residual_candidate(row, run_check=run_check) for row in candidates]
    summary = summarize_staged_residual_pack(rows)
    write_outputs(out_dir, rows, summary)
    return summary
