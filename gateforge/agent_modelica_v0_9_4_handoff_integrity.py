from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_9_4_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V093_CLOSEOUT_PATH,
    GOAL_ALIGNMENT_RATE_RANGE_PCT_MAX,
    PER_CASE_CONSISTENCY_RATE_PCT_MIN,
    PROFILE_RUN_COUNT_MIN,
    SCHEMA_PREFIX,
    UNEXPLAINED_CASE_FLIP_COUNT_MAX,
    WORKFLOW_RATE_RANGE_PCT_MAX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v094_handoff_integrity(
    *,
    v093_closeout_path: str = str(DEFAULT_V093_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    closeout = load_json(v093_closeout_path)
    conclusion = closeout.get("conclusion") if isinstance(closeout.get("conclusion"), dict) else {}
    replay = closeout.get("expanded_profile_replay_pack") if isinstance(closeout.get("expanded_profile_replay_pack"), dict) else {}
    characterization = (
        closeout.get("expanded_workflow_profile_characterization")
        if isinstance(closeout.get("expanded_workflow_profile_characterization"), dict)
        else {}
    )

    checks = {
        "version_decision_ok": conclusion.get("version_decision")
        == "v0_9_3_expanded_workflow_profile_characterized",
        "handoff_mode_ok": conclusion.get("v0_9_4_handoff_mode") == "freeze_expanded_workflow_thresholds",
        "profile_barrier_unclassified_ok": int(characterization.get("profile_barrier_unclassified_count") or 0) == 0,
        "barrier_label_coverage_ok": float(characterization.get("barrier_label_coverage_rate_pct") or 0.0) == 100.0,
        "surface_fix_only_explained_ok": float(characterization.get("surface_fix_only_explained_rate_pct") or 0.0)
        == 100.0,
        "unresolved_explained_ok": float(characterization.get("unresolved_explained_rate_pct") or 0.0) == 100.0,
        "profile_run_count_ok": int(replay.get("profile_run_count") or 0) >= PROFILE_RUN_COUNT_MIN,
        "unexplained_flip_count_ok": int(replay.get("unexplained_case_flip_count") or 0)
        <= UNEXPLAINED_CASE_FLIP_COUNT_MAX,
        "per_case_consistency_ok": float(replay.get("per_case_outcome_consistency_rate_pct") or 0.0)
        >= PER_CASE_CONSISTENCY_RATE_PCT_MIN,
        "workflow_resolution_range_ok": float(replay.get("workflow_resolution_rate_range_pct") or 0.0)
        <= WORKFLOW_RATE_RANGE_PCT_MAX,
        "goal_alignment_range_ok": float(replay.get("goal_alignment_rate_range_pct") or 0.0)
        <= GOAL_ALIGNMENT_RATE_RANGE_PCT_MAX,
        "execution_source_ok": str(replay.get("execution_source") or "")
        == "frozen_expanded_substrate_deterministic_replay",
    }
    passed = all(checks.values())
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": "PASS" if passed else "FAIL",
        "handoff_integrity_status": "PASS" if passed else "FAIL",
        "checks": checks,
        "upstream_version_decision": conclusion.get("version_decision"),
        "upstream_handoff_mode": conclusion.get("v0_9_4_handoff_mode"),
        "execution_source": replay.get("execution_source"),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.4 Handoff Integrity",
                "",
                f"- status: `{payload['status']}`",
                f"- upstream_version_decision: `{payload['upstream_version_decision']}`",
                f"- upstream_handoff_mode: `{payload['upstream_handoff_mode']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.4 handoff integrity summary.")
    parser.add_argument("--v093-closeout", default=str(DEFAULT_V093_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v094_handoff_integrity(v093_closeout_path=str(args.v093_closeout), out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "handoff_integrity_status": payload.get("handoff_integrity_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
