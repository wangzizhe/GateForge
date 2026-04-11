from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_11_6_common import (
    BOUND_STEP_KIND_NONE,
    BOUND_STEP_KIND_TARGETED_CONTEXT_CONTRACT_CLARIFICATION,
    DEFAULT_REMAINING_UNCERTAINTY_CHARACTERIZATION_OUT_DIR,
    DEFAULT_V115_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v116_remaining_uncertainty_characterization(
    *,
    v115_closeout_path: str = str(DEFAULT_V115_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_REMAINING_UNCERTAINTY_CHARACTERIZATION_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    closeout = load_json(v115_closeout_path)
    conclusion = closeout.get("conclusion") if isinstance(closeout.get("conclusion"), dict) else {}

    final_label = str(conclusion.get("formal_adjudication_label") or "")
    execution_ok = bool(conclusion.get("execution_posture_semantics_preserved"))
    dominant_gap_family = str(conclusion.get("dominant_gap_family_readout") or "")

    if (
        final_label == "product_gap_partial_but_interpretable"
        and execution_ok
        and dominant_gap_family == "context_discipline_gap"
    ):
        remaining_uncertainty_status = "phase_relevant_and_step_addressable"
        remaining_uncertainty_label = "bounded_context_contract_clarification_may_still_shift_product_gap_reading"
        remaining_uncertainty_is_step_addressable = True
        remaining_uncertainty_is_phase_relevant = True
        expected_information_gain = "non_marginal"
        candidate_next_step_shape = BOUND_STEP_KIND_TARGETED_CONTEXT_CONTRACT_CLARIFICATION
        why = (
            "One bounded product-gap clarification step remains plausible because the carried dominant gap family "
            "still points to context-discipline limits that may be sharpened by one concrete context-contract clarification step."
        )
    else:
        remaining_uncertainty_status = "no_phase_relevant_uncertainty_remaining"
        remaining_uncertainty_label = "current_product_gap_adjudication_already_answers_phase_question_strongly_enough"
        remaining_uncertainty_is_step_addressable = False
        remaining_uncertainty_is_phase_relevant = False
        expected_information_gain = "marginal"
        candidate_next_step_shape = BOUND_STEP_KIND_NONE
        why = (
            "The current product-gap adjudication already answers the phase question strongly enough, and no bounded "
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
        "why_this_uncertainty_does_or_does_not_justify_one_more_step": why,
        "carried_dominant_gap_family_readout": dominant_gap_family,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.11.6 Remaining Uncertainty Characterization",
                "",
                f"- remaining_uncertainty_status: `{remaining_uncertainty_status}`",
                f"- expected_information_gain: `{expected_information_gain}`",
                f"- candidate_next_step_shape: `{candidate_next_step_shape}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.11.6 remaining uncertainty characterization.")
    parser.add_argument("--v115-closeout", default=str(DEFAULT_V115_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_REMAINING_UNCERTAINTY_CHARACTERIZATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v116_remaining_uncertainty_characterization(
        v115_closeout_path=str(args.v115_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "remaining_uncertainty_status": payload.get("remaining_uncertainty_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
