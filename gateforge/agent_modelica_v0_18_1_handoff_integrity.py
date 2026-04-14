from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_18_1_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V180_CLOSEOUT_PATH,
    EXPECTED_V180_GOVERNANCE_OUTCOME,
    EXPECTED_V180_GOVERNANCE_STATUS,
    EXPECTED_V180_HANDOFF_MODE,
    EXPECTED_V180_VERSION_DECISION,
    EXPECTED_V180_VIABILITY_STATUS,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v181_handoff_integrity(
    *,
    v180_closeout_path: str = str(DEFAULT_V180_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    conclusion = load_json(v180_closeout_path).get("conclusion") or {}
    checks = {
        "version_decision_ok": str(conclusion.get("version_decision") or "") == EXPECTED_V180_VERSION_DECISION,
        "governance_status_ok": str(conclusion.get("next_honest_move_governance_status") or "")
        == EXPECTED_V180_GOVERNANCE_STATUS,
        "governance_ready_for_runtime_execution_ok": bool(conclusion.get("governance_ready_for_runtime_execution")) is False,
        "minimum_completion_signal_ok": bool(conclusion.get("minimum_completion_signal_pass")) is False,
        "viability_status_ok": str(conclusion.get("next_move_viability_status") or "") == EXPECTED_V180_VIABILITY_STATUS,
        "governance_outcome_ok": str(conclusion.get("next_move_governance_outcome") or "")
        == EXPECTED_V180_GOVERNANCE_OUTCOME,
        "handoff_mode_ok": str(conclusion.get("v0_18_1_handoff_mode") or "") == EXPECTED_V180_HANDOFF_MODE,
    }
    handoff_integrity_status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": handoff_integrity_status,
        "handoff_integrity_status": handoff_integrity_status,
        "checks": checks,
        "upstream_version_decision": str(conclusion.get("version_decision") or ""),
        "upstream_next_honest_move_governance_status": str(conclusion.get("next_honest_move_governance_status") or ""),
        "upstream_next_move_viability_status": str(conclusion.get("next_move_viability_status") or ""),
        "upstream_next_move_governance_outcome": str(conclusion.get("next_move_governance_outcome") or ""),
        "upstream_handoff_mode": str(conclusion.get("v0_18_1_handoff_mode") or ""),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.18.1 Handoff Integrity",
                "",
                f"- handoff_integrity_status: `{handoff_integrity_status}`",
                f"- upstream_version_decision: `{payload['upstream_version_decision']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.18.1 handoff-integrity artifact.")
    parser.add_argument("--v180-closeout", default=str(DEFAULT_V180_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v181_handoff_integrity(v180_closeout_path=str(args.v180_closeout), out_dir=str(args.out_dir))
    print(json.dumps({"status": payload["status"], "handoff_integrity_status": payload["handoff_integrity_status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
