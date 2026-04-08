from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_8_2_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V081_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v082_handoff_integrity(
    *,
    v081_closeout_path: str = str(DEFAULT_V081_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    closeout = load_json(v081_closeout_path)
    conclusion = closeout.get("conclusion") or {}
    replay = closeout.get("profile_replay_pack") or {}
    characterization = closeout.get("workflow_profile_characterization") or {}

    checks = {
        "version_decision_ok": conclusion.get("version_decision")
        == "v0_8_1_workflow_readiness_profile_characterized",
        "handoff_mode_ok": conclusion.get("v0_8_2_handoff_mode")
        == "freeze_workflow_readiness_thresholds_on_characterized_profile",
        "barrier_label_coverage_ok": float(characterization.get("barrier_label_coverage_rate_pct") or 0.0)
        == 100.0,
        "profile_barrier_unclassified_ok": int(
            characterization.get("profile_barrier_unclassified_count") or 0
        )
        == 0,
        "profile_run_count_ok": int(replay.get("profile_run_count") or 0) >= 3,
        "execution_source_ok": replay.get("execution_source") == "gateforge_run_contract_live_path",
        "mock_executor_path_forbidden_ok": not bool(replay.get("mock_executor_path_used")),
    }
    passed = all(checks.values())
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": "PASS" if passed else "FAIL",
        "handoff_integrity_status": "PASS" if passed else "FAIL",
        "checks": checks,
        "upstream_version_decision": conclusion.get("version_decision"),
        "upstream_handoff_mode": conclusion.get("v0_8_2_handoff_mode"),
        "execution_source": replay.get("execution_source"),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.8.2 Handoff Integrity",
                "",
                f"- status: `{payload['status']}`",
                f"- upstream_version_decision: `{payload['upstream_version_decision']}`",
                f"- upstream_handoff_mode: `{payload['upstream_handoff_mode']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.8.2 handoff integrity summary.")
    parser.add_argument("--v081-closeout", default=str(DEFAULT_V081_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v082_handoff_integrity(
        v081_closeout_path=str(args.v081_closeout),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
