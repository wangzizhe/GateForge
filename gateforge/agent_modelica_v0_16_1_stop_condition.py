from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_16_1_common import (
    DEFAULT_STOP_CONDITION_OUT_DIR,
    DEFAULT_V160_CLOSEOUT_PATH,
    EXPECTED_V160_GOVERNANCE_OUTCOME,
    EXPECTED_V160_VERSION_DECISION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v161_stop_condition(
    *,
    v160_closeout_path: str = str(DEFAULT_V160_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_STOP_CONDITION_OUT_DIR),
) -> dict:
    c160 = load_json(v160_closeout_path).get("conclusion") or {}

    governance_question_answered = str(c160.get("version_decision") or "") == EXPECTED_V160_VERSION_DECISION
    no_honest_next_question_answered = str(c160.get("next_change_governance_outcome") or "") == EXPECTED_V160_GOVERNANCE_OUTCOME
    same_class_reopen_required = not (governance_question_answered and no_honest_next_question_answered)

    named_reason_if_not_ready = ""
    if not governance_question_answered:
        named_reason_if_not_ready = "no_honest_next_change_terminal_governance_path_not_confirmed"
    elif not no_honest_next_question_answered:
        named_reason_if_not_ready = "no_honest_next_local_question_outcome_not_confirmed"

    if same_class_reopen_required:
        phase_stop_condition_status = "not_ready_for_closeout"
    elif governance_question_answered and no_honest_next_question_answered:
        phase_stop_condition_status = "nearly_complete_with_caveat"
    else:
        phase_stop_condition_status = "not_ready_for_closeout"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_stop_condition",
        "generated_at_utc": now_utc(),
        "status": "PASS" if phase_stop_condition_status == "nearly_complete_with_caveat" else "FAIL",
        "phase_stop_condition_status": phase_stop_condition_status,
        "governance_question_answered": governance_question_answered,
        "no_honest_next_question_answered": no_honest_next_question_answered,
        "same_class_reopen_required": same_class_reopen_required,
        "named_reason_if_not_ready": named_reason_if_not_ready,
        "phase_stop_condition_checks": {
            "governance_question_answered": governance_question_answered,
            "no_honest_next_question_answered": no_honest_next_question_answered,
            "same_class_reopen_required": same_class_reopen_required,
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.16.1 Stop Condition",
                "",
                f"- phase_stop_condition_status: `{phase_stop_condition_status}`",
                f"- governance_question_answered: `{governance_question_answered}`",
                f"- no_honest_next_question_answered: `{no_honest_next_question_answered}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.16.1 stop condition artifact.")
    parser.add_argument("--v160-closeout", default=str(DEFAULT_V160_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_STOP_CONDITION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v161_stop_condition(
        v160_closeout_path=str(args.v160_closeout),
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
