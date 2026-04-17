"""
Build GateForge Benchmark v1 — the first clean, correctly-designed benchmark.

Design principles:
  - All mutations derived from real Modelica engineering errors
  - Error layer taxonomy:
      Layer 2 (structural-observable): OMC gives symptom (count) but not fix location
      Layer 3 (behavioral-only):       OMC passes; failure only visible via behavioral oracle
  - failure_type labels are correct from the start
  - No heuristic-solvable cases
  - No artificial injection markers (no gateforge_undef_trigger, no assert(false,...) tags)

Sources:
  - 12 overdetermined KVL/KCL cases (v0.19.11)          — error_layer=2
  - 11 underdetermined missing-ground cases (v0.19.12)   — error_layer=2
  -  8 semantic RC time-constant cases (v0.19.15)        — error_layer=3
  - 11 spurious short-circuit cases (v0.19.14)           — error_layer=2
  -  5 two-layer compound cases (v0.19.18)               — error_layer=2
  -  5 three-layer compound cases (v0.19.19)             — error_layer=2
  -  5 four-layer compound cases (v0.19.20)              — error_layer=2

Output:
  artifacts/benchmark_gf_v1/admitted_cases.jsonl
  artifacts/benchmark_gf_v1/summary.json
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "artifacts" / "benchmark_gf_v1"

# Source JSONLs — all correctly designed and admission-verified
OVERDET_JSONL = (
    REPO_ROOT / "artifacts" / "overdetermined_mutations_v0_19_11" / "admitted_cases.jsonl"
)
UNDERDET_JSONL = (
    REPO_ROOT / "artifacts" / "underdetermined_mutations_v0_19_12" / "admitted_cases.jsonl"
)
SEMANTIC_JSONL = (
    REPO_ROOT / "artifacts" / "semantic_reasoning_mutations_v0_19_15" / "admitted_cases.jsonl"
)
SHORTCIRC_JSONL = (
    REPO_ROOT / "artifacts" / "spurious_short_circuit_mutations_v0_19_14" / "admitted_cases.jsonl"
)
COMPOUND2_JSONL = (
    REPO_ROOT / "artifacts" / "compound_mutation_v0_19_18" / "admitted_cases.jsonl"
)
COMPOUND3_JSONL = (
    REPO_ROOT / "artifacts" / "triple_compound_mutation_v0_19_19" / "admitted_cases.jsonl"
)
COMPOUND4_JSONL = (
    REPO_ROOT / "artifacts" / "quad_compound_mutation_v0_19_20" / "admitted_cases.jsonl"
)

# Canonical benchmark_family names
FAMILY_OVERDET_KVL = "overdetermined_kvl"
FAMILY_OVERDET_KCL = "overdetermined_kcl"
FAMILY_UNDERDET_GROUND = "underdetermined_missing_ground"
FAMILY_SEMANTIC_TAU = "semantic_time_constant"
FAMILY_SHORTCIRC = "spurious_short_circuit"
FAMILY_COMPOUND2 = "compound_two_layer"
FAMILY_COMPOUND3 = "compound_three_layer"
FAMILY_COMPOUND4 = "compound_four_layer"


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _normalise_overdet(row: dict) -> dict:
    """Normalise an overdetermined case to the gf_v1 unified schema."""
    relation_id = str(row.get("overdetermined_relation_id") or row.get("relation_id") or "")
    if "kcl" in relation_id:
        family = FAMILY_OVERDET_KCL
        mutation_mechanism = "redundant_kcl_equation"
    else:
        family = FAMILY_OVERDET_KVL
        mutation_mechanism = "redundant_kvl_equation"

    return {
        "candidate_id": row["candidate_id"],
        "task_id": row["candidate_id"],
        "benchmark_version": "gf_v1",
        "benchmark_family": family,
        "error_layer": 2,
        "mutation_mechanism": mutation_mechanism,
        "failure_type": "constraint_violation",
        "expected_stage": "simulate",
        "source_model_path": row["source_model_path"],
        "mutated_model_path": row["mutated_model_path"],
        "workflow_goal": str(row.get("workflow_goal") or
            "Remove the redundant structural relation while preserving the source electrical model."),
        "requires_semantic_reasoning": False,
        "omc_localizes_fix": False,
        "admission_verified": True,
        "planner_backend": "gemini",
        "backend": "openmodelica_docker",
        # preserve provenance
        "_source_version": "v0.19.11",
        "_relation_id": relation_id,
        "_redundant_equation": str(row.get("redundant_relation_equation") or ""),
    }


def _normalise_underdet(row: dict) -> dict:
    """Normalise an underdetermined case to the gf_v1 unified schema."""
    return {
        "candidate_id": row["candidate_id"],
        "task_id": row["candidate_id"],
        "benchmark_version": "gf_v1",
        "benchmark_family": FAMILY_UNDERDET_GROUND,
        "error_layer": 2,
        "mutation_mechanism": "missing_ground_reference",
        "failure_type": "constraint_violation",
        "expected_stage": "simulate",
        "source_model_path": row["source_model_path"],
        "mutated_model_path": row["mutated_model_path"],
        "workflow_goal": str(row.get("workflow_goal") or
            "Restore the missing ground connections so the circuit has an absolute "
            "potential reference, while preserving all other circuit elements."),
        "requires_semantic_reasoning": False,
        "omc_localizes_fix": False,
        "admission_verified": True,
        "planner_backend": "gemini",
        "backend": "openmodelica_docker",
        # preserve provenance
        "_source_version": "v0.19.12",
        "_relation_id": str(row.get("underdetermined_relation_id") or ""),
        "_removed_ground_connects": list(row.get("removed_ground_connects") or []),
    }


def _normalise_semantic(row: dict) -> dict:
    """Normalise a semantic reasoning case to the gf_v1 unified schema."""
    return {
        "candidate_id": row["candidate_id"],
        "task_id": row["candidate_id"],
        "benchmark_version": "gf_v1",
        "benchmark_family": FAMILY_SEMANTIC_TAU,
        "error_layer": 3,
        "mutation_mechanism": "wrong_semantic_parameter_value",
        "failure_type": str(row.get("failure_type") or "behavioral_contract_fail"),
        "expected_stage": "simulate",
        "source_model_path": row["source_model_path"],
        "mutated_model_path": row["mutated_model_path"],
        "workflow_goal": str(row.get("workflow_goal") or ""),
        "requires_semantic_reasoning": True,
        "omc_localizes_fix": False,
        "admission_verified": True,
        "planner_backend": "gemini",
        "backend": "openmodelica_docker",
        # preserve provenance
        "_source_version": "v0.19.15",
        "_semantic_oracle": row.get("semantic_oracle", {}),
    }


def _normalise_shortcirc(row: dict) -> dict:
    """Normalise a spurious short-circuit case to the gf_v1 unified schema."""
    return {
        "candidate_id": row["candidate_id"],
        "task_id": row["candidate_id"],
        "benchmark_version": "gf_v1",
        "benchmark_family": FAMILY_SHORTCIRC,
        "error_layer": 2,
        "mutation_mechanism": "spurious_short_circuit_connect",
        "failure_type": "constraint_violation",
        "expected_stage": "simulate",
        "source_model_path": row["source_model_path"],
        "mutated_model_path": row["mutated_model_path"],
        "workflow_goal": str(row.get("workflow_goal") or
            "Remove the spurious connect() that short-circuits the primary voltage "
            "source to ground, while preserving all other circuit connections."),
        "requires_semantic_reasoning": False,
        "omc_localizes_fix": False,
        "admission_verified": True,
        "planner_backend": "gemini",
        "backend": "openmodelica_docker",
        # preserve provenance
        "_source_version": "v0.19.14",
        "_relation_id": str(row.get("short_circuit_relation_id") or ""),
        "_injected_connect": str(row.get("injected_connect") or ""),
    }


def _normalise_compound(row: dict, *, depth: int) -> dict:
    """Normalise a compound family case to the gf_v1 unified schema."""
    if depth == 2:
        family = FAMILY_COMPOUND2
        mutation_mechanism = "compound_missing_ground_plus_wrong_capacitance"
        source_version = "v0.19.18"
    elif depth == 3:
        family = FAMILY_COMPOUND3
        mutation_mechanism = "compound_missing_ground_plus_wrong_capacitance_plus_wrong_resistance"
        source_version = "v0.19.19"
    elif depth == 4:
        family = FAMILY_COMPOUND4
        mutation_mechanism = "compound_missing_ground_plus_wrong_capacitance_plus_wrong_resistance_plus_parallel_leak"
        source_version = "v0.19.20"
    else:
        raise ValueError(f"unsupported compound depth: {depth}")

    return {
        "candidate_id": row["candidate_id"],
        "task_id": row["candidate_id"],
        "benchmark_version": "gf_v1",
        "benchmark_family": family,
        "error_layer": 2,
        "mutation_mechanism": mutation_mechanism,
        "failure_type": str(row.get("failure_type") or "behavioral_contract_fail"),
        "expected_stage": "simulate",
        "source_model_path": row["source_model_path"],
        "mutated_model_path": row["mutated_model_path"],
        "workflow_goal": str(row.get("workflow_goal") or ""),
        "requires_semantic_reasoning": True,
        "omc_localizes_fix": False,
        "admission_verified": True,
        "planner_backend": "gemini",
        "backend": "openmodelica_docker",
        "_source_version": source_version,
        "_compound_depth": depth,
        "_mutation_family": str(row.get("mutation_family") or ""),
        "_compound_mutation_bugs": list(row.get("compound_mutation_bugs") or []),
        "_removed_ground_connects": list(row.get("removed_ground_connects") or []),
        "_semantic_oracle": row.get("semantic_oracle", {}),
        "_parameter_mutations": row.get("parameter_mutations", {}),
        "_base_v01915_candidate_id": str(row.get("base_v01915_candidate_id") or ""),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    overdet_rows = _load_jsonl(OVERDET_JSONL)
    underdet_rows = _load_jsonl(UNDERDET_JSONL)
    semantic_rows = _load_jsonl(SEMANTIC_JSONL)
    shortcirc_rows = _load_jsonl(SHORTCIRC_JSONL)
    compound2_rows = _load_jsonl(COMPOUND2_JSONL)
    compound3_rows = _load_jsonl(COMPOUND3_JSONL)
    compound4_rows = _load_jsonl(COMPOUND4_JSONL)

    cases: list[dict] = []
    for row in overdet_rows:
        cases.append(_normalise_overdet(row))
    for row in underdet_rows:
        cases.append(_normalise_underdet(row))
    for row in semantic_rows:
        cases.append(_normalise_semantic(row))
    for row in shortcirc_rows:
        cases.append(_normalise_shortcirc(row))
    for row in compound2_rows:
        cases.append(_normalise_compound(row, depth=2))
    for row in compound3_rows:
        cases.append(_normalise_compound(row, depth=3))
    for row in compound4_rows:
        cases.append(_normalise_compound(row, depth=4))

    # Write unified JSONL
    out_jsonl = OUT_DIR / "admitted_cases.jsonl"
    with open(out_jsonl, "w", encoding="utf-8") as f:
        for case in cases:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")

    # Tally by family and layer
    by_family: dict[str, int] = {}
    by_layer: dict[int, int] = {}
    for case in cases:
        fam = case["benchmark_family"]
        by_family[fam] = by_family.get(fam, 0) + 1
        layer = case["error_layer"]
        by_layer[layer] = by_layer.get(layer, 0) + 1

    summary = {
        "benchmark_version": "gf_v1",
        "total_cases": len(cases),
        "by_family": by_family,
        "by_error_layer": {str(k): v for k, v in sorted(by_layer.items())},
        "design_principles": [
            "mutations derived from real Modelica engineering error patterns",
            "failure_type labels correct from admission",
            "no artificial injection markers",
            "no heuristic-solvable cases",
            "compound families preserve cross-layer repair paths without executor-side staging",
        ],
        "output": str(out_jsonl),
    }

    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nCases written to: {out_jsonl}")


if __name__ == "__main__":
    main()
