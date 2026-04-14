from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_17_1_common import (
    DEFAULT_PHASE_LEDGER_OUT_DIR,
    DEFAULT_V170_CLOSEOUT_PATH,
    EXPECTED_V170_GOVERNANCE_OUTCOME,
    EXPECTED_V170_VERSION_DECISION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v171_phase_ledger(
    *,
    v170_closeout_path: str = str(DEFAULT_V170_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_PHASE_LEDGER_OUT_DIR),
) -> dict:
    v170 = load_json(v170_closeout_path)
    conclusion = v170.get("conclusion") or {}
    actual_version_decision = str(conclusion.get("version_decision") or "")
    carried_transition_governance_outcome = str(conclusion.get("transition_governance_outcome") or "")
    latest_handoff_mode = str(conclusion.get("v0_17_1_handoff_mode") or "")

    checks = {
        "v0.17.0": {
            "expected_version_decision": EXPECTED_V170_VERSION_DECISION,
            "actual_version_decision": actual_version_decision,
            "check_passed": actual_version_decision == EXPECTED_V170_VERSION_DECISION,
        }
    }
    version_chain_ok = all(item["check_passed"] for item in checks.values())
    governance_outcome_ok = carried_transition_governance_outcome == EXPECTED_V170_GOVERNANCE_OUTCOME
    handoff_mode_ok = latest_handoff_mode == "prepare_v0_17_phase_synthesis"

    phase_primary_question_answered_enough_for_handoff = version_chain_ok and governance_outcome_ok and handoff_mode_ok
    phase_ledger_status = "ready" if phase_primary_question_answered_enough_for_handoff else "invalid"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_phase_ledger",
        "generated_at_utc": now_utc(),
        "status": "PASS" if phase_ledger_status == "ready" else "FAIL",
        "phase_ledger_status": phase_ledger_status,
        "transition_governance_stage_result": actual_version_decision,
        "carried_transition_governance_outcome": carried_transition_governance_outcome,
        "phase_primary_question_answered_enough_for_handoff": phase_primary_question_answered_enough_for_handoff,
        "latest_handoff_mode": latest_handoff_mode,
        "phase_question": "carried_baseline_evidence_exhaustion_transition_evaluation",
        "per_version_checks": checks,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.17.1 Phase Ledger",
                "",
                f"- phase_ledger_status: `{phase_ledger_status}`",
                f"- latest_handoff_mode: `{latest_handoff_mode}`",
                f"- carried_transition_governance_outcome: `{carried_transition_governance_outcome}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.17.1 phase ledger.")
    parser.add_argument("--v170-closeout", default=str(DEFAULT_V170_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_PHASE_LEDGER_OUT_DIR))
    args = parser.parse_args()
    payload = build_v171_phase_ledger(
        v170_closeout_path=str(args.v170_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "phase_ledger_status": payload.get("phase_ledger_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
