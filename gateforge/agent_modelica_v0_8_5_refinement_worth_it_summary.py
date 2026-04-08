from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_8_5_common import (
    DEFAULT_REFINEMENT_WORTH_IT_SUMMARY_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v085_refinement_worth_it_summary(
    *,
    remaining_gap_characterization_path: str,
    out_dir: str = str(DEFAULT_REFINEMENT_WORTH_IT_SUMMARY_OUT_DIR),
) -> dict:
    gap = load_json(remaining_gap_characterization_path)
    threshold_proximal = bool(gap.get("remaining_gap_is_threshold_proximal"))
    same_logic_addressable = bool(gap.get("remaining_gap_is_same_logic_addressable"))
    expected_gain = str(gap.get("expected_information_gain") or "")
    status = str(gap.get("remaining_gap_status") or "")

    if status == "single_refinable_gap" and threshold_proximal and same_logic_addressable and expected_gain == "non_trivial":
        why = "One more same-logic refinement is justified because the remaining gap is singular, threshold-proximal, addressable under the current logic, and still promises non-trivial information gain."
    else:
        why = "One more same-logic refinement is not justified because the remaining gap is either too far from the supported boundary, not addressable under the frozen execution posture, or only promises marginal information gain."

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_refinement_worth_it_summary",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "remaining_gap_status": status,
        "remaining_gap_label": gap.get("remaining_gap_label"),
        "remaining_gap_magnitude_pct": gap.get("remaining_gap_magnitude_pct"),
        "remaining_gap_is_threshold_proximal": threshold_proximal,
        "remaining_gap_is_same_logic_addressable": same_logic_addressable,
        "expected_information_gain": expected_gain,
        "why_one_more_same_logic_refinement_is_or_is_not_justified": why,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.8.5 Refinement Worth-It Summary",
                "",
                f"- remaining_gap_status: `{status}`",
                f"- expected_information_gain: `{expected_gain}`",
                f"- remaining_gap_is_same_logic_addressable: `{same_logic_addressable}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.8.5 refinement worth-it summary.")
    parser.add_argument("--remaining-gap-characterization", required=True)
    parser.add_argument("--out-dir", default=str(DEFAULT_REFINEMENT_WORTH_IT_SUMMARY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v085_refinement_worth_it_summary(
        remaining_gap_characterization_path=str(args.remaining_gap_characterization),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "remaining_gap_status": payload.get("remaining_gap_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
