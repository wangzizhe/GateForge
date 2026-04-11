from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_11_6_bounded_product_gap_step_worth_it_summary import (
    build_v116_bounded_product_gap_step_worth_it_summary,
)
from .agent_modelica_v0_11_6_common import (
    DEFAULT_BOUNDED_PRODUCT_GAP_STEP_WORTH_IT_SUMMARY_OUT_DIR,
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_REMAINING_UNCERTAINTY_CHARACTERIZATION_OUT_DIR,
    DEFAULT_V115_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_11_6_handoff_integrity import build_v116_handoff_integrity
from .agent_modelica_v0_11_6_remaining_uncertainty_characterization import (
    build_v116_remaining_uncertainty_characterization,
)


def build_v116_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    remaining_uncertainty_characterization_path: str = str(
        DEFAULT_REMAINING_UNCERTAINTY_CHARACTERIZATION_OUT_DIR / "summary.json"
    ),
    bounded_product_gap_step_worth_it_summary_path: str = str(
        DEFAULT_BOUNDED_PRODUCT_GAP_STEP_WORTH_IT_SUMMARY_OUT_DIR / "summary.json"
    ),
    v115_closeout_path: str = str(DEFAULT_V115_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    build_v116_handoff_integrity(
        v115_closeout_path=v115_closeout_path,
        out_dir=str(Path(handoff_integrity_path).parent),
    )
    integrity = load_json(handoff_integrity_path)
    if integrity.get("handoff_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_11_6_PRODUCT_GAP_NEXT_STEP_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_11_6_product_gap_next_step_inputs_invalid",
                "v0_11_7_handoff_mode": "rebuild_v0_11_6_inputs_first",
            },
            "handoff_integrity": integrity,
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.11.6 Closeout\n\n- version_decision: `v0_11_6_product_gap_next_step_inputs_invalid`\n")
        return payload

    if not Path(remaining_uncertainty_characterization_path).exists():
        build_v116_remaining_uncertainty_characterization(
            v115_closeout_path=v115_closeout_path,
            out_dir=str(Path(remaining_uncertainty_characterization_path).parent),
        )
    if not Path(bounded_product_gap_step_worth_it_summary_path).exists():
        build_v116_bounded_product_gap_step_worth_it_summary(
            remaining_uncertainty_characterization_path=remaining_uncertainty_characterization_path,
            out_dir=str(Path(bounded_product_gap_step_worth_it_summary_path).parent),
        )

    uncertainty = load_json(remaining_uncertainty_characterization_path)
    summary = load_json(bounded_product_gap_step_worth_it_summary_path)

    worth_it_status = str(summary.get("bounded_product_gap_step_worth_it_status") or "")
    expected_gain = str(summary.get("expected_information_gain") or "")
    step_addressable = bool(uncertainty.get("remaining_uncertainty_is_step_addressable"))
    phase_relevant = bool(uncertainty.get("remaining_uncertainty_is_phase_relevant"))

    justified = (
        worth_it_status == "one_more_bounded_product_gap_step_justified"
        and step_addressable
        and phase_relevant
        and expected_gain == "non_marginal"
    )
    invalid = any(
        [
            not str(uncertainty.get("remaining_uncertainty_status") or ""),
            not str(summary.get("bounded_product_gap_step_worth_it_status") or ""),
            uncertainty.get("expected_information_gain") != summary.get("expected_information_gain"),
        ]
    )

    if invalid:
        decision = "v0_11_6_product_gap_next_step_inputs_invalid"
        handoff = "rebuild_v0_11_6_inputs_first"
        status = "FAIL"
        closeout_status = "V0_11_6_PRODUCT_GAP_NEXT_STEP_INPUTS_INVALID"
    elif justified:
        decision = "v0_11_6_one_more_bounded_product_gap_step_justified"
        handoff = "execute_one_more_bounded_product_gap_step_before_phase_synthesis"
        status = "PASS"
        closeout_status = "V0_11_6_ONE_MORE_BOUNDED_PRODUCT_GAP_STEP_JUSTIFIED"
    else:
        decision = "v0_11_6_more_bounded_product_gap_step_not_worth_it"
        handoff = "prepare_v0_11_phase_synthesis"
        status = "PASS"
        closeout_status = "V0_11_6_MORE_BOUNDED_PRODUCT_GAP_STEP_NOT_WORTH_IT"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": closeout_status,
        "conclusion": {
            "version_decision": decision,
            "remaining_uncertainty_status": uncertainty.get("remaining_uncertainty_status"),
            "remaining_uncertainty_label": uncertainty.get("remaining_uncertainty_label"),
            "expected_information_gain": uncertainty.get("expected_information_gain"),
            "proposed_next_step_kind": summary.get("proposed_next_step_kind"),
            "why_one_more_step_is_or_is_not_worth_it": summary.get("why_one_more_step_is_or_is_not_worth_it"),
            "v0_11_7_handoff_mode": handoff,
        },
        "handoff_integrity": integrity,
        "remaining_uncertainty_characterization": uncertainty,
        "bounded_product_gap_step_worth_it_summary": summary,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.11.6 Closeout",
                "",
                f"- version_decision: `{decision}`",
                f"- remaining_uncertainty_status: `{uncertainty.get('remaining_uncertainty_status')}`",
                f"- expected_information_gain: `{uncertainty.get('expected_information_gain')}`",
                f"- v0_11_7_handoff_mode: `{handoff}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.11.6 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument(
        "--remaining-uncertainty-characterization",
        default=str(DEFAULT_REMAINING_UNCERTAINTY_CHARACTERIZATION_OUT_DIR / "summary.json"),
    )
    parser.add_argument(
        "--bounded-product-gap-step-worth-it-summary",
        default=str(DEFAULT_BOUNDED_PRODUCT_GAP_STEP_WORTH_IT_SUMMARY_OUT_DIR / "summary.json"),
    )
    parser.add_argument("--v115-closeout", default=str(DEFAULT_V115_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v116_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        remaining_uncertainty_characterization_path=str(args.remaining_uncertainty_characterization),
        bounded_product_gap_step_worth_it_summary_path=str(args.bounded_product_gap_step_worth_it_summary),
        v115_closeout_path=str(args.v115_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
