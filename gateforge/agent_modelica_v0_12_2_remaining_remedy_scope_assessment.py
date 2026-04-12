from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_12_2_common import (
    ALLOWED_CANDIDATE_REMEDY_SHAPES,
    CARRIED_DOMINANT_GAP_FAMILY,
    DEFAULT_NAMED_BLOCKER,
    DEFAULT_REMAINING_REMEDY_SCOPE_ASSESSMENT_OUT_DIR,
    DEFAULT_V121_CLOSEOUT_PATH,
    EXPECTED_V121_PACK_LEVEL_EFFECT,
    SCHEMA_PREFIX,
    SCOPE_STATUS_INVALID,
    SCOPE_STATUS_NO_STRONGER,
    SCOPE_STATUS_STRONGER_IN_SCOPE,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v122_remaining_remedy_scope_assessment(
    *,
    v121_closeout_path: str = str(DEFAULT_V121_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_REMAINING_REMEDY_SCOPE_ASSESSMENT_OUT_DIR),
    scope_relevant_uncertainty_remains: bool | None = None,
    uncertainty_is_bounded_step_addressable: bool | None = None,
    expected_information_gain: str | None = None,
    candidate_next_remedy_shape: str | None = None,
    named_blocker_if_not_in_scope: str | None = None,
) -> dict:
    upstream = load_json(v121_closeout_path)
    conclusion = upstream.get("conclusion") if isinstance(upstream.get("conclusion"), dict) else {}

    first_pack_result_readout = str(conclusion.get("pack_level_effect") or EXPECTED_V121_PACK_LEVEL_EFFECT)
    remaining_gap_family_readout = CARRIED_DOMINANT_GAP_FAMILY

    # Default logic: non_material result from residual_core_capability_gap means
    # no concrete bounded operational lever remains to test.
    if scope_relevant_uncertainty_remains is None:
        scope_relevant_uncertainty_remains = False
    if uncertainty_is_bounded_step_addressable is None:
        uncertainty_is_bounded_step_addressable = False
    if candidate_next_remedy_shape is None:
        candidate_next_remedy_shape = "none"
    if named_blocker_if_not_in_scope is None:
        named_blocker_if_not_in_scope = DEFAULT_NAMED_BLOCKER

    # Hard rules (plan § Step 2):
    # if scope_relevant_uncertainty_remains = false → expected_information_gain must be marginal
    # if uncertainty_is_bounded_step_addressable = false → candidate_next_remedy_shape must be none
    if not scope_relevant_uncertainty_remains:
        if expected_information_gain is not None and expected_information_gain != "marginal":
            # Caller violated hard rule; collapse
            expected_information_gain = "marginal"
        else:
            expected_information_gain = "marginal"
    else:
        if expected_information_gain is None:
            expected_information_gain = "marginal"

    if not uncertainty_is_bounded_step_addressable:
        if candidate_next_remedy_shape != "none":
            candidate_next_remedy_shape = "none"

    # Validate candidate_next_remedy_shape
    if candidate_next_remedy_shape not in ALLOWED_CANDIDATE_REMEDY_SHAPES:
        candidate_next_remedy_shape = "none"

    # Derive remaining_scope_status from computed values
    if (
        scope_relevant_uncertainty_remains
        and uncertainty_is_bounded_step_addressable
        and expected_information_gain == "non_marginal"
        and candidate_next_remedy_shape != "none"
    ):
        remaining_scope_status = SCOPE_STATUS_STRONGER_IN_SCOPE
    else:
        remaining_scope_status = SCOPE_STATUS_NO_STRONGER

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_remaining_remedy_scope_assessment",
        "generated_at_utc": now_utc(),
        "status": "PASS" if remaining_scope_status != SCOPE_STATUS_INVALID else "FAIL",
        "remaining_remedy_scope_object": {
            "remaining_scope_status": remaining_scope_status,
            "remaining_gap_family_readout": remaining_gap_family_readout,
            "first_pack_result_readout": first_pack_result_readout,
            "scope_relevant_uncertainty_remains": scope_relevant_uncertainty_remains,
            "uncertainty_is_bounded_step_addressable": uncertainty_is_bounded_step_addressable,
            "expected_information_gain": expected_information_gain,
            "candidate_next_remedy_shape": candidate_next_remedy_shape,
            "named_blocker_if_not_in_scope": (
                named_blocker_if_not_in_scope if remaining_scope_status != SCOPE_STATUS_STRONGER_IN_SCOPE else ""
            ),
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.12.2 Remaining Remedy Scope Assessment",
                "",
                f"- remaining_scope_status: `{remaining_scope_status}`",
                f"- scope_relevant_uncertainty_remains: `{scope_relevant_uncertainty_remains}`",
                f"- expected_information_gain: `{expected_information_gain}`",
                f"- candidate_next_remedy_shape: `{candidate_next_remedy_shape}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.12.2 remaining remedy scope assessment.")
    parser.add_argument("--v121-closeout", default=str(DEFAULT_V121_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_REMAINING_REMEDY_SCOPE_ASSESSMENT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v122_remaining_remedy_scope_assessment(
        v121_closeout_path=str(args.v121_closeout),
        out_dir=str(args.out_dir),
    )
    scope_obj = payload.get("remaining_remedy_scope_object") or {}
    print(json.dumps({
        "status": payload.get("status"),
        "remaining_scope_status": scope_obj.get("remaining_scope_status"),
        "expected_information_gain": scope_obj.get("expected_information_gain"),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
