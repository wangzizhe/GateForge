from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_INVENTORY_PATH = (
    REPO_ROOT / "artifacts" / "source_backed_family_pack_v0_21_5" / "source_inventory.jsonl"
)
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "complex_single_root_pack_v0_21_8"

MODEL_NAME_RE = re.compile(r"\bmodel\s+([A-Za-z_][A-Za-z0-9_]*)\b")


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


def mutate_signal_source_migration_partial(model_text: str) -> tuple[str, list[str]]:
    impacts = [
        "source component class changed to signal-driven source",
        "old voltage source modifiers remain on the new component",
        "required signal input is not introduced",
    ]
    mutated = re.sub(
        r"Modelica\.Electrical\.Analog\.Sources\.(ConstantVoltage|StepVoltage)\s+([A-Za-z_][A-Za-z0-9_]*)\(",
        r"Modelica.Electrical.Analog.Sources.SignalVoltage \2(",
        model_text,
        count=1,
    )
    if mutated == model_text:
        return model_text, impacts
    mutated = _insert_before_equation(mutated, "  Real requestedVoltage;")
    mutated = _insert_after_equation(mutated, "  requestedVoltage = commandedVoltage;")
    impacts.append("new control variable references a missing command signal")
    return mutated, impacts


def mutate_measurement_abstraction_partial(model_text: str) -> tuple[str, list[str]]:
    impacts = [
        "measurement concept changed from direct sensor output to aggregate power",
        "aggregate output declaration is added without all supporting signals",
        "old sensor variables remain as mixed direct references",
        "new equation references a missing current measurement",
    ]
    mutated = _insert_before_equation(model_text, "  Real aggregatePower;")
    mutated = _insert_after_equation(
        mutated,
        "  aggregatePower = VS1.v * measuredCurrent;\n  VS1.v = aggregatePower / measuredCurrent;",
    )
    return mutated, impacts


def mutate_namespace_migration_partial(model_text: str) -> tuple[str, list[str]]:
    impacts = [
        "component namespace is migrated to a plausible but incompatible library path",
        "only one declaration family is migrated",
        "old connections and validation targets remain unchanged",
    ]
    mutated = re.sub(
        r"Modelica\.Electrical\.Analog\.Basic\.Resistor",
        "Modelica.Electrical.Analog.Ideal.Resistor",
        model_text,
        count=1,
    )
    if mutated == model_text:
        mutated = _insert_before_equation(mutated, "  Modelica.Electrical.Analog.Ideal.Resistor migratedLoad;")
    return mutated, impacts


PATTERNS = [
    ("signal_source_migration_partial", mutate_signal_source_migration_partial),
    ("measurement_abstraction_partial", mutate_measurement_abstraction_partial),
    ("namespace_migration_partial", mutate_namespace_migration_partial),
]


def build_complex_candidate(source_row: dict[str, Any], *, index: int) -> dict[str, Any]:
    source_path = Path(str(source_row.get("source_model_path") or ""))
    source_text = source_path.read_text(encoding="utf-8")
    model_name = extract_model_name(source_text) or str(source_row.get("source_model_name") or f"Model{index}")
    pattern_id, mutator = PATTERNS[(index - 1) % len(PATTERNS)]
    target_text, impacts = mutator(source_text)
    return {
        "candidate_id": f"v0218_{index:03d}_{pattern_id}_{model_name}",
        "source_model_path": str(source_path),
        "source_model_name": model_name,
        "source_viability_status": source_row.get("source_viability_status"),
        "source_evidence_artifact": source_row.get("source_evidence_artifact"),
        "source_evidence_case_id": source_row.get("source_evidence_case_id"),
        "target_model_name": model_name,
        "target_model_text": target_text,
        "mutation_pattern": pattern_id,
        "root_cause_shape": "single_refactor_intent_with_multiple_consistency_residuals",
        "impact_points": impacts,
        "impact_point_count": len(impacts),
        "benchmark_admission_status": "isolated_complex_single_root_candidate_only",
        "repair_eval_discipline": "agent_llm_omc_only_no_deterministic_repair",
    }


def build_complex_candidates(source_inventory: list[dict[str, Any]], *, limit: int = 9) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    usable = [row for row in source_inventory if row.get("source_viability_status")]
    for index, source_row in enumerate(usable[:limit], start=1):
        candidates.append(build_complex_candidate(source_row, index=index))
    return candidates


def summarize_complex_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_pattern = Counter(str(row.get("mutation_pattern") or "") for row in rows)
    min_impact = min((int(row.get("impact_point_count") or 0) for row in rows), default=0)
    status = "PASS" if len(rows) >= 6 and min_impact >= 3 and len(by_pattern) >= 3 else "REVIEW"
    return {
        "version": "v0.21.8",
        "status": status,
        "candidate_count": len(rows),
        "pattern_counts": dict(sorted(by_pattern.items())),
        "minimum_impact_point_count": min_impact,
        "benchmark_admission_status": "isolated_complex_single_root_candidate_only",
        "repair_eval_discipline": "agent_llm_omc_only_no_deterministic_repair",
        "next_action": "omc_admit_complex_single_root_targets",
        "conclusion": (
            "complex_single_root_candidate_pack_ready_for_omc_admission"
            if status == "PASS"
            else "complex_single_root_candidate_pack_needs_review"
        ),
    }


def write_outputs(out_dir: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    models_dir = out_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    public_rows: list[dict[str, Any]] = []
    for row in rows:
        model_path = models_dir / f"{row['candidate_id']}.mo"
        model_path.write_text(str(row.get("target_model_text") or ""), encoding="utf-8")
        public_row = dict(row)
        public_row.pop("target_model_text", None)
        public_row["target_model_path"] = str(model_path)
        public_rows.append(public_row)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "complex_candidates.jsonl").open("w", encoding="utf-8") as fh:
        for row in public_rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def run_complex_single_root_pack(
    *,
    source_inventory_path: Path = DEFAULT_SOURCE_INVENTORY_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
    limit: int = 9,
) -> dict[str, Any]:
    source_inventory = load_jsonl(source_inventory_path)
    rows = build_complex_candidates(source_inventory, limit=limit)
    summary = summarize_complex_pack(rows)
    write_outputs(out_dir, rows, summary)
    return summary
