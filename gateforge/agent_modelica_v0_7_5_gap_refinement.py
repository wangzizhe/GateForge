from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_7_5_common import (
    DEFAULT_GAP_REFINEMENT_OUT_DIR,
    DEFAULT_V073_CLOSEOUT_PATH,
    DEFAULT_V074_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)

# Supported floor thresholds (frozen in v0.7.3).
_SUPPORTED_STABLE_COVERAGE_FLOOR = 40.0
_SUPPORTED_SPILLOVER_CEIL = 20.0
_SUPPORTED_LEGACY_MAPPING_FLOOR = 80.0
# Fallback trigger threshold (from v0.7.3 frozen floors).
_FALLBACK_BOUNDED_UNCOVERED_FLOOR = 15.0


def _compute_gap_components(
    stable_coverage: float,
    spillover: float,
    legacy_mapping: float,
) -> dict:
    return {
        "stable_coverage_below_floor": stable_coverage < _SUPPORTED_STABLE_COVERAGE_FLOOR,
        "spillover_above_ceil": spillover > _SUPPORTED_SPILLOVER_CEIL,
        "legacy_mapping_below_floor": legacy_mapping < _SUPPORTED_LEGACY_MAPPING_FLOOR,
    }


def _dominant_remaining_gap(
    stable_margin: float,
    spillover_margin: float,
    legacy_margin: float,
) -> str:
    # Each margin is "distance from passing": negative = failing.
    # For stable and legacy: passing = margin >= 0, failing gap = abs(margin) when < 0.
    # For spillover: passing = margin <= 0, failing gap = margin when > 0.
    gaps: dict[str, float] = {}
    if stable_margin < 0:
        gaps["stable_coverage_below_supported_floor"] = abs(stable_margin)
    if spillover_margin > 0:
        gaps["spillover_above_supported_ceil"] = spillover_margin
    if legacy_margin < 0:
        gaps["legacy_mapping_below_supported_floor"] = abs(legacy_margin)
    if not gaps:
        return "none"
    return max(gaps, key=lambda k: gaps[k])


def build_v075_gap_refinement(
    *,
    v074_closeout_path: str = str(DEFAULT_V074_CLOSEOUT_PATH),
    v073_closeout_path: str = str(DEFAULT_V073_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_GAP_REFINEMENT_OUT_DIR),
) -> dict:
    v074 = load_json(v074_closeout_path)
    v074_conclusion = v074.get("conclusion") or {}

    # Pull v0.7.4 adjudication details for current metric values.
    v074_adjudication = v074.get("adjudication") or {}
    v073 = load_json(v073_closeout_path)
    v073_conclusion = v073.get("conclusion") or {}
    v073_table = v073.get("decision_input_table") or {}

    stable_coverage = float(v073_conclusion.get("stable_coverage_share_pct_stable") or 0.0)
    spillover = float(v073_conclusion.get("spillover_share_pct_stable") or 100.0)
    legacy_mapping = float(v073_conclusion.get("legacy_bucket_mapping_rate_pct_stable") or 0.0)
    bounded_uncovered_share = float(
        v074_adjudication.get("bounded_uncovered_subtype_candidate_share_pct_reference") or 0.0
    )
    dominant_pressure_source = str(
        v074_conclusion.get("dominant_pressure_source_reference") or "unknown"
    )

    # Margins vs supported floor.
    stable_margin = stable_coverage - _SUPPORTED_STABLE_COVERAGE_FLOOR
    spillover_margin = spillover - _SUPPORTED_SPILLOVER_CEIL
    legacy_margin = legacy_mapping - _SUPPORTED_LEGACY_MAPPING_FLOOR

    gap_components = _compute_gap_components(stable_coverage, spillover, legacy_mapping)
    remaining_gap_count = sum(gap_components.values())
    bounded_uncovered_still_subcritical = bounded_uncovered_share < _FALLBACK_BOUNDED_UNCOVERED_FLOOR

    dominant_remaining_gap = (
        _dominant_remaining_gap(stable_margin, spillover_margin, legacy_margin)
        if remaining_gap_count > 0
        else "none"
    )

    same_logic_refinement_explanation = (
        f"Re-analysis of v0.7.4 partial_but_interpretable result under unchanged "
        f"open-world-adjacent logic. "
        f"stable_coverage={stable_coverage:.1f}% (floor={_SUPPORTED_STABLE_COVERAGE_FLOOR}%), "
        f"spillover={spillover:.1f}% (ceil={_SUPPORTED_SPILLOVER_CEIL}%), "
        f"legacy_mapping={legacy_mapping:.1f}% (floor={_SUPPORTED_LEGACY_MAPPING_FLOOR}%). "
        f"remaining_gap_count={remaining_gap_count}. "
        f"dominant_remaining_gap={dominant_remaining_gap}. "
        f"bounded_uncovered_share={bounded_uncovered_share:.1f}% "
        f"(subcritical={bounded_uncovered_still_subcritical})."
    )

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_gap_refinement",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "supported_gap_components": gap_components,
        "stable_coverage_margin_vs_supported_floor_pct": round(stable_margin, 2),
        "spillover_margin_vs_supported_floor_pct": round(spillover_margin, 2),
        "legacy_mapping_margin_vs_supported_floor_pct": round(legacy_margin, 2),
        "bounded_uncovered_still_subcritical": bounded_uncovered_still_subcritical,
        "dominant_remaining_gap_after_refinement": dominant_remaining_gap,
        "remaining_gap_count_after_refinement": remaining_gap_count,
        "same_logic_refinement_explanation": same_logic_refinement_explanation,
        "inputs": {
            "stable_coverage_share_pct": stable_coverage,
            "spillover_share_pct": spillover,
            "legacy_bucket_mapping_rate_pct": legacy_mapping,
            "bounded_uncovered_subtype_candidate_share_pct": bounded_uncovered_share,
            "dominant_pressure_source_reference": dominant_pressure_source,
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.5 Gap Refinement",
                "",
                f"- remaining_gap_count: `{remaining_gap_count}`",
                f"- dominant_remaining_gap: `{dominant_remaining_gap}`",
                f"- stable_coverage_margin: `{stable_margin:+.2f}pp`",
                f"- spillover_margin: `{spillover_margin:+.2f}pp`",
                f"- legacy_mapping_margin: `{legacy_margin:+.2f}pp`",
                f"- bounded_uncovered_still_subcritical: `{bounded_uncovered_still_subcritical}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.5 gap refinement analysis.")
    parser.add_argument("--v074-closeout", default=str(DEFAULT_V074_CLOSEOUT_PATH))
    parser.add_argument("--v073-closeout", default=str(DEFAULT_V073_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_GAP_REFINEMENT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v075_gap_refinement(
        v074_closeout_path=str(args.v074_closeout),
        v073_closeout_path=str(args.v073_closeout),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
