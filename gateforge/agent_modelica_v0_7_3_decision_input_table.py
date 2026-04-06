from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_7_3_common import (
    DEFAULT_DECISION_INPUT_TABLE_OUT_DIR,
    DEFAULT_V071_CLOSEOUT_PATH,
    DEFAULT_V072_CLOSEOUT_PATH,
    FALLBACK_TO_TARGETED_EXPANSION_FLOOR,
    OPEN_WORLD_PARTIAL_FLOOR,
    OPEN_WORLD_SUPPORTED_FLOOR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def _build_complexity_pressure_profile(v071: dict, v072: dict) -> dict:
    baseline = ((v071.get("profile_classification") or {}).get("complexity_breakdown_after_live_run") or {})
    stable = ((v072.get("profile_stability") or {}).get("complexity_breakdown_after_extension") or {})
    dominant = (v072.get("conclusion") or {}).get("dominant_pressure_source_after_extension")
    return {
        "baseline": baseline,
        "stable": stable,
        "dominant": dominant,
        "explainable": dominant not in {None, "unknown"},
    }


def _build_family_pressure_profile(v072: dict) -> dict:
    family_breakdown = ((v072.get("profile_stability") or {}).get("family_breakdown_after_extension") or {})
    pressure_ranking = sorted(
        (
            {
                "family_id": family_id,
                "limited_or_uncovered": int(values.get("limited_or_uncovered") or 0),
                "fragile": int(values.get("fragile") or 0),
                "stable": int(values.get("stable") or 0),
            }
            for family_id, values in family_breakdown.items()
        ),
        key=lambda item: (item["limited_or_uncovered"], item["fragile"]),
        reverse=True,
    )
    return {
        "family_breakdown_after_extension": family_breakdown,
        "pressure_ranking": pressure_ranking,
    }


def build_v073_decision_input_table(
    *,
    v071_closeout_path: str = str(DEFAULT_V071_CLOSEOUT_PATH),
    v072_closeout_path: str = str(DEFAULT_V072_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_DECISION_INPUT_TABLE_OUT_DIR),
) -> dict:
    v071 = load_json(v071_closeout_path)
    v072 = load_json(v072_closeout_path)

    baseline_conclusion = v071.get("conclusion") or {}
    stable_conclusion = v072.get("conclusion") or {}
    baseline_classification = v071.get("profile_classification") or {}

    stable_coverage_share_pct_baseline = float(baseline_conclusion.get("stable_coverage_share_pct") or 0.0)
    stable_coverage_share_pct_stable = float(stable_conclusion.get("stable_coverage_share_pct_after_extension") or 0.0)
    spillover_share_pct_baseline = float(baseline_conclusion.get("spillover_share_pct_after_live_run") or 0.0)
    spillover_share_pct_stable = float(stable_conclusion.get("spillover_share_pct_after_extension") or 0.0)
    legacy_bucket_mapping_rate_pct_baseline = float(
        baseline_conclusion.get("legacy_bucket_mapping_rate_pct_after_live_run") or 0.0
    )
    legacy_bucket_mapping_rate_pct_stable = float(
        stable_conclusion.get("legacy_bucket_mapping_rate_pct_after_extension") or 0.0
    )

    stable_coverage_margin_delta_pct = round(
        stable_coverage_share_pct_stable - OPEN_WORLD_SUPPORTED_FLOOR["stable_coverage_share_pct"], 1
    )
    spillover_delta_pct = round(
        spillover_share_pct_stable - OPEN_WORLD_SUPPORTED_FLOOR["spillover_share_pct"], 1
    )
    bounded_uncovered_share_pct_baseline = round(
        100.0
        * float((baseline_classification.get("bucket_counts") or {}).get("bounded_uncovered_subtype_candidate") or 0)
        / max(float((baseline_classification.get("bucket_counts") or {}).get("covered_success") or 0)
              + float((baseline_classification.get("bucket_counts") or {}).get("covered_but_fragile") or 0)
              + float((baseline_classification.get("bucket_counts") or {}).get("dispatch_or_policy_limited") or 0)
              + float((baseline_classification.get("bucket_counts") or {}).get("bounded_uncovered_subtype_candidate") or 0)
              + float((baseline_classification.get("bucket_counts") or {}).get("topology_or_open_world_spillover") or 0)
              + float((baseline_classification.get("bucket_counts") or {}).get("unclassified_pending_taxonomy") or 0), 1.0),
        1,
    )

    complexity_pressure_profile = _build_complexity_pressure_profile(v071, v072)
    family_pressure_profile = _build_family_pressure_profile(v072)

    if stable_coverage_share_pct_stable >= OPEN_WORLD_SUPPORTED_FLOOR["stable_coverage_share_pct"]:
        open_world_candidate_gap_summary = "supported_floor_met"
    elif (
        stable_coverage_share_pct_stable >= OPEN_WORLD_PARTIAL_FLOOR["stable_coverage_share_pct"]
        and complexity_pressure_profile["dominant"] == "complexity:complex"
    ):
        open_world_candidate_gap_summary = "single_gap_complexity_complex_near_supported_floor"
    else:
        open_world_candidate_gap_summary = "multi_gap_or_non_single_gap"

    decision_input_table_complete = all(
        [
            complexity_pressure_profile["explainable"],
            bool(family_pressure_profile["pressure_ranking"]),
            open_world_candidate_gap_summary is not None,
        ]
    )

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_decision_input_table",
        "generated_at_utc": now_utc(),
        "status": "PASS" if decision_input_table_complete else "FAIL",
        "stable_coverage_share_pct_baseline": stable_coverage_share_pct_baseline,
        "stable_coverage_share_pct_stable": stable_coverage_share_pct_stable,
        "stable_coverage_margin_delta_pct": stable_coverage_margin_delta_pct,
        "spillover_share_pct_baseline": spillover_share_pct_baseline,
        "spillover_share_pct_stable": spillover_share_pct_stable,
        "spillover_delta_pct": spillover_delta_pct,
        "legacy_bucket_mapping_rate_pct_baseline": legacy_bucket_mapping_rate_pct_baseline,
        "legacy_bucket_mapping_rate_pct_stable": legacy_bucket_mapping_rate_pct_stable,
        "bounded_uncovered_subtype_candidate_share_pct_baseline": bounded_uncovered_share_pct_baseline,
        "complexity_pressure_profile": complexity_pressure_profile,
        "family_pressure_profile": family_pressure_profile,
        "open_world_candidate_gap_summary": open_world_candidate_gap_summary,
        "decision_input_table_complete": decision_input_table_complete,
        "v0_7_4_open_world_readiness_supported_floor": OPEN_WORLD_SUPPORTED_FLOOR,
        "v0_7_4_open_world_readiness_partial_floor": OPEN_WORLD_PARTIAL_FLOOR,
        "v0_7_4_fallback_to_targeted_expansion_floor": FALLBACK_TO_TARGETED_EXPANSION_FLOOR,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.3 Decision Input Table",
                "",
                f"- stable_coverage_share_pct_stable: `{stable_coverage_share_pct_stable}`",
                f"- spillover_share_pct_stable: `{spillover_share_pct_stable}`",
                f"- legacy_bucket_mapping_rate_pct_stable: `{legacy_bucket_mapping_rate_pct_stable}`",
                f"- open_world_candidate_gap_summary: `{open_world_candidate_gap_summary}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.3 decision input table.")
    parser.add_argument("--v071-closeout", default=str(DEFAULT_V071_CLOSEOUT_PATH))
    parser.add_argument("--v072-closeout", default=str(DEFAULT_V072_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_DECISION_INPUT_TABLE_OUT_DIR))
    args = parser.parse_args()
    payload = build_v073_decision_input_table(
        v071_closeout_path=str(args.v071_closeout),
        v072_closeout_path=str(args.v072_closeout),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
