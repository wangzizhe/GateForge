from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_6_5_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_OPEN_WORLD_RECHECK_OUT_DIR,
    DEFAULT_V064_CLOSEOUT_PATH,
    OPEN_WORLD_READY_STABLE_COVERAGE_MIN,
    COMPLEX_PRESSURE_SHARE_MIN,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    pct,
    write_json,
    write_text,
)
from .agent_modelica_v0_6_5_handoff_integrity import build_v065_handoff_integrity


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_open_world_recheck"


def build_v065_open_world_recheck(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    v064_closeout_path: str = str(DEFAULT_V064_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_OPEN_WORLD_RECHECK_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v065_handoff_integrity(out_dir=str(Path(handoff_integrity_path).parent))

    integrity = load_json(handoff_integrity_path)
    v064 = load_json(v064_closeout_path)
    refinement = v064.get("profile_refinement") or {}
    candidate = v064.get("candidate_pressure") or {}

    stable_coverage_share_pct_rechecked = float(candidate.get("stable_coverage_share_pct") or 0.0)
    fragile_pressure_share_pct_rechecked = float((v064.get("phase_decision_input") or {}).get("fragile_coverage_share_pct") or 0.0)
    if not fragile_pressure_share_pct_rechecked:
        fragile_pressure_share_pct_rechecked = float((v064.get("profile_refinement") or {}).get("fragile_coverage_by_family", {}).get("component_api_alignment", 0.0))

    stable_coverage_by_complexity = refinement.get("stable_coverage_by_complexity") or {}
    complex_tier_pressure_rechecked = {
        "stable_coverage_complex": float(stable_coverage_by_complexity.get("complex") or 0.0),
        "stable_coverage_medium": float(stable_coverage_by_complexity.get("medium") or 0.0),
        "stable_coverage_simple": float(stable_coverage_by_complexity.get("simple") or 0.0),
        "complex_pressure_count": int((refinement.get("complexity_pressure_counts") or {}).get("complex") or 0),
        "total_pressure_case_count": int(refinement.get("total_pressure_case_count") or 0),
    }

    fluid_network_subprofile_rechecked = refinement.get("fluid_network_pressure_subprofile") or {}
    representative_logic_delta = refinement.get("representative_logic_delta") or "unknown"
    legacy_taxonomy_still_sufficient = bool(refinement.get("legacy_taxonomy_still_sufficient"))

    topology_or_open_world_spillover_share_pct = float(candidate.get("topology_or_open_world_spillover_share_pct") or 0.0)
    fluid_network_still_not_blocking = candidate.get("fluid_network_extension_blocking_open_world") is False
    open_world_candidate_supported_after_recheck = (
        stable_coverage_share_pct_rechecked >= OPEN_WORLD_READY_STABLE_COVERAGE_MIN
        and topology_or_open_world_spillover_share_pct <= 10.0
        and fluid_network_still_not_blocking
    )
    open_world_margin_vs_floor_pct = round(stable_coverage_share_pct_rechecked - OPEN_WORLD_READY_STABLE_COVERAGE_MIN, 1)

    complex_pressure_share = pct(
        complex_tier_pressure_rechecked["complex_pressure_count"],
        complex_tier_pressure_rechecked["total_pressure_case_count"],
    )
    complex_tier_pressure_is_primary_gap = (
        complex_tier_pressure_rechecked["stable_coverage_complex"] < complex_tier_pressure_rechecked["stable_coverage_simple"]
        and complex_tier_pressure_rechecked["stable_coverage_complex"] < complex_tier_pressure_rechecked["stable_coverage_medium"]
        and complex_pressure_share >= COMPLEX_PRESSURE_SHARE_MIN
    )

    if open_world_candidate_supported_after_recheck:
        dominant_remaining_authority_gap = "none"
    elif complex_tier_pressure_is_primary_gap:
        dominant_remaining_authority_gap = "complex_tier_pressure_under_representative_logic"
    else:
        dominant_remaining_authority_gap = "stable_coverage_floor_not_yet_met"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if integrity.get("status") == "PASS" else "FAIL",
        "stable_coverage_share_pct_rechecked": stable_coverage_share_pct_rechecked,
        "fragile_pressure_share_pct_rechecked": fragile_pressure_share_pct_rechecked,
        "complex_tier_pressure_rechecked": complex_tier_pressure_rechecked,
        "fluid_network_subprofile_rechecked": fluid_network_subprofile_rechecked,
        "representative_logic_delta": representative_logic_delta,
        "legacy_taxonomy_still_sufficient": legacy_taxonomy_still_sufficient,
        "open_world_candidate_supported_after_recheck": open_world_candidate_supported_after_recheck,
        "open_world_margin_vs_floor_pct": open_world_margin_vs_floor_pct,
        "dominant_remaining_authority_gap": dominant_remaining_authority_gap,
        "complex_tier_pressure_is_primary_gap": complex_tier_pressure_is_primary_gap,
        "fluid_network_still_not_blocking": fluid_network_still_not_blocking,
        "topology_or_open_world_spillover_share_pct": topology_or_open_world_spillover_share_pct,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.6.5 Open World Recheck",
                "",
                f"- open_world_candidate_supported_after_recheck: `{open_world_candidate_supported_after_recheck}`",
                f"- open_world_margin_vs_floor_pct: `{open_world_margin_vs_floor_pct}`",
                f"- dominant_remaining_authority_gap: `{dominant_remaining_authority_gap}`",
                f"- complex_tier_pressure_is_primary_gap: `{complex_tier_pressure_is_primary_gap}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.6.5 open-world recheck.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--v064-closeout", default=str(DEFAULT_V064_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_OPEN_WORLD_RECHECK_OUT_DIR))
    args = parser.parse_args()
    payload = build_v065_open_world_recheck(
        handoff_integrity_path=str(args.handoff_integrity),
        v064_closeout_path=str(args.v064_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "open_world_margin_vs_floor_pct": payload.get("open_world_margin_vs_floor_pct")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
