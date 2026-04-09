from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_9_4_common import (
    DEFAULT_EXPANDED_THRESHOLD_PACK_OUT_DIR,
    DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR,
    FALLBACK_RULE_SUMMARY,
    FROZEN_TASK_COUNT,
    PARTIAL_THRESHOLD_PACK,
    SCHEMA_PREFIX,
    SUPPORTED_THRESHOLD_PACK,
    classify_baseline_against_pack,
    integer_safe_display,
    load_json,
    now_utc,
    pct_from_case_count,
    ratio_is_integer_safe,
    write_json,
    write_text,
)


def _threshold_pack_is_structurally_explicit(pack: dict) -> bool:
    return all(
        [
            isinstance(pack.get("primary_workflow_metrics"), dict),
            isinstance(pack.get("barrier_sidecar_metrics"), dict),
            isinstance(pack.get("interpretability_safeguards"), dict),
            isinstance(pack.get("repeatability_preconditions"), dict),
            isinstance(pack.get("execution_posture"), dict),
        ]
    )


def _ordering_checks(supported_pack: dict, partial_pack: dict) -> dict[str, bool]:
    supported_primary = supported_pack["primary_workflow_metrics"]
    partial_primary = partial_pack["primary_workflow_metrics"]
    supported_barrier = supported_pack["barrier_sidecar_metrics"]
    partial_barrier = partial_pack["barrier_sidecar_metrics"]
    return {
        "workflow_resolution_case_count_ordered": supported_primary["workflow_resolution_case_count_min"]
        > partial_primary["workflow_resolution_case_count_min"],
        "goal_alignment_case_count_ordered": supported_primary["goal_alignment_case_count_min"]
        > partial_primary["goal_alignment_case_count_min"],
        "surface_fix_only_case_count_ordered": supported_primary["surface_fix_only_case_count_max"]
        <= partial_primary["surface_fix_only_case_count_max"],
        "unresolved_case_count_ordered": supported_primary["unresolved_case_count_max"]
        <= partial_primary["unresolved_case_count_max"],
        "workflow_spillover_case_count_ordered": supported_barrier["workflow_spillover_case_count_max"]
        <= partial_barrier["workflow_spillover_case_count_max"],
    }


def _integer_safe_checks(pack: dict, *, task_count: int) -> dict[str, bool]:
    primary = pack["primary_workflow_metrics"]
    barrier = pack["barrier_sidecar_metrics"]
    checks = {}
    for key, case_count in {
        "workflow_resolution_case_count": primary["workflow_resolution_case_count_min"],
        "goal_alignment_case_count": primary["goal_alignment_case_count_min"],
        "surface_fix_only_case_count": primary["surface_fix_only_case_count_max"],
        "unresolved_case_count": primary["unresolved_case_count_max"],
        "workflow_spillover_case_count": barrier["workflow_spillover_case_count_max"],
    }.items():
        pct = pct_from_case_count(int(case_count), task_count)
        checks[f"{key}_integer_safe"] = ratio_is_integer_safe(int(case_count), task_count, pct)
    return checks


def build_v094_expanded_threshold_pack(
    *,
    threshold_input_table_path: str = str(DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_EXPANDED_THRESHOLD_PACK_OUT_DIR),
    supported_threshold_pack: dict | None = None,
    partial_threshold_pack: dict | None = None,
) -> dict:
    inputs = load_json(threshold_input_table_path)
    metrics = dict(inputs.get("frozen_baseline_metrics") or {})
    task_count = int(metrics.get("task_count") or FROZEN_TASK_COUNT)

    supported_pack = supported_threshold_pack or SUPPORTED_THRESHOLD_PACK
    partial_pack = partial_threshold_pack or PARTIAL_THRESHOLD_PACK

    baseline_classification = classify_baseline_against_pack(
        metrics,
        supported_pack=supported_pack,
        partial_pack=partial_pack,
    )
    anti_tautology_pass = baseline_classification == "expanded_workflow_readiness_partial_but_interpretable"

    integer_safe_checks = {}
    integer_safe_checks.update(_integer_safe_checks(supported_pack, task_count=task_count))
    integer_safe_checks.update(
        {
            f"partial_{key}": value
            for key, value in _integer_safe_checks(partial_pack, task_count=task_count).items()
        }
    )
    integer_safe_pass = all(integer_safe_checks.values())

    threshold_ordering_checks = _ordering_checks(supported_pack, partial_pack)
    threshold_ordering_pass = all(threshold_ordering_checks.values())

    execution_posture_note_present = all(
        [
            str(supported_pack.get("execution_posture", {}).get("allowed_execution_source") or "")
            == "frozen_expanded_substrate_deterministic_replay",
            bool(str(supported_pack.get("execution_posture", {}).get("scope_note") or "").strip()),
            str(partial_pack.get("execution_posture", {}).get("allowed_execution_source") or "")
            == "frozen_expanded_substrate_deterministic_replay",
            bool(str(partial_pack.get("execution_posture", {}).get("scope_note") or "").strip()),
        ]
    )

    structural_explicit = _threshold_pack_is_structurally_explicit(supported_pack) and _threshold_pack_is_structurally_explicit(partial_pack)
    baseline_fallback = baseline_classification == "fallback_to_profile_clarification_or_expansion_needed"
    threshold_pack_ready = all(
        [
            structural_explicit,
            anti_tautology_pass,
            integer_safe_pass,
            threshold_ordering_pass,
            execution_posture_note_present,
            not baseline_fallback,
        ]
    )
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_expanded_threshold_pack",
        "generated_at_utc": now_utc(),
        "status": "PASS" if threshold_pack_ready else "FAIL",
        "threshold_pack_status": "FROZEN" if threshold_pack_ready else "INCOMPLETE",
        "supported_threshold_pack": supported_pack,
        "partial_threshold_pack": partial_pack,
        "fallback_rule_summary": FALLBACK_RULE_SUMMARY,
        "baseline_classification_under_frozen_pack": baseline_classification,
        "anti_tautology_check": {
            "pass": anti_tautology_pass,
            "current_v093_baseline_supported": baseline_classification == "expanded_workflow_readiness_supported",
            "current_v093_baseline_partial": baseline_classification
            == "expanded_workflow_readiness_partial_but_interpretable",
        },
        "integer_safe_check": {
            "pass": integer_safe_pass,
            "checks": integer_safe_checks,
            "supported_display_equivalents": {
                key: integer_safe_display(value, task_count)
                for key, value in supported_pack["primary_workflow_metrics"].items()
                if key.endswith("_count_min") or key.endswith("_count_max")
            },
        },
        "threshold_ordering_check": {
            "pass": threshold_ordering_pass,
            "checks": threshold_ordering_checks,
        },
        "execution_posture_semantics_check": {
            "pass": execution_posture_note_present,
            "required_execution_source": "frozen_expanded_substrate_deterministic_replay",
        },
        "structural_explicit_check": {"pass": structural_explicit},
        "why_current_v093_baseline_is_or_is_not_partial_by_default": (
            "The current baseline clears the frozen partial floor but remains below the supported workflow-resolution and goal-alignment thresholds."
            if baseline_classification == "expanded_workflow_readiness_partial_but_interpretable"
            else "The current baseline does not cleanly land in the intended partial band under the frozen pack."
        ),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.4 Expanded Threshold Pack",
                "",
                f"- threshold_pack_status: `{payload['threshold_pack_status']}`",
                f"- baseline_classification_under_frozen_pack: `{baseline_classification}`",
                f"- anti_tautology_pass: `{anti_tautology_pass}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.4 expanded threshold pack summary.")
    parser.add_argument("--threshold-input-table-path", default=str(DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_EXPANDED_THRESHOLD_PACK_OUT_DIR))
    args = parser.parse_args()
    payload = build_v094_expanded_threshold_pack(
        threshold_input_table_path=str(args.threshold_input_table_path),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
