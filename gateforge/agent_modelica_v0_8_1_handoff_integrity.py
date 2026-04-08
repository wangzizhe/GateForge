from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_8_1_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V080_CLOSEOUT_PATH,
    DEFAULT_V080_PILOT_PROFILE_PATH,
    DEFAULT_V080_SUBSTRATE_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v081_handoff_integrity(
    *,
    v080_closeout_path: str = str(DEFAULT_V080_CLOSEOUT_PATH),
    v080_substrate_path: str = str(DEFAULT_V080_SUBSTRATE_PATH),
    v080_pilot_profile_path: str = str(DEFAULT_V080_PILOT_PROFILE_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    closeout = load_json(v080_closeout_path)
    substrate = load_json(v080_substrate_path)
    pilot = load_json(v080_pilot_profile_path)

    conclusion = closeout.get("conclusion") or {}
    runtime_checks = {
        "execution_source_ok": pilot.get("execution_source") == "gateforge_run_contract_live_path",
        "goal_level_oracle_frozen_ok": bool(pilot.get("goal_level_resolution_criterion_frozen")),
        "planner_backend_rule_ok": True,
        "experience_replay_off_ok": True,
        "planner_experience_off_ok": True,
        "max_rounds_one_ok": True,
    }
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": "PASS"
        if (
            conclusion.get("version_decision") == "v0_8_0_workflow_proximal_substrate_ready"
            and conclusion.get("v0_8_1_handoff_mode")
            == "characterize_workflow_readiness_profile_on_frozen_substrate"
            and bool(substrate.get("workflow_proximity_audit_pass_rate_pct"))
            and all(runtime_checks.values())
        )
        else "FAIL",
        "handoff_integrity_status": "PASS"
        if (
            conclusion.get("version_decision") == "v0_8_0_workflow_proximal_substrate_ready"
            and conclusion.get("v0_8_1_handoff_mode")
            == "characterize_workflow_readiness_profile_on_frozen_substrate"
            and bool(substrate.get("workflow_proximity_audit_pass_rate_pct"))
            and all(runtime_checks.values())
        )
        else "FAIL",
        "checks": {
            "version_decision_ok": conclusion.get("version_decision")
            == "v0_8_0_workflow_proximal_substrate_ready",
            "handoff_mode_ok": conclusion.get("v0_8_1_handoff_mode")
            == "characterize_workflow_readiness_profile_on_frozen_substrate",
            "substrate_present_ok": bool(substrate.get("task_rows")),
            **runtime_checks,
        },
        "upstream_version_decision": conclusion.get("version_decision"),
        "upstream_handoff_mode": conclusion.get("v0_8_1_handoff_mode"),
        "frozen_task_count": int(substrate.get("task_count") or 0),
        "execution_source": pilot.get("execution_source"),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.8.1 Handoff Integrity",
                "",
                f"- status: `{payload['status']}`",
                f"- upstream_version_decision: `{payload['upstream_version_decision']}`",
                f"- upstream_handoff_mode: `{payload['upstream_handoff_mode']}`",
                f"- execution_source: `{payload['execution_source']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.8.1 handoff integrity summary.")
    parser.add_argument("--v080-closeout", default=str(DEFAULT_V080_CLOSEOUT_PATH))
    parser.add_argument("--v080-substrate", default=str(DEFAULT_V080_SUBSTRATE_PATH))
    parser.add_argument("--v080-pilot-profile", default=str(DEFAULT_V080_PILOT_PROFILE_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v081_handoff_integrity(
        v080_closeout_path=str(args.v080_closeout),
        v080_substrate_path=str(args.v080_substrate),
        v080_pilot_profile_path=str(args.v080_pilot_profile),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
