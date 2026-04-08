from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_8_4_common import (
    DEFAULT_ROUTE_INTERPRETATION_SUMMARY_OUT_DIR,
    DEFAULT_V081_CHARACTERIZATION_PATH,
    DEFAULT_V082_THRESHOLD_INPUT_TABLE_PATH,
    DEFAULT_V083_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    dominant_barrier_family,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v084_route_interpretation_summary(
    *,
    frozen_baseline_adjudication_path: str,
    v081_characterization_path: str = str(DEFAULT_V081_CHARACTERIZATION_PATH),
    v082_threshold_input_table_path: str = str(DEFAULT_V082_THRESHOLD_INPUT_TABLE_PATH),
    v083_closeout_path: str = str(DEFAULT_V083_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_ROUTE_INTERPRETATION_SUMMARY_OUT_DIR),
) -> dict:
    adjudication = load_json(frozen_baseline_adjudication_path)
    characterization = load_json(v081_characterization_path)
    threshold_input = load_json(v082_threshold_input_table_path)
    v083 = load_json(v083_closeout_path)

    barrier_distribution = characterization.get("barrier_label_distribution") or threshold_input.get(
        "frozen_barrier_distribution"
    ) or {}
    dominant = dominant_barrier_family(barrier_distribution)
    sidecar_interpretable = int(characterization.get("profile_barrier_unclassified_count") or 0) == 0

    route = str(adjudication.get("adjudication_route") or "")
    if route == "workflow_readiness_supported":
        why_supported = "The frozen baseline clears the supported workflow-resolution and goal-alignment floors while preserving interpretable sidecar structure."
        why_fallback = "Fallback is not triggered because both supported thresholds and sidecar safeguards remain satisfied."
    elif route == "workflow_readiness_partial_but_interpretable":
        why_supported = "Supported is not reached because the frozen baseline remains below the supported workflow-resolution and goal-alignment floors, even though sidecar metrics remain interpretable."
        why_fallback = "Fallback is not triggered because the frozen baseline still clears the frozen partial floor and does not collapse into sidecar noise."
    elif route == "fallback_to_error_distribution_hardening_needed":
        why_supported = "Supported is not reached because the frozen baseline fails the supported route entirely."
        why_fallback = "Fallback is triggered because the frozen baseline fails both supported and partial under the validated threshold pack."
    else:
        why_supported = "Supported cannot be interpreted because the frozen baseline did not produce a unique adjudication route."
        why_fallback = "Fallback cannot be interpreted because the route count is invalid."

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_route_interpretation_summary",
        "generated_at_utc": now_utc(),
        "status": "PASS" if adjudication.get("adjudication_route_count") == 1 else "FAIL",
        "current_baseline_route_expected": (
            (v083.get("conclusion") or {}).get("current_baseline_route_observed")
        ),
        "adjudication_route": route,
        "adjudication_route_count": adjudication.get("adjudication_route_count"),
        "legacy_bucket_sidecar_still_interpretable": sidecar_interpretable,
        "dominant_workflow_barrier_family": dominant,
        "workflow_barrier_distribution_summary": barrier_distribution,
        "why_supported_is_or_is_not_reached": why_supported,
        "why_fallback_is_or_is_not_triggered": why_fallback,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.8.4 Route Interpretation Summary",
                "",
                f"- adjudication_route: `{payload['adjudication_route']}`",
                f"- legacy_bucket_sidecar_still_interpretable: `{payload['legacy_bucket_sidecar_still_interpretable']}`",
                f"- dominant_workflow_barrier_family: `{payload['dominant_workflow_barrier_family']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.8.4 route interpretation summary.")
    parser.add_argument("--frozen-baseline-adjudication", required=True)
    parser.add_argument("--v081-characterization", default=str(DEFAULT_V081_CHARACTERIZATION_PATH))
    parser.add_argument("--v082-threshold-input-table", default=str(DEFAULT_V082_THRESHOLD_INPUT_TABLE_PATH))
    parser.add_argument("--v083-closeout", default=str(DEFAULT_V083_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_ROUTE_INTERPRETATION_SUMMARY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v084_route_interpretation_summary(
        frozen_baseline_adjudication_path=str(args.frozen_baseline_adjudication),
        v081_characterization_path=str(args.v081_characterization),
        v082_threshold_input_table_path=str(args.v082_threshold_input_table),
        v083_closeout_path=str(args.v083_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "adjudication_route": payload.get("adjudication_route")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
