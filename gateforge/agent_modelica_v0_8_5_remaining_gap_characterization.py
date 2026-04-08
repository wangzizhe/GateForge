from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_8_5_common import (
    DEFAULT_REMAINING_GAP_CHARACTERIZATION_OUT_DIR,
    DEFAULT_V081_CLOSEOUT_PATH,
    DEFAULT_V082_THRESHOLD_FREEZE_PATH,
    DEFAULT_V084_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v085_remaining_gap_characterization(
    *,
    v084_closeout_path: str = str(DEFAULT_V084_CLOSEOUT_PATH),
    v081_closeout_path: str = str(DEFAULT_V081_CLOSEOUT_PATH),
    v082_threshold_freeze_path: str = str(DEFAULT_V082_THRESHOLD_FREEZE_PATH),
    out_dir: str = str(DEFAULT_REMAINING_GAP_CHARACTERIZATION_OUT_DIR),
) -> dict:
    v084 = load_json(v084_closeout_path)
    v081 = load_json(v081_closeout_path)
    v082 = load_json(v082_threshold_freeze_path)

    adjudication = v084.get("frozen_baseline_adjudication") or {}
    replay = v081.get("profile_replay_pack") or {}
    handoff = v081.get("handoff_integrity") or {}
    supported_pack = v082.get("supported_threshold_pack") or {}
    supported_primary = supported_pack.get("primary_workflow_metrics") or {}

    current_workflow_resolution = float(adjudication.get("workflow_resolution_rate_pct") or 0.0)
    current_goal_alignment = float(adjudication.get("goal_alignment_rate_pct") or 0.0)
    supported_workflow_floor = float(supported_primary.get("workflow_resolution_rate_pct_min") or 0.0)
    supported_goal_alignment_floor = float(supported_primary.get("goal_alignment_rate_pct_min") or 0.0)

    gap_resolution = round(supported_workflow_floor - current_workflow_resolution, 1)
    gap_alignment = round(supported_goal_alignment_floor - current_goal_alignment, 1)
    remaining_gap_magnitude = max(gap_resolution, gap_alignment)

    execution_posture_frozen = all(
        [
            bool((handoff.get("checks") or {}).get("planner_backend_rule_ok")),
            bool((handoff.get("checks") or {}).get("experience_replay_off_ok")),
            bool((handoff.get("checks") or {}).get("planner_experience_off_ok")),
            bool((handoff.get("checks") or {}).get("max_rounds_one_ok")),
        ]
    )
    profile_run_count = int(replay.get("profile_run_count") or 0)
    per_case_consistency = float(replay.get("per_case_outcome_consistency_rate_pct") or 0.0)

    threshold_proximal = gap_resolution <= 3.0 or gap_alignment <= 3.0
    same_logic_addressable = True
    if execution_posture_frozen and profile_run_count >= 3 and per_case_consistency == 100.0:
        same_logic_addressable = False

    if threshold_proximal and same_logic_addressable:
        remaining_gap_status = "single_refinable_gap"
    else:
        remaining_gap_status = "no_same_logic_gap_with_meaningful_expected_gain"

    if gap_resolution == gap_alignment:
        remaining_gap_label = "supported_resolution_and_alignment_gap_move_together"
    elif gap_resolution > gap_alignment:
        remaining_gap_label = "supported_workflow_resolution_gap"
    else:
        remaining_gap_label = "supported_goal_alignment_gap"

    if threshold_proximal and same_logic_addressable:
        expected_information_gain = "non_trivial"
    else:
        expected_information_gain = "marginal"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_remaining_gap_characterization",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "current_workflow_resolution_rate_pct": current_workflow_resolution,
        "current_goal_alignment_rate_pct": current_goal_alignment,
        "supported_workflow_resolution_floor_pct": supported_workflow_floor,
        "supported_goal_alignment_floor_pct": supported_goal_alignment_floor,
        "gap_to_supported_workflow_resolution_pct": gap_resolution,
        "gap_to_supported_goal_alignment_pct": gap_alignment,
        "execution_posture_frozen": execution_posture_frozen,
        "profile_run_count": profile_run_count,
        "per_case_outcome_consistency_rate_pct": per_case_consistency,
        "remaining_gap_status": remaining_gap_status,
        "remaining_gap_label": remaining_gap_label,
        "remaining_gap_magnitude_pct": remaining_gap_magnitude,
        "remaining_gap_is_threshold_proximal": threshold_proximal,
        "remaining_gap_is_same_logic_addressable": same_logic_addressable,
        "expected_information_gain": expected_information_gain,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.8.5 Remaining Gap Characterization",
                "",
                f"- remaining_gap_status: `{remaining_gap_status}`",
                f"- remaining_gap_label: `{remaining_gap_label}`",
                f"- remaining_gap_magnitude_pct: `{remaining_gap_magnitude}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.8.5 remaining gap characterization.")
    parser.add_argument("--v084-closeout", default=str(DEFAULT_V084_CLOSEOUT_PATH))
    parser.add_argument("--v081-closeout", default=str(DEFAULT_V081_CLOSEOUT_PATH))
    parser.add_argument("--v082-threshold-freeze", default=str(DEFAULT_V082_THRESHOLD_FREEZE_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_REMAINING_GAP_CHARACTERIZATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v085_remaining_gap_characterization(
        v084_closeout_path=str(args.v084_closeout),
        v081_closeout_path=str(args.v081_closeout),
        v082_threshold_freeze_path=str(args.v082_threshold_freeze),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "remaining_gap_status": payload.get("remaining_gap_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
