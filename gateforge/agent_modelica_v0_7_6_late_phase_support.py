from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_7_6_common import (
    CLOSEOUT_SUPPORT_GAP_MAX,
    DEFAULT_LATE_PHASE_SUPPORT_OUT_DIR,
    DEFAULT_V074_CLOSEOUT_PATH,
    DEFAULT_V075_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    SUPPORTED_STABLE_COVERAGE_FLOOR,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v076_late_phase_support(
    *,
    v075_closeout_path: str = str(DEFAULT_V075_CLOSEOUT_PATH),
    v074_closeout_path: str = str(DEFAULT_V074_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_LATE_PHASE_SUPPORT_OUT_DIR),
) -> dict:
    v075 = load_json(v075_closeout_path)
    v075_conclusion = v075.get("conclusion") or {}
    v074 = load_json(v074_closeout_path)
    v074_conclusion = v074.get("conclusion") or {}

    stable_margin = float(v075_conclusion.get("stable_coverage_margin_vs_supported_floor_pct") or 0.0)
    spillover_margin = float(
        v075_conclusion.get("spillover_margin_vs_supported_floor_pct") or 999.0
    )
    legacy_margin = float(
        v075_conclusion.get("legacy_mapping_margin_vs_supported_floor_pct") or -999.0
    )
    gap_magnitude_pct = round(abs(stable_margin), 2)

    v074_supported_passed = v074_conclusion.get("supported_floor_passed") is True
    v074_partial_passed = v074_conclusion.get("partial_floor_passed") is True
    v074_fallback_passed = v074_conclusion.get("fallback_floor_passed") is True

    single_gap_still_holds = (
        v075_conclusion.get("remaining_gap_count_after_refinement") == 1
        and v075_conclusion.get("dominant_remaining_gap_after_refinement")
        == "stable_coverage_below_supported_floor"
    )
    bounded_uncovered_still_subcritical = (
        v075_conclusion.get("bounded_uncovered_still_subcritical") is True
    )
    spillover_still_not_blocking = spillover_margin <= 0
    legacy_mapping_still_strong = legacy_margin >= 0
    new_multi_gap_signal_present = (
        int(v075_conclusion.get("remaining_gap_count_after_refinement") or 0) > 1
    )
    new_targeted_expansion_pressure_present = v074_fallback_passed

    # Same-logic persistence across v0.7.4 and v0.7.5:
    # v0.7.4 still partial without fallback; v0.7.5 keeps a single stable-coverage gap.
    same_gap_persists_across_versions = (
        v074_supported_passed is False
        and v074_partial_passed is True
        and v074_fallback_passed is False
        and single_gap_still_holds
    )
    gap_magnitude_small_enough = (
        gap_magnitude_pct <= CLOSEOUT_SUPPORT_GAP_MAX and same_gap_persists_across_versions
    )

    if new_multi_gap_signal_present:
        support_basis = "new_multi_gap_reopened"
    elif new_targeted_expansion_pressure_present:
        support_basis = "new_targeted_expansion_pressure_reopened"
    elif not single_gap_still_holds:
        support_basis = "single_gap_no_longer_holds"
    elif gap_magnitude_small_enough:
        support_basis = "single_gap_small_and_persistent_under_same_logic"
    elif gap_magnitude_pct > CLOSEOUT_SUPPORT_GAP_MAX:
        support_basis = "gap_still_too_large_for_closeout_support"
    else:
        support_basis = "unknown"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_late_phase_support",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "single_gap_still_holds": single_gap_still_holds,
        "gap_magnitude_pct": gap_magnitude_pct,
        "gap_magnitude_small_enough_for_closeout_support": gap_magnitude_small_enough,
        "bounded_uncovered_still_subcritical": bounded_uncovered_still_subcritical,
        "spillover_still_not_blocking": spillover_still_not_blocking,
        "legacy_mapping_still_strong": legacy_mapping_still_strong,
        "new_multi_gap_signal_present": new_multi_gap_signal_present,
        "new_targeted_expansion_pressure_present": new_targeted_expansion_pressure_present,
        "late_phase_closeout_support_basis": support_basis,
        "supported_stable_coverage_floor_pct": SUPPORTED_STABLE_COVERAGE_FLOOR,
        "stable_coverage_margin_vs_supported_floor_pct": stable_margin,
        "spillover_margin_vs_supported_floor_pct": spillover_margin,
        "legacy_mapping_margin_vs_supported_floor_pct": legacy_margin,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.6 Late-Phase Support",
                "",
                f"- single_gap_still_holds: `{single_gap_still_holds}`",
                f"- gap_magnitude_pct: `{gap_magnitude_pct:.2f}`",
                f"- gap_magnitude_small_enough_for_closeout_support: `{gap_magnitude_small_enough}`",
                f"- bounded_uncovered_still_subcritical: `{bounded_uncovered_still_subcritical}`",
                f"- spillover_still_not_blocking: `{spillover_still_not_blocking}`",
                f"- legacy_mapping_still_strong: `{legacy_mapping_still_strong}`",
                f"- new_multi_gap_signal_present: `{new_multi_gap_signal_present}`",
                f"- new_targeted_expansion_pressure_present: `{new_targeted_expansion_pressure_present}`",
                f"- late_phase_closeout_support_basis: `{support_basis}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.6 late-phase support table.")
    parser.add_argument("--v075-closeout", default=str(DEFAULT_V075_CLOSEOUT_PATH))
    parser.add_argument("--v074-closeout", default=str(DEFAULT_V074_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_LATE_PHASE_SUPPORT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v076_late_phase_support(
        v075_closeout_path=str(args.v075_closeout),
        v074_closeout_path=str(args.v074_closeout),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
