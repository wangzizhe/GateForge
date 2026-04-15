"""
Build the v0.19.8 capability attribution report.

The report compares the normal v0.19.7 56-case trajectory run against a
counterfactual run with bounded residual repairs disabled. It separates cases
that require executor heuristics from cases where those heuristics are merely
helpful or not involved, and freezes the reasoning-case admission criterion
for the next mutation-family step.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BENCHMARK = REPO_ROOT / "artifacts" / "benchmark_v0_19_5" / "admitted_cases.jsonl"
DEFAULT_NORMAL_SUMMARY = REPO_ROOT / "artifacts" / "benchmark_trajectory_v0_19_7" / "summary.json"
DEFAULT_COUNTERFACTUAL_SUMMARY = REPO_ROOT / "artifacts" / "benchmark_counterfactual_v0_19_8" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "capability_attribution_v0_19_8"

NONLOCAL_REASONING_DEFINITION = (
    "repair cannot be completed by reading only the OMC-indicated line or symbol; "
    "it requires understanding model structure outside the error point to choose the correct fix"
)

LOCAL_SIGNAL_FAMILIES = {
    "type1_intra_layer",
    "type2_inter_layer",
    "component_parameter_reference_error",
    "component_modifier_name_error",
    "connection_endpoint_typo",
    "equation_count_extra_constraint",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _index_by_candidate(rows: Iterable[dict]) -> dict[str, dict]:
    indexed = {}
    for row in rows:
        cid = str(row.get("candidate_id") or "")
        if cid:
            indexed[cid] = dict(row)
    return indexed


def classify_resolution_mechanism(normal: dict, counterfactual: dict) -> str:
    normal_status = str(normal.get("executor_status") or normal.get("status") or "")
    counterfactual_status = str(counterfactual.get("executor_status") or counterfactual.get("status") or "")
    if normal_status != "PASS":
        return "unresolved_in_normal_run"
    if counterfactual_status != "PASS":
        return "executor_heuristic_dependent"
    normal_turns = int(normal.get("n_turns") or 0)
    counterfactual_turns = int(counterfactual.get("n_turns") or 0)
    if counterfactual_turns > normal_turns:
        return "heuristic_assisted_but_not_required"
    return "llm_local_or_surface_repair"


def classify_reasoning_requirement(case: dict, normal: dict, counterfactual: dict) -> str:
    mechanism = classify_resolution_mechanism(normal, counterfactual)
    if mechanism == "executor_heuristic_dependent":
        return "executor_heuristic_required"
    family = str(case.get("benchmark_family") or case.get("mutation_family") or "")
    if family in LOCAL_SIGNAL_FAMILIES:
        return "local_error_signal_repair"
    return "requires_nonlocal_or_semantic_review"


def _build_case_record(case: dict, normal: dict, counterfactual: dict) -> dict:
    mechanism = classify_resolution_mechanism(normal, counterfactual)
    reasoning_requirement = classify_reasoning_requirement(case, normal, counterfactual)
    normal_turns = int(normal.get("n_turns") or 0)
    counterfactual_turns = int(counterfactual.get("n_turns") or 0)
    return {
        "candidate_id": str(case.get("candidate_id") or ""),
        "benchmark_family": str(case.get("benchmark_family") or ""),
        "mutation_family": str(case.get("mutation_family") or case.get("benchmark_family") or ""),
        "benchmark_source": str(case.get("benchmark_source") or ""),
        "normal_status": str(normal.get("executor_status") or normal.get("status") or ""),
        "counterfactual_status": str(counterfactual.get("executor_status") or counterfactual.get("status") or ""),
        "normal_turns": normal_turns,
        "counterfactual_turns": counterfactual_turns,
        "turns_delta_counterfactual_minus_normal": counterfactual_turns - normal_turns,
        "normal_observed_error_sequence": list(normal.get("observed_error_sequence") or []),
        "counterfactual_observed_error_sequence": list(counterfactual.get("observed_error_sequence") or []),
        "resolution_mechanism": mechanism,
        "reasoning_requirement": reasoning_requirement,
        "requires_nonlocal_or_semantic_reasoning": reasoning_requirement == "requires_nonlocal_or_semantic_review",
        "failure_localization_signal": "explicit_omc_line_or_symbol",
    }


def reasoning_case_admission_criterion() -> dict:
    return {
        "status": "frozen",
        "version": "v0.19.8",
        "requires_nonlocal_or_semantic_reasoning_definition": NONLOCAL_REASONING_DEFINITION,
        "hard_constraints": [
            {
                "id": "source_clean_and_omc_admitted",
                "description": "The source model must pass the same OMC check/simulate path before mutation.",
            },
            {
                "id": "no_known_heuristic_solvable",
                "description": "The candidate must remain non-trivial when known executor heuristics are disabled.",
            },
            {
                "id": "failure_localization_not_explicit_tag",
                "description": "The correct repair cannot be identified solely from a literal OMC-named line, symbol, or injected tag.",
            },
            {
                "id": "requires_nonlocal_or_semantic_reasoning",
                "description": NONLOCAL_REASONING_DEFINITION,
            },
            {
                "id": "counterfactual_report_required",
                "description": "Admission must include a normal run and a heuristic-disabled counterfactual attribution record.",
            },
        ],
    }


def v0_19_9_candidate_shortlist() -> list[dict]:
    return [
        {
            "family": "semantic_initial_value_wrong_but_compiles",
            "reason": "The model compiles, but the repair requires interpreting dynamic behavior and physically plausible state.",
            "admission_risk": "simulate failures may be backend-sensitive; require deterministic source-clean baseline.",
        },
        {
            "family": "nonlocal_parameter_behavior_regression",
            "reason": "The wrong value is not the symbol named by OMC; the agent must inspect connected structure to choose the fix.",
            "admission_risk": "Needs a clear behavioral oracle to avoid subjective success labels.",
        },
        {
            "family": "multi_component_coupled_error_without_symbol_tag",
            "reason": "The visible failure is downstream of multiple component choices, so single-line OMC localization is insufficient.",
            "admission_risk": "Must avoid creating permanently stuck cases with no readable residual.",
        },
        {
            "family": "subcomponent_param_top_level_behavior_mismatch",
            "reason": "A subcomponent parameter change produces a top-level behavior error and requires hierarchy-aware repair.",
            "admission_risk": "Requires preserving structural balance while changing the semantic parameter target.",
        },
        {
            "family": "wrong_equation_structure_semantic_but_balanced",
            "reason": "The equation count stays balanced, but the equation has the wrong physical meaning.",
            "admission_risk": "Needs an oracle stronger than checkModel and not too brittle under simulate.",
        },
    ]


def build_report(
    *,
    benchmark_path: Path,
    normal_summary_path: Path,
    counterfactual_summary_path: Path,
) -> tuple[dict, list[dict]]:
    cases = _index_by_candidate(_load_jsonl(benchmark_path))
    normal = _index_by_candidate(_load_json(normal_summary_path).get("summaries") or [])
    counterfactual = _index_by_candidate(_load_json(counterfactual_summary_path).get("summaries") or [])

    missing = sorted(set(cases) - set(normal)) + sorted(set(cases) - set(counterfactual))
    if missing:
        raise ValueError(f"missing candidate summaries: {missing[:8]}")

    records = [
        _build_case_record(cases[cid], normal[cid], counterfactual[cid])
        for cid in sorted(cases)
    ]

    mechanism_counts = Counter(record["resolution_mechanism"] for record in records)
    reasoning_counts = Counter(record["reasoning_requirement"] for record in records)
    by_family: dict[str, Counter] = defaultdict(Counter)
    for record in records:
        by_family[record["benchmark_family"]][record["resolution_mechanism"]] += 1

    semantic_count = sum(1 for record in records if record["requires_nonlocal_or_semantic_reasoning"])
    report = {
        "version": "v0.19.8",
        "n_cases": len(records),
        "normal_run": str(normal_summary_path.relative_to(REPO_ROOT)),
        "counterfactual_run": str(counterfactual_summary_path.relative_to(REPO_ROOT)),
        "counterfactual": "disable_bounded_residual_repairs",
        "resolution_mechanism_counts": dict(sorted(mechanism_counts.items())),
        "reasoning_requirement_counts": dict(sorted(reasoning_counts.items())),
        "current_benchmark_semantic_reasoning_required_count": semantic_count,
        "current_benchmark_semantic_reasoning_required_rate": semantic_count / len(records) if records else 0.0,
        "by_family_resolution_mechanism_counts": {
            family: dict(sorted(counter.items()))
            for family, counter in sorted(by_family.items())
        },
        "interpretation": {
            "current_56_case_benchmark": (
                "The benchmark remains useful as a local repair and bounded heuristic anchor, "
                "but it does not yet measure nonlocal or semantic Modelica reasoning."
            ),
            "pass_rate_warning": (
                "A 100% normal pass rate is not a sufficient capability claim unless the "
                "resolution mechanism mix is reported with the pass rate."
            ),
        },
        "reasoning_case_admission_criterion": reasoning_case_admission_criterion(),
        "v0_19_9_candidate_shortlist": v0_19_9_candidate_shortlist(),
    }
    return report, records


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", default=str(DEFAULT_BENCHMARK))
    parser.add_argument("--normal-summary", default=str(DEFAULT_NORMAL_SUMMARY))
    parser.add_argument("--counterfactual-summary", default=str(DEFAULT_COUNTERFACTUAL_SUMMARY))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report, records = build_report(
        benchmark_path=Path(args.benchmark),
        normal_summary_path=Path(args.normal_summary),
        counterfactual_summary_path=Path(args.counterfactual_summary),
    )
    (out_dir / "summary.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    with open(out_dir / "cases.jsonl", "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Wrote {len(records)} case attribution records to {out_dir}/")
    print("resolution_mechanism_counts:")
    for key, value in report["resolution_mechanism_counts"].items():
        print(f"  {key}: {value}")
    print(
        "current_benchmark_semantic_reasoning_required_count: "
        f"{report['current_benchmark_semantic_reasoning_required_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
