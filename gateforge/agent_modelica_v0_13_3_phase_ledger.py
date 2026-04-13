from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_13_3_common import (
    DEFAULT_PHASE_LEDGER_OUT_DIR,
    DEFAULT_V130_CLOSEOUT_PATH,
    DEFAULT_V131_CLOSEOUT_PATH,
    DEFAULT_V132_CLOSEOUT_PATH,
    EXPECTED_V130_VERSION_DECISION,
    EXPECTED_V131_VERSION_DECISION,
    EXPECTED_V132_VERSION_DECISION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


EXPECTED = {
    "v0.13.0": EXPECTED_V130_VERSION_DECISION,
    "v0.13.1": EXPECTED_V131_VERSION_DECISION,
    "v0.13.2": EXPECTED_V132_VERSION_DECISION,
}


def _check(path: str, expected: str) -> dict:
    payload = load_json(path)
    actual = str((payload.get("conclusion") or {}).get("version_decision") or "")
    return {
        "expected_version_decision": expected,
        "actual_version_decision": actual,
        "check_passed": actual == expected,
    }


def build_v133_phase_ledger(
    *,
    v130_closeout_path: str = str(DEFAULT_V130_CLOSEOUT_PATH),
    v131_closeout_path: str = str(DEFAULT_V131_CLOSEOUT_PATH),
    v132_closeout_path: str = str(DEFAULT_V132_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_PHASE_LEDGER_OUT_DIR),
) -> dict:
    checks = {
        "v0.13.0": _check(v130_closeout_path, EXPECTED["v0.13.0"]),
        "v0.13.1": _check(v131_closeout_path, EXPECTED["v0.13.1"]),
        "v0.13.2": _check(v132_closeout_path, EXPECTED["v0.13.2"]),
    }
    version_chain_ok = all(item["check_passed"] for item in checks.values())

    c132 = load_json(v132_closeout_path)
    latest_handoff_mode = str(((c132.get("conclusion") or {}).get("v0_13_3_handoff_mode") or ""))
    handoff_mode_ok = latest_handoff_mode == "prepare_v0_13_phase_synthesis"
    c132_blocker = str(((c132.get("conclusion") or {}).get("named_blocker_if_not_in_scope") or ""))
    blocker_ok = bool(c132_blocker)

    phase_primary_question_answered_enough_for_handoff = version_chain_ok and handoff_mode_ok and blocker_ok
    phase_ledger_status = "ready" if phase_primary_question_answered_enough_for_handoff else "invalid"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_phase_ledger",
        "generated_at_utc": now_utc(),
        "status": "PASS" if phase_ledger_status == "ready" else "FAIL",
        "phase_ledger_status": phase_ledger_status,
        "governance_stage_result": checks["v0.13.0"]["actual_version_decision"],
        "first_capability_intervention_execution_result": checks["v0.13.1"]["actual_version_decision"],
        "stronger_capability_intervention_scope_result": checks["v0.13.2"]["actual_version_decision"],
        "carried_blocker_readout": c132_blocker,
        "phase_primary_question_answered_enough_for_handoff": phase_primary_question_answered_enough_for_handoff,
        "latest_handoff_mode": latest_handoff_mode,
        "phase_question": "capability_level_improvement_evaluation_after_operational_remedy_exhaustion",
        "per_version_checks": checks,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.13.3 Phase Ledger",
                "",
                f"- phase_ledger_status: `{phase_ledger_status}`",
                f"- latest_handoff_mode: `{latest_handoff_mode}`",
                f"- carried_blocker_readout: `{c132_blocker}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.13.3 phase ledger.")
    parser.add_argument("--v130-closeout", default=str(DEFAULT_V130_CLOSEOUT_PATH))
    parser.add_argument("--v131-closeout", default=str(DEFAULT_V131_CLOSEOUT_PATH))
    parser.add_argument("--v132-closeout", default=str(DEFAULT_V132_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_PHASE_LEDGER_OUT_DIR))
    args = parser.parse_args()
    payload = build_v133_phase_ledger(
        v130_closeout_path=str(args.v130_closeout),
        v131_closeout_path=str(args.v131_closeout),
        v132_closeout_path=str(args.v132_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "phase_ledger_status": payload.get("phase_ledger_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
