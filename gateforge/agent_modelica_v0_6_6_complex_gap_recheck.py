from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_6_6_common import (
    DEFAULT_COMPLEX_GAP_RECHECK_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V064_CLOSEOUT_PATH,
    DEFAULT_V065_CLOSEOUT_PATH,
    OPEN_WORLD_MEANINGFUL_IMPROVEMENT_MIN,
    OPEN_WORLD_READY_STABLE_COVERAGE_MIN,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_6_6_handoff_integrity import build_v066_handoff_integrity


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_complex_gap_recheck"


def build_v066_complex_gap_recheck(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    v064_closeout_path: str = str(DEFAULT_V064_CLOSEOUT_PATH),
    v065_closeout_path: str = str(DEFAULT_V065_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_COMPLEX_GAP_RECHECK_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v066_handoff_integrity(out_dir=str(Path(handoff_integrity_path).parent))

    integrity = load_json(handoff_integrity_path)
    v064 = load_json(v064_closeout_path)
    v065 = load_json(v065_closeout_path)

    v064_refinement = v064.get("profile_refinement") or {}
    v065_recheck = v065.get("open_world_recheck") or {}
    v064_conclusion = (v064.get("conclusion") or {})

    complex_pressure = v065_recheck.get("complex_tier_pressure_rechecked") or {}
    complex_tier_stable_coverage_rechecked = float(complex_pressure.get("stable_coverage_complex") or 0.0)
    complex_tier_fragile_share_rechecked = 0.0
    complex_tier_limited_or_uncovered_share_rechecked = 0.0
    if isinstance(v064_refinement.get("fragile_coverage_by_complexity"), dict):
        complex_tier_fragile_share_rechecked = float((v064_refinement.get("fragile_coverage_by_complexity") or {}).get("complex") or 0.0)
    if isinstance(v064_refinement.get("limited_or_uncovered_by_complexity"), dict):
        complex_tier_limited_or_uncovered_share_rechecked = float((v064_refinement.get("limited_or_uncovered_by_complexity") or {}).get("complex") or 0.0)
    complex_tier_pressure_share_rechecked = round(
        complex_tier_fragile_share_rechecked + complex_tier_limited_or_uncovered_share_rechecked,
        1,
    )

    remaining_gap_still_single = (
        str(v065_recheck.get("dominant_remaining_authority_gap") or "") == "complex_tier_pressure_under_representative_logic"
    )
    fluid_network_still_not_blocking = bool(v065_recheck.get("fluid_network_still_not_blocking"))
    legacy_taxonomy_still_sufficient = bool(v065_recheck.get("legacy_taxonomy_still_sufficient"))
    representative_logic_delta = str(v065_recheck.get("representative_logic_delta") or "none")

    open_world_margin_vs_floor_pct_rechecked = float(v065_recheck.get("open_world_margin_vs_floor_pct") or 0.0)
    open_world_candidate_supported_after_gap_recheck = bool(v065_recheck.get("open_world_candidate_supported_after_recheck"))

    previous_margin = float(v064_conclusion.get("near_miss_open_world_candidate") and -2.8 or -999.0)
    # v0.6.5 is the previous calibrated near-miss reference; use the actual v0.6.5 value as the baseline.
    previous_margin = float((v065.get("conclusion") or {}).get("open_world_margin_vs_floor_pct") or 0.0)
    bounded_methods_exhausted_under_current_logic = (
        remaining_gap_still_single
        and (open_world_margin_vs_floor_pct_rechecked - previous_margin) < OPEN_WORLD_MEANINGFUL_IMPROVEMENT_MIN
    )
    phase_closeout_supported = (
        not open_world_candidate_supported_after_gap_recheck
        and remaining_gap_still_single
        and fluid_network_still_not_blocking
        and legacy_taxonomy_still_sufficient
        and bounded_methods_exhausted_under_current_logic
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if integrity.get("status") == "PASS" else "FAIL",
        "complex_tier_stable_coverage_rechecked": complex_tier_stable_coverage_rechecked,
        "complex_tier_fragile_share_rechecked": complex_tier_fragile_share_rechecked,
        "complex_tier_limited_or_uncovered_share_rechecked": complex_tier_limited_or_uncovered_share_rechecked,
        "complex_tier_pressure_share_rechecked": complex_tier_pressure_share_rechecked,
        "remaining_gap_still_single": remaining_gap_still_single,
        "fluid_network_still_not_blocking": fluid_network_still_not_blocking,
        "legacy_taxonomy_still_sufficient": legacy_taxonomy_still_sufficient,
        "representative_logic_delta": representative_logic_delta,
        "open_world_candidate_supported_after_gap_recheck": open_world_candidate_supported_after_gap_recheck,
        "open_world_margin_vs_floor_pct_rechecked": open_world_margin_vs_floor_pct_rechecked,
        "bounded_methods_exhausted_under_current_logic": bounded_methods_exhausted_under_current_logic,
        "phase_closeout_supported": phase_closeout_supported,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.6.6 Complex Gap Recheck",
                "",
                f"- open_world_candidate_supported_after_gap_recheck: `{open_world_candidate_supported_after_gap_recheck}`",
                f"- open_world_margin_vs_floor_pct_rechecked: `{open_world_margin_vs_floor_pct_rechecked}`",
                f"- bounded_methods_exhausted_under_current_logic: `{bounded_methods_exhausted_under_current_logic}`",
                f"- phase_closeout_supported: `{phase_closeout_supported}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.6.6 complex-gap recheck.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--v064-closeout", default=str(DEFAULT_V064_CLOSEOUT_PATH))
    parser.add_argument("--v065-closeout", default=str(DEFAULT_V065_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_COMPLEX_GAP_RECHECK_OUT_DIR))
    args = parser.parse_args()
    payload = build_v066_complex_gap_recheck(
        handoff_integrity_path=str(args.handoff_integrity),
        v064_closeout_path=str(args.v064_closeout),
        v065_closeout_path=str(args.v065_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "phase_closeout_supported": payload.get("phase_closeout_supported")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
