from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_7_4_common import (
    DEFAULT_ADJUDICATION_OUT_DIR,
    DEFAULT_V073_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v074_adjudication(
    *,
    v073_closeout_path: str = str(DEFAULT_V073_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_ADJUDICATION_OUT_DIR),
) -> dict:
    closeout = load_json(v073_closeout_path)
    conclusion = closeout.get("conclusion") or {}
    table = closeout.get("decision_input_table") or {}

    stable_coverage = float(conclusion.get("stable_coverage_share_pct_stable") or 0.0)
    spillover = float(conclusion.get("spillover_share_pct_stable") or 100.0)
    legacy_mapping = float(conclusion.get("legacy_bucket_mapping_rate_pct_stable") or 0.0)
    dominant_pressure_source_reference = str(
        ((conclusion.get("complexity_pressure_profile") or {}).get("dominant")) or "unknown"
    )
    bounded_uncovered_share = float(table.get("bounded_uncovered_subtype_candidate_share_pct_baseline") or 0.0)
    gap_summary = str(conclusion.get("open_world_candidate_gap_summary") or "unknown")

    supported_floor = conclusion.get("v0_7_4_open_world_readiness_supported_floor") or {}
    partial_floor = conclusion.get("v0_7_4_open_world_readiness_partial_floor") or {}
    fallback_floor = conclusion.get("v0_7_4_fallback_to_targeted_expansion_floor") or {}

    supported_floor_check = {
        "stable_coverage_share_pct": stable_coverage >= float(supported_floor.get("stable_coverage_share_pct") or 0.0),
        "spillover_share_pct": spillover <= float(supported_floor.get("spillover_share_pct") or 0.0),
        "legacy_bucket_mapping_rate_pct": legacy_mapping >= float(supported_floor.get("legacy_bucket_mapping_rate_pct") or 0.0),
        "dominant_pressure_known": dominant_pressure_source_reference != "unknown",
        "bounded_uncovered_not_reemergent": bounded_uncovered_share < float(fallback_floor.get("bounded_uncovered_subtype_candidate_share_pct") or 100.0),
    }
    partial_floor_check = {
        "stable_coverage_share_pct": stable_coverage >= float(partial_floor.get("stable_coverage_share_pct") or 0.0),
        "spillover_share_pct": spillover <= float(partial_floor.get("spillover_share_pct") or 0.0),
        "legacy_bucket_mapping_rate_pct": legacy_mapping >= float(partial_floor.get("legacy_bucket_mapping_rate_pct") or 0.0),
        "dominant_pressure_known": dominant_pressure_source_reference != "unknown",
        "legacy_taxonomy_still_interpretable": True,
    }
    fallback_floor_check = {
        "bounded_uncovered_subtype_candidate_share_pct": bounded_uncovered_share >= float(
            fallback_floor.get("bounded_uncovered_subtype_candidate_share_pct") or 100.0
        ),
        "bounded_uncovered_is_dominant_gap": gap_summary == "bounded_uncovered_reemergent",
        "failure_mode_not_primarily_open_world_readiness": gap_summary == "bounded_uncovered_reemergent",
    }

    supported_floor_passed = all(supported_floor_check.values())
    partial_floor_passed = all(partial_floor_check.values())
    fallback_floor_passed = any(fallback_floor_check.values())

    route_count = 0
    if supported_floor_passed and not fallback_floor_passed:
        route_count += 1
    if (not supported_floor_passed) and partial_floor_passed and not fallback_floor_passed:
        route_count += 1
    if fallback_floor_passed:
        route_count += 1

    if route_count != 1 or dominant_pressure_source_reference == "unknown":
        status = "invalid"
    elif supported_floor_passed and not fallback_floor_passed:
        status = "supported"
    elif fallback_floor_passed:
        status = "fallback_to_targeted_expansion_needed"
    else:
        status = "partial_but_interpretable"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_adjudication",
        "generated_at_utc": now_utc(),
        "status": "PASS" if status != "invalid" else "FAIL",
        "readiness_adjudication_status": status,
        "supported_floor_check": supported_floor_check,
        "partial_floor_check": partial_floor_check,
        "fallback_floor_check": fallback_floor_check,
        "supported_floor_passed": supported_floor_passed,
        "partial_floor_passed": partial_floor_passed,
        "fallback_floor_passed": fallback_floor_passed,
        "bounded_uncovered_subtype_candidate_share_pct_reference": bounded_uncovered_share,
        "dominant_pressure_source_reference": dominant_pressure_source_reference,
        "readiness_adjudication_route_count": route_count,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.4 Adjudication",
                "",
                f"- readiness_adjudication_status: `{status}`",
                f"- supported_floor_passed: `{supported_floor_passed}`",
                f"- partial_floor_passed: `{partial_floor_passed}`",
                f"- fallback_floor_passed: `{fallback_floor_passed}`",
                f"- readiness_adjudication_route_count: `{route_count}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.4 readiness adjudication.")
    parser.add_argument("--v073-closeout", default=str(DEFAULT_V073_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_ADJUDICATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v074_adjudication(
        v073_closeout_path=str(args.v073_closeout),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
