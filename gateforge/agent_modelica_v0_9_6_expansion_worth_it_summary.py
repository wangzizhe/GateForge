from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_9_6_common import (
    DEFAULT_EXPANSION_WORTH_IT_SUMMARY_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v096_expansion_worth_it_summary(
    *,
    remaining_uncertainty_characterization_path: str,
    out_dir: str = str(DEFAULT_EXPANSION_WORTH_IT_SUMMARY_OUT_DIR),
) -> dict:
    uncertainty = load_json(remaining_uncertainty_characterization_path)
    depth_limited = bool(uncertainty.get("remaining_uncertainty_is_depth_limited"))
    expansion_addressable = bool(uncertainty.get("remaining_uncertainty_is_authentic_expansion_addressable"))
    expected_gain = str(uncertainty.get("expected_information_gain") or "")
    status = str(uncertainty.get("remaining_uncertainty_status") or "")

    if (
        status == "single_expansion_addressable_uncertainty"
        and depth_limited
        and expansion_addressable
        and expected_gain == "non_trivial"
    ):
        why = "One more authentic expansion is justified because a single remaining uncertainty still appears depth-limited, addressable under the frozen authenticity discipline, and likely to add non-trivial information."
    else:
        why = "One more authentic expansion is not justified because the current authentic-expansion chain already yields a stable, explainable, threshold-backed partial result and another bounded expansion would likely add only marginal information."

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_expansion_worth_it_summary",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "remaining_uncertainty_status": status,
        "remaining_uncertainty_label": uncertainty.get("remaining_uncertainty_label"),
        "remaining_uncertainty_scope": uncertainty.get("remaining_uncertainty_scope"),
        "remaining_uncertainty_is_depth_limited": depth_limited,
        "remaining_uncertainty_is_authentic_expansion_addressable": expansion_addressable,
        "expected_information_gain": expected_gain,
        "why_one_more_authentic_expansion_is_or_is_not_justified": why,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.6 Expansion Worth-It Summary",
                "",
                f"- remaining_uncertainty_status: `{status}`",
                f"- expected_information_gain: `{expected_gain}`",
                f"- remaining_uncertainty_is_authentic_expansion_addressable: `{expansion_addressable}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.6 expansion worth-it summary.")
    parser.add_argument("--remaining-uncertainty-characterization", required=True)
    parser.add_argument("--out-dir", default=str(DEFAULT_EXPANSION_WORTH_IT_SUMMARY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v096_expansion_worth_it_summary(
        remaining_uncertainty_characterization_path=str(args.remaining_uncertainty_characterization),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "remaining_uncertainty_status": payload.get("remaining_uncertainty_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
