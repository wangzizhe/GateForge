from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_12_3_common import (
    DEFAULT_PHASE_LEDGER_OUT_DIR,
    DEFAULT_V120_CLOSEOUT_PATH,
    DEFAULT_V121_CLOSEOUT_PATH,
    DEFAULT_V122_CLOSEOUT_PATH,
    EXPECTED_V120_VERSION_DECISION,
    EXPECTED_V121_VERSION_DECISION,
    EXPECTED_V122_VERSION_DECISION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


EXPECTED = {
    "v0.12.0": EXPECTED_V120_VERSION_DECISION,
    "v0.12.1": EXPECTED_V121_VERSION_DECISION,
    "v0.12.2": EXPECTED_V122_VERSION_DECISION,
}


def _check(path: str, expected: str) -> dict:
    payload = load_json(path)
    actual = str((payload.get("conclusion") or {}).get("version_decision") or "")
    return {
        "expected_version_decision": expected,
        "actual_version_decision": actual,
        "check_passed": actual == expected,
    }


def build_v123_phase_ledger(
    *,
    v120_closeout_path: str = str(DEFAULT_V120_CLOSEOUT_PATH),
    v121_closeout_path: str = str(DEFAULT_V121_CLOSEOUT_PATH),
    v122_closeout_path: str = str(DEFAULT_V122_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_PHASE_LEDGER_OUT_DIR),
) -> dict:
    checks = {
        "v0.12.0": _check(v120_closeout_path, EXPECTED["v0.12.0"]),
        "v0.12.1": _check(v121_closeout_path, EXPECTED["v0.12.1"]),
        "v0.12.2": _check(v122_closeout_path, EXPECTED["v0.12.2"]),
    }
    passed = all(item["check_passed"] for item in checks.values())

    c122 = load_json(v122_closeout_path)
    latest_handoff_mode = str(((c122.get("conclusion") or {}).get("v0_12_3_handoff_mode") or ""))
    handoff_mode_ok = latest_handoff_mode == "prepare_v0_12_phase_synthesis"

    c122_blocker = str(((c122.get("conclusion") or {}).get("named_blocker_if_not_in_scope") or ""))

    phase_ledger_status = "PASS" if passed and handoff_mode_ok else "FAIL"
    phase_primary_question_answered_enough_for_handoff = passed and handoff_mode_ok

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_phase_ledger",
        "generated_at_utc": now_utc(),
        "status": phase_ledger_status,
        "phase_ledger_status": phase_ledger_status,
        "governance_stage_result": checks["v0.12.0"]["actual_version_decision"],
        "first_remedy_execution_result": checks["v0.12.1"]["actual_version_decision"],
        "stronger_remedy_scope_result": checks["v0.12.2"]["actual_version_decision"],
        "carried_blocker_readout": c122_blocker,
        "phase_primary_question_answered_enough_for_handoff": phase_primary_question_answered_enough_for_handoff,
        "latest_handoff_mode": latest_handoff_mode,
        "version_chain": list(EXPECTED.values()),
        "phase_question": "workflow_to_product_gap_operational_remedy_evaluation",
        "per_version_checks": checks,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.12.3 Phase Ledger",
                "",
                f"- phase_ledger_status: `{phase_ledger_status}`",
                f"- latest_handoff_mode: `{latest_handoff_mode}`",
                f"- carried_blocker_readout: `{c122_blocker}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.12.3 phase ledger.")
    parser.add_argument("--v120-closeout", default=str(DEFAULT_V120_CLOSEOUT_PATH))
    parser.add_argument("--v121-closeout", default=str(DEFAULT_V121_CLOSEOUT_PATH))
    parser.add_argument("--v122-closeout", default=str(DEFAULT_V122_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_PHASE_LEDGER_OUT_DIR))
    args = parser.parse_args()
    payload = build_v123_phase_ledger(
        v120_closeout_path=str(args.v120_closeout),
        v121_closeout_path=str(args.v121_closeout),
        v122_closeout_path=str(args.v122_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "phase_ledger_status": payload.get("phase_ledger_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
