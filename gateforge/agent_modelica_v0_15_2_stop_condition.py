from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_15_2_common import (
    DEFAULT_STOP_CONDITION_OUT_DIR,
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


def build_v152_stop_condition(
    *,
    v150_closeout_path: str = str(DEFAULT_V150_CLOSEOUT_PATH),
    v151_closeout_path: str = str(DEFAULT_V151_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_STOP_CONDITION_OUT_DIR),
) -> dict:
    c150 = load_json(v150_closeout_path).get("conclusion") or {}
    c151 = load_json(v151_closeout_path).get("conclusion") or {}

    governance_question_answered = str(c150.get("version_decision") or "") == EXPECTED_V150_VERSION_DECISION
    execution_viability_question_answered = str(c151.get("version_decision") or "") == EXPECTED_V151_VERSION_DECISION
    same_class_reopen_required = not (governance_question_answered and execution_viability_question_answered)

    named_reason_if_not_ready = ""
    if not governance_question_answered:
        named_reason_if_not_ready = "even_broader_change_governance_partial_path_not_confirmed"
    elif not execution_viability_question_answered:
        named_reason_if_not_ready = "even_broader_execution_not_justified_path_not_confirmed"

    if same_class_reopen_required:
        phase_stop_condition_status = "not_ready_for_closeout"
    elif governance_question_answered and execution_viability_question_answered:
        phase_stop_condition_status = "nearly_complete_with_caveat"
    else:
        phase_stop_condition_status = "not_ready_for_closeout"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_stop_condition",
        "generated_at_utc": now_utc(),
        "status": "PASS" if phase_stop_condition_status == "nearly_complete_with_caveat" else "FAIL",
        "phase_stop_condition_status": phase_stop_condition_status,
        "governance_question_answered": governance_question_answered,
        "execution_viability_question_answered": execution_viability_question_answered,
        "same_class_reopen_required": same_class_reopen_required,
        "named_reason_if_not_ready": named_reason_if_not_ready,
        "phase_stop_condition_checks": {
            "governance_question_answered": governance_question_answered,
            "execution_viability_question_answered": execution_viability_question_answered,
            "same_class_reopen_required": same_class_reopen_required,
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.15.2 Stop Condition",
                "",
                f"- phase_stop_condition_status: `{phase_stop_condition_status}`",
                f"- governance_question_answered: `{governance_question_answered}`",
                f"- execution_viability_question_answered: `{execution_viability_question_answered}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.15.2 stop condition artifact.")
    parser.add_argument("--v150-closeout", default=str(DEFAULT_V150_CLOSEOUT_PATH))
    parser.add_argument("--v151-closeout", default=str(DEFAULT_V151_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_STOP_CONDITION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v152_stop_condition(
        v150_closeout_path=str(args.v150_closeout),
        v151_closeout_path=str(args.v151_closeout),
        out_dir=str(args.out_dir),
    )
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "phase_stop_condition_status": payload.get("phase_stop_condition_status"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
