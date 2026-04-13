from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_14_3_common import (
    DEFAULT_PHASE_LEDGER_OUT_DIR,
    DEFAULT_V140_CLOSEOUT_PATH,
    DEFAULT_V141_CLOSEOUT_PATH,
    DEFAULT_V142_CLOSEOUT_PATH,
    EXPECTED_V140_VERSION_DECISION,
    EXPECTED_V141_VERSION_DECISIONS,
    EXPECTED_V142_VERSION_DECISION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def _check_exact(path: str, expected: str) -> dict:
    payload = load_json(path)
    actual = str((payload.get("conclusion") or {}).get("version_decision") or "")
    return {
        "expected_version_decision": expected,
        "actual_version_decision": actual,
        "check_passed": actual == expected,
    }


def _check_one_of(path: str, expected_values: frozenset[str]) -> dict:
    payload = load_json(path)
    actual = str((payload.get("conclusion") or {}).get("version_decision") or "")
    return {
        "expected_version_decisions": sorted(expected_values),
        "actual_version_decision": actual,
        "check_passed": actual in expected_values,
    }


def build_v143_phase_ledger(
    *,
    v140_closeout_path: str = str(DEFAULT_V140_CLOSEOUT_PATH),
    v141_closeout_path: str = str(DEFAULT_V141_CLOSEOUT_PATH),
    v142_closeout_path: str = str(DEFAULT_V142_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_PHASE_LEDGER_OUT_DIR),
) -> dict:
    checks = {
        "v0.14.0": _check_exact(v140_closeout_path, EXPECTED_V140_VERSION_DECISION),
        "v0.14.1": _check_one_of(v141_closeout_path, EXPECTED_V141_VERSION_DECISIONS),
        "v0.14.2": _check_exact(v142_closeout_path, EXPECTED_V142_VERSION_DECISION),
    }
    version_chain_ok = all(item["check_passed"] for item in checks.values())

    c142 = load_json(v142_closeout_path)
    latest_handoff_mode = str(((c142.get("conclusion") or {}).get("v0_14_3_handoff_mode") or ""))
    handoff_mode_ok = latest_handoff_mode == "prepare_v0_14_phase_synthesis"
    c142_blocker = str(((c142.get("conclusion") or {}).get("named_blocker_if_not_in_scope") or ""))
    blocker_ok = bool(c142_blocker)

    phase_primary_question_answered_enough_for_handoff = version_chain_ok and handoff_mode_ok and blocker_ok
    phase_ledger_status = "ready" if phase_primary_question_answered_enough_for_handoff else "invalid"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_phase_ledger",
        "generated_at_utc": now_utc(),
        "status": "PASS" if phase_ledger_status == "ready" else "FAIL",
        "phase_ledger_status": phase_ledger_status,
        "governance_stage_result": checks["v0.14.0"]["actual_version_decision"],
        "first_broader_change_execution_result": checks["v0.14.1"]["actual_version_decision"],
        "stronger_broader_change_scope_result": checks["v0.14.2"]["actual_version_decision"],
        "carried_blocker_readout": c142_blocker,
        "phase_primary_question_answered_enough_for_handoff": phase_primary_question_answered_enough_for_handoff,
        "latest_handoff_mode": latest_handoff_mode,
        "phase_question": "post_broader_change_exhaustion_even_broader_change_evaluation",
        "per_version_checks": checks,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.14.3 Phase Ledger",
                "",
                f"- phase_ledger_status: `{phase_ledger_status}`",
                f"- latest_handoff_mode: `{latest_handoff_mode}`",
                f"- carried_blocker_readout: `{c142_blocker}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.14.3 phase ledger.")
    parser.add_argument("--v140-closeout", default=str(DEFAULT_V140_CLOSEOUT_PATH))
    parser.add_argument("--v141-closeout", default=str(DEFAULT_V141_CLOSEOUT_PATH))
    parser.add_argument("--v142-closeout", default=str(DEFAULT_V142_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_PHASE_LEDGER_OUT_DIR))
    args = parser.parse_args()
    payload = build_v143_phase_ledger(
        v140_closeout_path=str(args.v140_closeout),
        v141_closeout_path=str(args.v141_closeout),
        v142_closeout_path=str(args.v142_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "phase_ledger_status": payload.get("phase_ledger_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
