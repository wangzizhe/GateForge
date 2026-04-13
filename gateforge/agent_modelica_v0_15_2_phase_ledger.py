from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_15_2_common import (
    DEFAULT_PHASE_LEDGER_OUT_DIR,
    DEFAULT_V150_CLOSEOUT_PATH,
    DEFAULT_V151_CLOSEOUT_PATH,
    EXPECTED_V150_VERSION_DECISION,
    EXPECTED_V151_VERSION_DECISION,
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


def build_v152_phase_ledger(
    *,
    v150_closeout_path: str = str(DEFAULT_V150_CLOSEOUT_PATH),
    v151_closeout_path: str = str(DEFAULT_V151_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_PHASE_LEDGER_OUT_DIR),
) -> dict:
    checks = {
        "v0.15.0": _check_exact(v150_closeout_path, EXPECTED_V150_VERSION_DECISION),
        "v0.15.1": _check_exact(v151_closeout_path, EXPECTED_V151_VERSION_DECISION),
    }
    version_chain_ok = all(item["check_passed"] for item in checks.values())

    c151 = load_json(v151_closeout_path)
    latest_handoff_mode = str(((c151.get("conclusion") or {}).get("v0_15_2_handoff_mode") or ""))
    handoff_mode_ok = latest_handoff_mode == "prepare_v0_15_phase_synthesis"
    c151_blocker = str(((c151.get("conclusion") or {}).get("named_reason_if_not_justified") or ""))
    blocker_ok = bool(c151_blocker)

    phase_primary_question_answered_enough_for_handoff = version_chain_ok and handoff_mode_ok and blocker_ok
    phase_ledger_status = "ready" if phase_primary_question_answered_enough_for_handoff else "invalid"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_phase_ledger",
        "generated_at_utc": now_utc(),
        "status": "PASS" if phase_ledger_status == "ready" else "FAIL",
        "phase_ledger_status": phase_ledger_status,
        "governance_stage_result": checks["v0.15.0"]["actual_version_decision"],
        "viability_resolution_result": checks["v0.15.1"]["actual_version_decision"],
        "carried_blocker_readout": c151_blocker,
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
                "# v0.15.2 Phase Ledger",
                "",
                f"- phase_ledger_status: `{phase_ledger_status}`",
                f"- latest_handoff_mode: `{latest_handoff_mode}`",
                f"- carried_blocker_readout: `{c151_blocker}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.15.2 phase ledger.")
    parser.add_argument("--v150-closeout", default=str(DEFAULT_V150_CLOSEOUT_PATH))
    parser.add_argument("--v151-closeout", default=str(DEFAULT_V151_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_PHASE_LEDGER_OUT_DIR))
    args = parser.parse_args()
    payload = build_v152_phase_ledger(
        v150_closeout_path=str(args.v150_closeout),
        v151_closeout_path=str(args.v151_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "phase_ledger_status": payload.get("phase_ledger_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
