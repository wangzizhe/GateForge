from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_8_3_common import (
    DEFAULT_THRESHOLD_VALIDATION_REPLAY_PACK_OUT_DIR,
    DEFAULT_THRESHOLD_VALIDATION_SUMMARY_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v083_threshold_validation_summary(
    *,
    validation_replay_pack_path: str = str(DEFAULT_THRESHOLD_VALIDATION_REPLAY_PACK_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_THRESHOLD_VALIDATION_SUMMARY_OUT_DIR),
) -> dict:
    replay = load_json(validation_replay_pack_path)
    runs = list(replay.get("validation_runs") or [])
    route_counts = [int(run.get("route_count_per_run") or 0) for run in runs]
    observed_routes = [str(run.get("adjudication_route") or "") for run in runs]
    expected = "workflow_readiness_partial_but_interpretable"
    observed = replay.get("canonical_adjudication_route")
    pack_overlap = any(count > 1 for count in route_counts)
    pack_under_specified = any(count == 0 for count in route_counts)
    flip_count = int(replay.get("adjudication_route_flip_count") or 0)
    boundary_crossing_flags = [bool(run.get("flip_coincides_with_boundary_crossing")) for run in runs]

    if flip_count == 0:
        flip_coincides = "not_applicable"
        flip_root_cause = "not_applicable"
    elif all(boundary_crossing_flags):
        flip_coincides = True
        flip_root_cause = "boundary_crossing"
    else:
        flip_coincides = False
        flip_root_cause = "pack_logic_or_unspecified"

    if pack_overlap or pack_under_specified:
        same_logic_status = "invalid"
    elif observed == expected and float(replay.get("adjudication_route_consistency_rate_pct") or 0.0) == 100.0:
        same_logic_status = "validated"
    else:
        same_logic_status = "partial"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_threshold_validation_summary",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "current_baseline_route_expected": expected,
        "current_baseline_route_observed": observed,
        "route_count_valid_rate_pct": round(
            sum(1 for count in route_counts if count == 1) / len(route_counts) * 100.0, 1
        )
        if route_counts
        else 0.0,
        "adjudication_route_consistency_rate_pct": float(
            replay.get("adjudication_route_consistency_rate_pct") or 0.0
        ),
        "same_logic_validation_status": same_logic_status,
        "pack_overlap_detected": pack_overlap,
        "pack_under_specified_detected": pack_under_specified,
        "flip_coincides_with_boundary_crossing": flip_coincides,
        "flip_root_cause_interpretation": flip_root_cause,
        "observed_routes": observed_routes,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.8.3 Threshold Validation Summary",
                "",
                f"- current_baseline_route_observed: `{payload['current_baseline_route_observed']}`",
                f"- same_logic_validation_status: `{payload['same_logic_validation_status']}`",
                f"- pack_overlap_detected: `{payload['pack_overlap_detected']}`",
                f"- pack_under_specified_detected: `{payload['pack_under_specified_detected']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.8.3 threshold validation summary.")
    parser.add_argument(
        "--validation-replay-pack",
        default=str(DEFAULT_THRESHOLD_VALIDATION_REPLAY_PACK_OUT_DIR / "summary.json"),
    )
    parser.add_argument("--out-dir", default=str(DEFAULT_THRESHOLD_VALIDATION_SUMMARY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v083_threshold_validation_summary(
        validation_replay_pack_path=str(args.validation_replay_pack),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
