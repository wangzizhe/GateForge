from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_10_7_common import (
    BOUND_STEP_KIND_NONE,
    BOUND_STEP_KIND_TARGETED_NON_SUCCESS_FAMILY_CLARIFICATION,
    DEFAULT_REMAINING_UNCERTAINTY_CHARACTERIZATION_OUT_DIR,
    DEFAULT_V106_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v107_remaining_uncertainty_characterization(
    *,
    v106_closeout_path: str = str(DEFAULT_V106_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_REMAINING_UNCERTAINTY_CHARACTERIZATION_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    closeout = load_json(v106_closeout_path)
    conclusion = closeout.get("conclusion") if isinstance(closeout.get("conclusion"), dict) else {}
    adjudication_input = (
        closeout.get("real_origin_adjudication_input_table")
        if isinstance(closeout.get("real_origin_adjudication_input_table"), dict)
        else {}
    )

    final_label = str(conclusion.get("final_adjudication_label") or "")
    execution_ok = bool(conclusion.get("execution_posture_semantics_preserved"))
    label_distribution = {
        str(k): int(v) for k, v in ((adjudication_input.get("non_success_label_distribution") or {}).items()) if str(k).strip()
    }
    total_non_success = sum(label_distribution.values())
    dominant_non_success_count = max(label_distribution.values()) if label_distribution else 0
    dominant_non_success_share = round(dominant_non_success_count / total_non_success, 3) if total_non_success else 0.0

    if (
        final_label == "real_origin_workflow_readiness_partial_but_interpretable"
        and execution_ok
        and total_non_success > 0
        and dominant_non_success_share >= 0.6
    ):
        remaining_uncertainty_status = "phase_relevant_and_step_addressable"
        remaining_uncertainty_label = "dominant_non_success_family_may_still_support_one_bounded_clarification_step"
        remaining_uncertainty_is_step_addressable = True
        remaining_uncertainty_is_phase_relevant = True
        expected_information_gain = "non_marginal"
        candidate_next_step_shape = BOUND_STEP_KIND_TARGETED_NON_SUCCESS_FAMILY_CLARIFICATION
        why = (
            "One bounded clarification step remains plausible because a single non-success family still dominates "
            "the unresolved picture strongly enough to suggest a concentrated, phase-relevant clarification opportunity."
        )
    else:
        remaining_uncertainty_status = "no_phase_relevant_uncertainty_remaining"
        remaining_uncertainty_label = "current_real_origin_adjudication_already_answers_phase_question_strongly_enough"
        remaining_uncertainty_is_step_addressable = False
        remaining_uncertainty_is_phase_relevant = False
        expected_information_gain = "marginal"
        candidate_next_step_shape = BOUND_STEP_KIND_NONE
        why = (
            "The current real-origin adjudication already answers the phase question strongly enough, and no bounded "
            "next step is expected to change that answer with non-marginal information gain."
        )

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_remaining_uncertainty_characterization",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "remaining_uncertainty_status": remaining_uncertainty_status,
        "remaining_uncertainty_label": remaining_uncertainty_label,
        "remaining_uncertainty_is_step_addressable": remaining_uncertainty_is_step_addressable,
        "remaining_uncertainty_is_phase_relevant": remaining_uncertainty_is_phase_relevant,
        "expected_information_gain": expected_information_gain,
        "candidate_next_step_shape": candidate_next_step_shape,
        "dominant_non_success_share": dominant_non_success_share,
        "why_this_uncertainty_does_or_does_not_justify_one_more_step": why,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.10.7 Remaining Uncertainty Characterization",
                "",
                f"- remaining_uncertainty_status: `{remaining_uncertainty_status}`",
                f"- expected_information_gain: `{expected_information_gain}`",
                f"- candidate_next_step_shape: `{candidate_next_step_shape}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.10.7 remaining uncertainty characterization.")
    parser.add_argument("--v106-closeout", default=str(DEFAULT_V106_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_REMAINING_UNCERTAINTY_CHARACTERIZATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v107_remaining_uncertainty_characterization(
        v106_closeout_path=str(args.v106_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "remaining_uncertainty_status": payload.get("remaining_uncertainty_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
