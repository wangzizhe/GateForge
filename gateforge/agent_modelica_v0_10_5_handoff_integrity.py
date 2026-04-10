from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_10_5_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V104_CLOSEOUT_PATH,
    MAX_UNEXPLAINED_CASE_FLIPS,
    MIN_PROFILE_RUN_COUNT,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v105_handoff_integrity(
    *,
    v104_closeout_path: str = str(DEFAULT_V104_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    closeout = load_json(v104_closeout_path)
    conclusion = closeout.get("conclusion") if isinstance(closeout.get("conclusion"), dict) else {}
    replay_pack = (
        closeout.get("real_origin_profile_replay_pack")
        if isinstance(closeout.get("real_origin_profile_replay_pack"), dict)
        else {}
    )

    # Structural fields checked with equality; numeric floors checked with intervals.
    # Interpretation rule: concrete values are read from upstream v0.10.4 closeout at runtime;
    # no pre-estimated percentage equality is required beyond the frozen structural fields below.
    checks = {
        "version_decision_matches": conclusion.get("version_decision")
        == "v0_10_4_first_real_origin_workflow_profile_characterized",
        "profile_run_count_floor_met": int(conclusion.get("profile_run_count") or 0) >= MIN_PROFILE_RUN_COUNT,
        "profile_non_success_unclassified_zero": int(conclusion.get("profile_non_success_unclassified_count") or 0) == 0,
        "handoff_mode_expected": conclusion.get("v0_10_5_handoff_mode")
        == "freeze_first_real_origin_workflow_thresholds",
        "per_case_consistency_floor_met": float(replay_pack.get("per_case_outcome_consistency_rate_pct") or 0.0)
        >= 100.0,
        "unexplained_flip_count_floor_met": int(replay_pack.get("unexplained_case_flip_count") or 0)
        <= MAX_UNEXPLAINED_CASE_FLIPS,
        "workflow_resolution_rate_range_zero": float(replay_pack.get("workflow_resolution_rate_range_pct") or 0.0)
        == 0.0,
    }
    status = "PASS" if all(checks.values()) else "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": status,
        "handoff_integrity_status": status,
        "checks": checks,
        "v104_closeout_summary": {
            "version_decision": conclusion.get("version_decision"),
            "profile_run_count": conclusion.get("profile_run_count"),
            "profile_non_success_unclassified_count": conclusion.get("profile_non_success_unclassified_count"),
            "v0_10_5_handoff_mode": conclusion.get("v0_10_5_handoff_mode"),
        },
        "v104_replay_floor_summary": {
            "per_case_outcome_consistency_rate_pct": replay_pack.get("per_case_outcome_consistency_rate_pct"),
            "unexplained_case_flip_count": replay_pack.get("unexplained_case_flip_count"),
            "workflow_resolution_rate_range_pct": replay_pack.get("workflow_resolution_rate_range_pct"),
        },
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.10.5 Handoff Integrity",
                "",
                f"- handoff_integrity_status: `{status}`",
                f"- version_decision: `{conclusion.get('version_decision')}`",
                f"- v0_10_5_handoff_mode: `{conclusion.get('v0_10_5_handoff_mode')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.10.5 handoff integrity artifact.")
    parser.add_argument("--v104-closeout", default=str(DEFAULT_V104_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v105_handoff_integrity(
        v104_closeout_path=str(args.v104_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "handoff_integrity_status": payload.get("handoff_integrity_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
