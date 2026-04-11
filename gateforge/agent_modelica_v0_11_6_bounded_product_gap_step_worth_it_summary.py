from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_11_6_common import (
    BOUND_STEP_KIND_NONE,
    BOUND_STEP_KIND_TARGETED_CONTEXT_CONTRACT_CLARIFICATION,
    DEFAULT_BOUNDED_PRODUCT_GAP_STEP_WORTH_IT_SUMMARY_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v116_bounded_product_gap_step_worth_it_summary(
    *,
    remaining_uncertainty_characterization_path: str,
    out_dir: str = str(DEFAULT_BOUNDED_PRODUCT_GAP_STEP_WORTH_IT_SUMMARY_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    uncertainty = load_json(remaining_uncertainty_characterization_path)
    status = str(uncertainty.get("remaining_uncertainty_status") or "")
    step_addressable = bool(uncertainty.get("remaining_uncertainty_is_step_addressable"))
    phase_relevant = bool(uncertainty.get("remaining_uncertainty_is_phase_relevant"))
    expected_gain = str(uncertainty.get("expected_information_gain") or "")
    candidate_shape = str(uncertainty.get("candidate_next_step_shape") or "")

    justified = (
        status == "phase_relevant_and_step_addressable"
        and step_addressable
        and phase_relevant
        and expected_gain == "non_marginal"
        and candidate_shape == BOUND_STEP_KIND_TARGETED_CONTEXT_CONTRACT_CLARIFICATION
    )

    if justified:
        worth_it_status = "one_more_bounded_product_gap_step_justified"
        proposed_next_step_kind = candidate_shape
        why = (
            "One more bounded product-gap step is justified because the remaining uncertainty is still phase-relevant, "
            "step-addressable, and concentrated enough to name one concrete context-contract clarification step "
            "without reopening replay, threshold design, or substrate composition."
        )
    else:
        worth_it_status = "more_bounded_product_gap_step_not_worth_it"
        proposed_next_step_kind = BOUND_STEP_KIND_NONE
        why = (
            "One more bounded product-gap step is not worth it because the current product-gap adjudication already "
            "answers the phase question strongly enough, or no concrete bounded clarification step can be named without "
            "violating the current no-reopen discipline."
        )

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_bounded_product_gap_step_worth_it_summary",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "bounded_product_gap_step_worth_it_status": worth_it_status,
        "why_one_more_step_is_or_is_not_worth_it": why,
        "proposed_next_step_kind": proposed_next_step_kind,
        "expected_information_gain": expected_gain,
        "remaining_uncertainty_status": status,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.11.6 Bounded Product-Gap Step Worth-It Summary",
                "",
                f"- bounded_product_gap_step_worth_it_status: `{worth_it_status}`",
                f"- proposed_next_step_kind: `{proposed_next_step_kind}`",
                f"- expected_information_gain: `{expected_gain}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.11.6 bounded product-gap step worth-it summary.")
    parser.add_argument("--remaining-uncertainty-characterization", required=True)
    parser.add_argument("--out-dir", default=str(DEFAULT_BOUNDED_PRODUCT_GAP_STEP_WORTH_IT_SUMMARY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v116_bounded_product_gap_step_worth_it_summary(
        remaining_uncertainty_characterization_path=str(args.remaining_uncertainty_characterization),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "bounded_product_gap_step_worth_it_status": payload.get("bounded_product_gap_step_worth_it_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
