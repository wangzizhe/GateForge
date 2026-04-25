from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from gateforge.agent_modelica_generation_audit_v0_19_60 import classify_generation_failure
from gateforge.agent_modelica_staged_residual_pack_v0_22_4 import (
    DEFAULT_SOURCE_INVENTORY_PATH,
    extract_model_name,
    load_jsonl,
)
from gateforge.experiment_runner_shared import run_check_only_omc


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "single_point_complex_pack_v0_22_6"

RESISTOR_RE = re.compile(
    r"Modelica\.Electrical\.Analog\.Basic\.Resistor\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*R\s*=\s*([^)]+?)\s*\)"
)


@dataclass(frozen=True)
class SinglePointMutationAttempt:
    target_text: str
    refactor_scope: str
    residual_chain: list[str]
    changed: bool


def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "")).strip("_")
    return cleaned or "Model"


def _insert_before_equation(model_text: str, insertion: str) -> str:
    return re.sub(r"\bequation\b", insertion.rstrip() + "\nequation", model_text, count=1)


def _insert_after_equation(model_text: str, insertion: str) -> str:
    return re.sub(r"\bequation\b", "equation\n" + insertion.rstrip(), model_text, count=1)


def source_complexity_class(model_text: str) -> str:
    component_count = len(re.findall(r"Modelica\.Electrical\.Analog\.", model_text))
    if component_count >= 10:
        return "large"
    if component_count >= 6:
        return "medium"
    return "small"


def mutate_single_point_resistor_observability_refactor(model_text: str) -> SinglePointMutationAttempt:
    match = RESISTOR_RE.search(model_text)
    if not match:
        return SinglePointMutationAttempt(model_text, "", [], False)
    resistor_name = match.group(1)
    original_resistance = match.group(2).strip()
    refactor_scope = f"{resistor_name}_observability_refactor"
    mutated = RESISTOR_RE.sub(
        f"Modelica.Electrical.Analog.Basic.Resistor {resistor_name}(R={resistor_name}Resistance[1])",
        model_text,
        count=1,
    )
    mutated = _insert_before_equation(
        mutated,
        (
            f"  parameter Real {resistor_name}Resistance = {original_resistance};\n"
            f"  Real {resistor_name}ResidualCurrent;"
        ),
    )
    mutated = _insert_after_equation(
        mutated,
        f"  {resistor_name}ResidualCurrent = {resistor_name}.i + {resistor_name}ResidualProbe;",
    )
    return SinglePointMutationAttempt(
        target_text=mutated,
        refactor_scope=refactor_scope,
        residual_chain=[
            "the same resistor refactor changes a scalar parameter into an indexed access",
            "the same resistor refactor adds an observability residual that references a missing probe",
            "a useful repair should need at least two LLM-applied patches rather than one patch plus validation",
        ],
        changed=True,
    )


def build_single_point_complex_candidates(
    source_inventory: list[dict[str, Any]],
    *,
    limit: int = 8,
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
        attempt = mutate_single_point_resistor_observability_refactor(source_text)
        if not attempt.changed:
            continue
        index = len(rows) + 1
        rows.append(
            {
                "candidate_id": f"v0226_{index:03d}_single_point_resistor_observability_{_safe_id(model_name)}",
                "source_model_path": str(source_path),
                "source_model_name": model_name,
                "source_complexity_class": source_complexity_class(source_text),
                "source_viability_status": source_row.get("source_viability_status"),
                "source_evidence_artifact": source_row.get("source_evidence_artifact"),
                "source_evidence_case_id": source_row.get("source_evidence_case_id"),
                "target_model_name": model_name,
                "target_model_text": attempt.target_text,
                "mutation_pattern": "single_point_resistor_observability_refactor",
                "single_point_refactor_scope": attempt.refactor_scope,
                "residual_chain": attempt.residual_chain,
                "residual_count": len(attempt.residual_chain),
                "residual_coupling_rationale": (
                    "all introduced failures are tied to one resistor observability refactor, "
                    "not to unrelated component or connection edits"
                ),
                "target_admission_status": "pending_omc_admission",
                "benchmark_admission_status": "isolated_single_point_complex_candidate_only",
                "repair_eval_discipline": "agent_llm_omc_only_no_deterministic_repair",
            }
        )
        if len(rows) >= limit:
            return rows
    return rows


def admit_single_point_complex_candidate(
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
                "admitted_single_point_complex_failure" if admitted else "rejected_target_not_classified"
            ),
        }
    )
    return admitted_row


def summarize_single_point_complex_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    admitted = [row for row in rows if row.get("target_admission_status") == "admitted_single_point_complex_failure"]
    bucket_counts = Counter(str(row.get("target_bucket_id") or "") for row in admitted)
    complexity_counts = Counter(str(row.get("source_complexity_class") or "") for row in rows)
    residual_min = min((int(row.get("residual_count") or 0) for row in rows), default=0)
    admission_rate = len(admitted) / len(rows) if rows else 0.0
    status = "PASS" if len(rows) >= 6 and residual_min >= 2 and admission_rate >= 0.8 else "REVIEW"
    return {
        "version": "v0.22.6",
        "status": status,
        "candidate_count": len(rows),
        "admitted_count": len(admitted),
        "rejected_count": len(rows) - len(admitted),
        "admission_pass_rate": round(admission_rate, 6),
        "mutation_pattern": "single_point_resistor_observability_refactor",
        "source_complexity_counts": dict(sorted(complexity_counts.items())),
        "admitted_bucket_counts": dict(sorted(bucket_counts.items())),
        "minimum_residual_count": residual_min,
        "analysis_scope": "single_point_complex_refactor_construction_and_omc_admission_only",
        "repair_eval_discipline": "agent_llm_omc_only_no_deterministic_repair",
        "next_action": "run_true_multiturn_screening_with_repair_round_count_gate",
        "conclusion": (
            "single_point_complex_candidates_ready_for_true_multiturn_screening"
            if status == "PASS"
            else "single_point_complex_candidates_need_review"
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
    with (out_dir / "single_point_candidates.jsonl").open("w", encoding="utf-8") as fh:
        for row in serializable_rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def run_single_point_complex_pack(
    *,
    source_inventory_path: Path = DEFAULT_SOURCE_INVENTORY_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
    limit: int = 8,
    run_check: Callable[[str, str], tuple[bool, str]] = run_check_only_omc,
) -> dict[str, Any]:
    source_inventory = load_jsonl(source_inventory_path)
    candidates = build_single_point_complex_candidates(source_inventory, limit=limit)
    rows = [admit_single_point_complex_candidate(row, run_check=run_check) for row in candidates]
    summary = summarize_single_point_complex_pack(rows)
    write_outputs(out_dir, rows, summary)
    return summary
