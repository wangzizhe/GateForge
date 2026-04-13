from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from .agent_modelica_v0_13_2_common import (
    ALLOWED_CANDIDATE_INTERVENTION_SHAPES,
    DEFAULT_OUT_OF_SCOPE_TRIGGER_TABLE,
    DEFAULT_REMAINING_CAPABILITY_INTERVENTION_SCOPE_ASSESSMENT_OUT_DIR,
    DEFAULT_STRONGER_CAPABILITY_INTERVENTION_SCOPE_SUMMARY_OUT_DIR,
    SCHEMA_PREFIX,
    SCOPE_STATUS_STRONGER_IN_SCOPE,
    STRONGER_CAPABILITY_INTERVENTION_STATUS_INVALID,
    STRONGER_CAPABILITY_INTERVENTION_STATUS_JUSTIFIED,
    STRONGER_CAPABILITY_INTERVENTION_STATUS_NOT_IN_SCOPE,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v132_stronger_capability_intervention_scope_summary(
    *,
    remaining_capability_intervention_scope_assessment_path: str = str(
        DEFAULT_REMAINING_CAPABILITY_INTERVENTION_SCOPE_ASSESSMENT_OUT_DIR / "summary.json"
    ),
    out_dir: str = str(DEFAULT_STRONGER_CAPABILITY_INTERVENTION_SCOPE_SUMMARY_OUT_DIR),
    candidate_intervention_id: str = "",
    candidate_intervention_family: str = "",
    candidate_intervention_shape: str = "none",
    target_gap_family: str = "",
    target_failure_mode: str = "",
    why_stronger_than_first_pack: str = "",
    why_still_bounded: str = "",
    expected_effect_type: str = "",
    same_source_comparison_still_possible: bool = False,
    out_of_scope_trigger_table: dict | None = None,
) -> dict:
    assessment = load_json(remaining_capability_intervention_scope_assessment_path)
    scope_obj = (
        assessment.get("remaining_capability_intervention_scope_object")
        if isinstance(assessment.get("remaining_capability_intervention_scope_object"), dict)
        else {}
    )

    scope_relevant_uncertainty_remains = bool(scope_obj.get("scope_relevant_uncertainty_remains"))
    uncertainty_is_bounded_step_addressable = bool(scope_obj.get("uncertainty_is_bounded_step_addressable"))
    expected_information_gain = str(scope_obj.get("expected_information_gain") or "marginal")
    remaining_scope_status = str(scope_obj.get("remaining_scope_status") or "")

    if candidate_intervention_shape not in ALLOWED_CANDIDATE_INTERVENTION_SHAPES:
        candidate_intervention_shape = "none"

    trigger_table = copy.deepcopy(DEFAULT_OUT_OF_SCOPE_TRIGGER_TABLE)
    if out_of_scope_trigger_table is not None:
        trigger_table.update(out_of_scope_trigger_table)

    structurally_invalid = False
    invalid_reason = ""
    if candidate_intervention_shape != "none" and not same_source_comparison_still_possible:
        structurally_invalid = True
        invalid_reason = "candidate_intervention_claimed_but_same_source_comparison_not_possible"
    elif candidate_intervention_shape != "none" and not candidate_intervention_id.strip():
        structurally_invalid = True
        invalid_reason = "candidate_intervention_shape_non_none_but_no_concrete_intervention_id"

    if structurally_invalid:
        stronger_intervention_scope_status = STRONGER_CAPABILITY_INTERVENTION_STATUS_INVALID
    elif (
        scope_relevant_uncertainty_remains
        and uncertainty_is_bounded_step_addressable
        and expected_information_gain == "non_marginal"
        and candidate_intervention_shape != "none"
        and candidate_intervention_id.strip()
        and same_source_comparison_still_possible
        and remaining_scope_status == SCOPE_STATUS_STRONGER_IN_SCOPE
    ):
        stronger_intervention_scope_status = STRONGER_CAPABILITY_INTERVENTION_STATUS_JUSTIFIED
    else:
        stronger_intervention_scope_status = STRONGER_CAPABILITY_INTERVENTION_STATUS_NOT_IN_SCOPE

    named_blocker_if_not_in_scope = str(scope_obj.get("named_blocker_if_not_in_scope") or "")

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_stronger_capability_intervention_scope_summary",
        "generated_at_utc": now_utc(),
        "status": "PASS" if stronger_intervention_scope_status != STRONGER_CAPABILITY_INTERVENTION_STATUS_INVALID else "FAIL",
        "stronger_intervention_scope_status": stronger_intervention_scope_status,
        "invalid_reason": invalid_reason if structurally_invalid else "",
        "stronger_intervention_candidate_object": {
            "candidate_intervention_id": (
                candidate_intervention_id
                if stronger_intervention_scope_status == STRONGER_CAPABILITY_INTERVENTION_STATUS_JUSTIFIED
                else ""
            ),
            "candidate_intervention_family": (
                candidate_intervention_family
                if stronger_intervention_scope_status == STRONGER_CAPABILITY_INTERVENTION_STATUS_JUSTIFIED
                else ""
            ),
            "candidate_intervention_shape": (
                candidate_intervention_shape
                if stronger_intervention_scope_status == STRONGER_CAPABILITY_INTERVENTION_STATUS_JUSTIFIED
                else "none"
            ),
            "target_gap_family": (
                target_gap_family if stronger_intervention_scope_status == STRONGER_CAPABILITY_INTERVENTION_STATUS_JUSTIFIED else ""
            ),
            "target_failure_mode": (
                target_failure_mode
                if stronger_intervention_scope_status == STRONGER_CAPABILITY_INTERVENTION_STATUS_JUSTIFIED
                else ""
            ),
            "why_stronger_than_first_pack": (
                why_stronger_than_first_pack
                if stronger_intervention_scope_status == STRONGER_CAPABILITY_INTERVENTION_STATUS_JUSTIFIED
                else ""
            ),
            "why_still_bounded": (
                why_still_bounded
                if stronger_intervention_scope_status == STRONGER_CAPABILITY_INTERVENTION_STATUS_JUSTIFIED
                else ""
            ),
            "expected_effect_type": (
                expected_effect_type
                if stronger_intervention_scope_status == STRONGER_CAPABILITY_INTERVENTION_STATUS_JUSTIFIED
                else ""
            ),
            "same_source_comparison_still_possible": same_source_comparison_still_possible,
        },
        "named_blocker_if_not_in_scope": named_blocker_if_not_in_scope,
        "out_of_scope_trigger_table": trigger_table,
        "remaining_capability_intervention_scope_object": scope_obj,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.13.2 Stronger Capability Intervention Scope Summary",
                "",
                f"- stronger_intervention_scope_status: `{stronger_intervention_scope_status}`",
                f"- candidate_intervention_shape: `{candidate_intervention_shape if stronger_intervention_scope_status == STRONGER_CAPABILITY_INTERVENTION_STATUS_JUSTIFIED else 'none'}`",
                f"- named_blocker_if_not_in_scope: `{named_blocker_if_not_in_scope}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.13.2 stronger capability intervention scope summary.")
    parser.add_argument(
        "--remaining-capability-intervention-scope-assessment",
        default=str(DEFAULT_REMAINING_CAPABILITY_INTERVENTION_SCOPE_ASSESSMENT_OUT_DIR / "summary.json"),
    )
    parser.add_argument("--out-dir", default=str(DEFAULT_STRONGER_CAPABILITY_INTERVENTION_SCOPE_SUMMARY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v132_stronger_capability_intervention_scope_summary(
        remaining_capability_intervention_scope_assessment_path=str(
            args.remaining_capability_intervention_scope_assessment
        ),
        out_dir=str(args.out_dir),
    )
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "stronger_intervention_scope_status": payload.get("stronger_intervention_scope_status"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
