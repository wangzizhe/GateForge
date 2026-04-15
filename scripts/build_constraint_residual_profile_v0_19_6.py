"""
Build the v0.19.6 residual profile for unresolved v0.19.5 benchmark cases.

The profile is intentionally analysis-only: it reads real v0.19.5 trajectory
artifacts, classifies unresolved residuals, and emits a bounded next-repair
strategy without changing the live executor.

Outputs:
  artifacts/constraint_residual_profile_v0_19_6/summary.json
  artifacts/constraint_residual_profile_v0_19_6/unresolved_cases.jsonl
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TRAJECTORY_SUMMARY = REPO_ROOT / "artifacts" / "benchmark_trajectory_v0_19_5" / "summary.json"
RAW_DIR = REPO_ROOT / "artifacts" / "benchmark_trajectory_v0_19_5" / "raw"
OUT_DIR = REPO_ROOT / "artifacts" / "constraint_residual_profile_v0_19_6"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _attempt_error_text(attempt: dict) -> str:
    fields = [
        "log_excerpt",
        "full_omc_error_output",
        "reason",
        "llm_plan_failure_mode",
    ]
    return "\n".join(str(attempt.get(field) or "") for field in fields)


def _classify_attempt(attempt: dict) -> str:
    text = _attempt_error_text(attempt)
    if "Too many equations" in text or "over-determined system" in text:
        return "overdetermined_structural_balance"
    if "Modelica.SIunits" in text and "not found" in text:
        return "legacy_msl_type_injection"
    if "gemini_patch_generation_failed" in text:
        return "patch_generation_failed"
    observed = str(attempt.get("observed_failure_type") or "")
    if observed == "constraint_violation":
        return "unclassified_constraint_violation"
    if observed == "model_check_error":
        return "model_check_error"
    return observed or "unknown"


def _transition_class(sequence: list[str]) -> str:
    if not sequence:
        return "no_attempts"
    if sequence == ["constraint_violation"]:
        return "starts_at_constraint_violation"
    if sequence[0] == "model_check_error" and all(item == "constraint_violation" for item in sequence[1:]):
        return "model_check_to_constraint_loop"
    if sequence[-1] == "constraint_violation":
        return "ends_at_constraint_violation"
    return "other"


def _repair_strategy_for(case: dict, residual_classes: list[str]) -> dict:
    family = str(case.get("benchmark_family") or "")
    residual_set = set(residual_classes)
    if family == "equation_count_extra_constraint":
        return {
            "strategy_id": "constraint_residual_remove_or_relax_extra_binding_equation",
            "strategy_class": "structural_balance_repair",
            "executor_change_required": True,
            "bounded_action": (
                "When simulate reports an over-determined system after checkModel passed, "
                "ask the repair path to remove or relax the non-connect binding equation "
                "introduced near the equation section, then re-run simulate."
            ),
        }
    if "legacy_msl_type_injection" in residual_set:
        return {
            "strategy_id": "reject_legacy_msl_siunits_repair",
            "strategy_class": "repair_guardrail",
            "executor_change_required": True,
            "bounded_action": (
                "Reject repair patches that introduce Modelica.SIunits.* in MSL 4.1 models; "
                "prefer untyped Real parameters or Modelica.Units.SI if a typed declaration is required."
            ),
        }
    return {
        "strategy_id": "inspect_case_manually_before_runtime_change",
        "strategy_class": "analysis_needed",
        "executor_change_required": False,
        "bounded_action": "Do not change executor behavior until this residual class has a stable signature.",
    }


def _profile_case(summary_case: dict) -> dict:
    cid = str(summary_case["candidate_id"])
    payload = _load_json(RAW_DIR / f"{cid}.json")
    attempts = list(payload.get("attempts") or [])
    observed_sequence = [str(attempt.get("observed_failure_type") or "") for attempt in attempts]
    residual_classes = [_classify_attempt(attempt) for attempt in attempts]
    final_attempt = attempts[-1] if attempts else {}
    final_residual_class = residual_classes[-1] if residual_classes else "no_attempts"

    case = {
        "candidate_id": cid,
        "benchmark_family": str(summary_case.get("benchmark_family") or ""),
        "executor_status": str(summary_case.get("executor_status") or ""),
        "termination": str(summary_case.get("termination") or ""),
        "n_turns": int(summary_case.get("n_turns") or 0),
        "observed_error_sequence": observed_sequence,
        "transition_class": _transition_class(observed_sequence),
        "residual_classes_by_turn": residual_classes,
        "final_residual_class": final_residual_class,
        "final_reason": str(final_attempt.get("reason") or ""),
        "llm_plan_failure_modes": [
            str(attempt.get("llm_plan_failure_mode") or "") for attempt in attempts
        ],
    }
    case["recommended_next_strategy"] = _repair_strategy_for(case, residual_classes)
    return case


def build_profile() -> dict:
    trajectory = _load_json(TRAJECTORY_SUMMARY)
    unresolved = [
        case for case in trajectory.get("summaries", [])
        if str(case.get("executor_status") or "").upper() != "PASS"
    ]
    profiled_cases = [_profile_case(case) for case in unresolved]

    by_family = Counter(case["benchmark_family"] for case in profiled_cases)
    by_final_residual = Counter(case["final_residual_class"] for case in profiled_cases)
    by_transition = Counter(case["transition_class"] for case in profiled_cases)
    by_strategy = Counter(
        case["recommended_next_strategy"]["strategy_id"] for case in profiled_cases
    )

    family_residual_matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for case in profiled_cases:
        family_residual_matrix[case["benchmark_family"]][case["final_residual_class"]] += 1

    return {
        "version": "v0.19.6",
        "input_trajectory_summary": str(TRAJECTORY_SUMMARY),
        "total_unresolved_cases": len(profiled_cases),
        "by_family": dict(sorted(by_family.items())),
        "by_final_residual_class": dict(sorted(by_final_residual.items())),
        "by_transition_class": dict(sorted(by_transition.items())),
        "by_recommended_strategy": dict(sorted(by_strategy.items())),
        "family_residual_matrix": {
            family: dict(sorted(counts.items()))
            for family, counts in sorted(family_residual_matrix.items())
        },
        "next_version_recommendation": {
            "version": "v0.19.7",
            "primary_focus": "implement_bounded_constraint_residual_repairs",
            "gates": [
                "handle overdetermined_structural_balance without overfitting to v0.19.5 line text",
                "reject or rewrite legacy Modelica.SIunits.* patch introductions under MSL 4.1",
                "re-run only the 10 unresolved v0.19.5 cases before full 56-case rerun",
            ],
        },
        "cases": profiled_cases,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    profile = build_profile()
    (OUT_DIR / "summary.json").write_text(
        json.dumps(profile, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    with open(OUT_DIR / "unresolved_cases.jsonl", "w", encoding="utf-8") as handle:
        for case in profile["cases"]:
            handle.write(json.dumps(case, ensure_ascii=False) + "\n")

    print("=== v0.19.6 Constraint Residual Profile ===")
    print(f"  unresolved_cases: {profile['total_unresolved_cases']}")
    for key, value in profile["by_final_residual_class"].items():
        print(f"  {key}: {value}")
    print(f"  summary: {OUT_DIR / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
