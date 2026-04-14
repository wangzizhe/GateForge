from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_17_0_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V161_CLOSEOUT_PATH,
    EXPECTED_V161_CAVEAT,
    EXPECTED_V161_NEXT_PRIMARY_QUESTION,
    EXPECTED_V161_PHASE_STOP_CONDITION_STATUS,
    EXPECTED_V161_VERSION_DECISION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v170_handoff_integrity(
    *,
    v161_closeout_path: str = str(DEFAULT_V161_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    conclusion = load_json(v161_closeout_path).get("conclusion", {})
    checks = {
        "version_decision_ok": conclusion.get("version_decision") == EXPECTED_V161_VERSION_DECISION,
        "phase_stop_condition_ok": conclusion.get("phase_stop_condition_status") == EXPECTED_V161_PHASE_STOP_CONDITION_STATUS,
        "explicit_caveat_present_ok": bool(conclusion.get("explicit_caveat_present")),
        "explicit_caveat_label_ok": conclusion.get("explicit_caveat_label") == EXPECTED_V161_CAVEAT,
        "next_primary_phase_question_ok": conclusion.get("next_primary_phase_question") == EXPECTED_V161_NEXT_PRIMARY_QUESTION,
        "no_reopen_rule_ok": bool(conclusion.get("do_not_continue_v0_16_same_next_change_question_loop_by_default")),
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": status,
        "handoff_integrity_status": status,
        "checks": checks,
        "upstream_version_decision": conclusion.get("version_decision", ""),
        "upstream_phase_stop_condition_status": conclusion.get("phase_stop_condition_status", ""),
        "upstream_explicit_caveat_present": bool(conclusion.get("explicit_caveat_present")),
        "upstream_explicit_caveat_label": conclusion.get("explicit_caveat_label", ""),
        "upstream_next_primary_phase_question": conclusion.get("next_primary_phase_question", ""),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.17.0 Handoff Integrity",
                "",
                f"- handoff_integrity_status: `{status}`",
                f"- upstream_version_decision: `{payload['upstream_version_decision']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.17.0 handoff-integrity artifact.")
    parser.add_argument("--v161-closeout", default=str(DEFAULT_V161_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v170_handoff_integrity(
        v161_closeout_path=str(args.v161_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload["status"], "handoff_integrity_status": payload["handoff_integrity_status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
