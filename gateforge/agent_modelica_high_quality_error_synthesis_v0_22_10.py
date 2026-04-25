from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUTS = {
    "engineering_screening": REPO_ROOT / "artifacts" / "engineering_mutation_screening_v0_22_1" / "summary.json",
    "staged_screening": REPO_ROOT / "artifacts" / "staged_residual_screening_v0_22_5" / "summary.json",
    "single_point_repeatability": REPO_ROOT / "artifacts" / "single_point_repeatability_v0_22_7" / "summary.json",
    "family_repeatability": REPO_ROOT / "artifacts" / "single_point_family_repeatability_v0_22_9" / "summary.json",
}
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "high_quality_error_synthesis_v0_22_10"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _aggregate(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload.get("aggregate")
    return aggregate if isinstance(aggregate, dict) else payload


def _family_counts(summary: dict[str, Any]) -> dict[str, dict[str, int]]:
    raw = summary.get("family_stability_counts") or {}
    if not isinstance(raw, dict):
        return {}
    result: dict[str, dict[str, int]] = {}
    for family, counts in raw.items():
        if isinstance(counts, dict):
            result[str(family)] = {str(key): int(value or 0) for key, value in counts.items()}
    return result


def classify_family_policy(family: str, counts: dict[str, int]) -> dict[str, Any]:
    stable = int(counts.get("stable_true_multi", 0))
    unstable = int(counts.get("unstable_true_multi", 0))
    never = int(counts.get("never_true_multi", 0))
    if stable >= 2 and unstable == 0:
        policy = "promote_family_prototype"
        rationale = "repeatability gate found multiple stable true-multiturn seeds and no unstable seed"
    elif stable >= 1:
        policy = "seed_only"
        rationale = "repeatability gate found at least one stable seed but family-level yield or stability is insufficient"
    else:
        policy = "reject_for_now"
        rationale = "repeatability gate found no stable true-multiturn seed"
    return {
        "family": family,
        "stable_true_multi": stable,
        "unstable_true_multi": unstable,
        "never_true_multi": never,
        "policy": policy,
        "rationale": rationale,
    }


def build_high_quality_error_synthesis(
    *,
    input_paths: dict[str, Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    paths = input_paths or DEFAULT_INPUTS
    loaded = {name: load_json(path) for name, path in paths.items()}
    missing = [name for name, payload in loaded.items() if not payload]

    engineering = _aggregate(loaded.get("engineering_screening", {}))
    staged = _aggregate(loaded.get("staged_screening", {}))
    single_point = loaded.get("single_point_repeatability", {})
    family_repeatability = loaded.get("family_repeatability", {})

    single_point_stable = int(
        (single_point.get("candidate_stability_counts") or {}).get("stable_true_multi", 0)
    )
    single_point_never = int((single_point.get("candidate_stability_counts") or {}).get("never_true_multi", 0))
    family_policies = [
        classify_family_policy(family, counts)
        for family, counts in sorted(_family_counts(family_repeatability).items())
    ]

    seed_rules = [
        "count true multiturn by repair_round_count >= 2, not executor turn count",
        "require OMC admission before live screening",
        "require repeatability gate before promoting a family into benchmark substrate",
        "promote stable seeds separately from family-level promotion",
        "record stable dead-ends as hard negatives instead of hiding them with deterministic repair",
        "keep residuals tied to one component or one workflow intent",
    ]
    promoted_family_prototypes = [
        row["family"] for row in family_policies if row.get("policy") == "promote_family_prototype"
    ]
    seed_only_families = [row["family"] for row in family_policies if row.get("policy") == "seed_only"]
    reject_families = [row["family"] for row in family_policies if row.get("policy") == "reject_for_now"]
    if single_point_stable >= 4:
        promoted_family_prototypes.insert(0, "single_point_resistor_observability_refactor")

    status = "PASS" if not missing and single_point_stable >= 4 and promoted_family_prototypes else "REVIEW"
    summary = {
        "version": "v0.22.10",
        "status": status,
        "analysis_scope": "high_quality_error_construction_phase_synthesis",
        "missing_inputs": missing,
        "phase_decision": (
            "v0.22_high_quality_error_construction_can_close"
            if status == "PASS"
            else "v0.22_high_quality_error_construction_needs_review"
        ),
        "engineering_residual_result": {
            "total_cases": int(engineering.get("total_cases", 0)),
            "multi_turn_useful_count": int(engineering.get("multi_turn_useful_count", 0)),
            "decision": "downgrade_as_false_multiturn_or_unstable_seed_source",
        },
        "staged_residual_result": {
            "total_cases": int(staged.get("total_cases", 0)),
            "multi_turn_useful_count": int(staged.get("multi_turn_useful_count", 0)),
            "decision": "valid_route_but_superseded_by_single_point_complex_for_next_seed_work",
        },
        "single_point_repeatability_result": {
            "stable_true_multi": single_point_stable,
            "never_true_multi": single_point_never,
            "decision": "promote_resistor_observability_as_family_prototype"
            if single_point_stable >= 4
            else "keep_resistor_observability_under_review",
        },
        "family_repeatability_policies": family_policies,
        "promoted_family_prototypes": promoted_family_prototypes,
        "seed_only_families": seed_only_families,
        "reject_families": reject_families,
        "seed_selection_rules": seed_rules,
        "architecture_handoff": {
            "ready_to_return_to_agent_framework": status == "PASS",
            "recommended_next_focus": "agent_framework_and_harness_hardening",
            "data_training_decision": "defer_training_until_framework_and_benchmark_substrate_are_stable",
        },
        "conclusion": (
            "single_point_complex_refactor_with_repeatability_gate_is_the_current_best_error_construction_method"
            if status == "PASS"
            else "high_quality_error_construction_synthesis_incomplete"
        ),
    }
    write_outputs(out_dir=out_dir, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
