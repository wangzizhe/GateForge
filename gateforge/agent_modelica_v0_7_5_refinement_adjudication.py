from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_7_5_common import (
    DEFAULT_GAP_REFINEMENT_OUT_DIR,
    DEFAULT_REFINEMENT_ADJUDICATION_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v075_refinement_adjudication(
    *,
    gap_refinement_path: str = str(DEFAULT_GAP_REFINEMENT_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_REFINEMENT_ADJUDICATION_OUT_DIR),
) -> dict:
    refinement = load_json(gap_refinement_path)

    stable_margin = float(refinement.get("stable_coverage_margin_vs_supported_floor_pct") or -999.0)
    spillover_margin = float(refinement.get("spillover_margin_vs_supported_floor_pct") or 999.0)
    legacy_margin = float(refinement.get("legacy_mapping_margin_vs_supported_floor_pct") or -999.0)
    bounded_uncovered_subcritical = bool(refinement.get("bounded_uncovered_still_subcritical"))
    dominant_remaining_gap = str(
        refinement.get("dominant_remaining_gap_after_refinement") or "unknown"
    )
    remaining_gap_count = int(refinement.get("remaining_gap_count_after_refinement") or 0)

    # Step 3 adjudication per PLAN_V0_7_5.
    supported_conditions_met = (
        stable_margin >= 0
        and spillover_margin <= 0
        and legacy_margin >= 0
        and bounded_uncovered_subcritical
    )

    # Invalid triggers (any one is sufficient).
    invalid_bounded_uncovered = not bounded_uncovered_subcritical
    invalid_zero_gap_not_supported = (remaining_gap_count == 0) and not supported_conditions_met
    invalid_multi_gap = remaining_gap_count > 1
    invalid_unknown_dominant = dominant_remaining_gap in ("unknown", "")

    is_invalid = (
        invalid_bounded_uncovered
        or invalid_zero_gap_not_supported
        or invalid_multi_gap
        or invalid_unknown_dominant
    )

    if is_invalid:
        status = "invalid"
    elif supported_conditions_met:
        status = "supported"
    elif (
        bounded_uncovered_subcritical
        and remaining_gap_count == 1
        and dominant_remaining_gap not in ("unknown", "", "none")
    ):
        status = "partial_but_interpretable"
    else:
        # Residual — should be unreachable given the invalid catches above, but defensive.
        status = "invalid"

    invalid_reasons: list[str] = []
    if invalid_bounded_uncovered:
        invalid_reasons.append("bounded_uncovered_not_subcritical")
    if invalid_zero_gap_not_supported:
        invalid_reasons.append("remaining_gap_count_zero_but_not_supported")
    if invalid_multi_gap:
        invalid_reasons.append("remaining_gap_count_greater_than_one")
    if invalid_unknown_dominant:
        invalid_reasons.append("dominant_remaining_gap_unknown")

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_refinement_adjudication",
        "generated_at_utc": now_utc(),
        "status": "PASS" if status != "invalid" else "FAIL",
        "readiness_refinement_status": status,
        "stable_coverage_margin_vs_supported_floor_pct": stable_margin,
        "spillover_margin_vs_supported_floor_pct": spillover_margin,
        "legacy_mapping_margin_vs_supported_floor_pct": legacy_margin,
        "bounded_uncovered_still_subcritical": bounded_uncovered_subcritical,
        "dominant_remaining_gap_after_refinement": dominant_remaining_gap,
        "remaining_gap_count_after_refinement": remaining_gap_count,
        "invalid_reasons": invalid_reasons,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.5 Refinement Adjudication",
                "",
                f"- readiness_refinement_status: `{status}`",
                f"- stable_coverage_margin: `{stable_margin:+.2f}pp`",
                f"- spillover_margin: `{spillover_margin:+.2f}pp`",
                f"- legacy_mapping_margin: `{legacy_margin:+.2f}pp`",
                f"- remaining_gap_count: `{remaining_gap_count}`",
                f"- dominant_remaining_gap: `{dominant_remaining_gap}`",
                f"- bounded_uncovered_still_subcritical: `{bounded_uncovered_subcritical}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.5 refinement adjudication.")
    parser.add_argument(
        "--gap-refinement",
        default=str(DEFAULT_GAP_REFINEMENT_OUT_DIR / "summary.json"),
    )
    parser.add_argument("--out-dir", default=str(DEFAULT_REFINEMENT_ADJUDICATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v075_refinement_adjudication(
        gap_refinement_path=str(args.gap_refinement),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
