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

Sources (v1 initial):
  - 12 overdetermined KVL/KCL cases (v0.19.11) — error_layer=2
  -  3 semantic RC time-constant cases (v0.19.9)  — error_layer=3

Output:
  artifacts/benchmark_gf_v1/admitted_cases.jsonl
  artifacts/benchmark_gf_v1/summary.json
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "artifacts" / "benchmark_gf_v1"

# Source JSONLs — both are correctly designed and admission-verified
OVERDET_JSONL = (
    REPO_ROOT / "artifacts" / "overdetermined_mutations_v0_19_11" / "admitted_cases.jsonl"
)
SEMANTIC_JSONL = (
    REPO_ROOT / "artifacts" / "semantic_reasoning_mutations_v0_19_9" / "admitted_cases.jsonl"
)

# Canonical benchmark_family names
FAMILY_OVERDET_KVL = "overdetermined_kvl"
FAMILY_OVERDET_KCL = "overdetermined_kcl"
FAMILY_SEMANTIC_TAU = "semantic_time_constant"


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


def _normalise_semantic(row: dict) -> dict:
    """Normalise a semantic reasoning case to the gf_v1 unified schema."""
    return {
        "candidate_id": row["candidate_id"],
        "task_id": row["candidate_id"],
        "benchmark_version": "gf_v1",
        "benchmark_family": FAMILY_SEMANTIC_TAU,
        "error_layer": 3,
        "mutation_mechanism": "wrong_semantic_parameter_value",
        "failure_type": row["failure_type"],
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
        "_source_version": "v0.19.9",
        "_semantic_contract": row.get("semantic_contract", {}),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    overdet_rows = _load_jsonl(OVERDET_JSONL)
    semantic_rows = _load_jsonl(SEMANTIC_JSONL)

    cases: list[dict] = []
    for row in overdet_rows:
        cases.append(_normalise_overdet(row))
    for row in semantic_rows:
        cases.append(_normalise_semantic(row))

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
