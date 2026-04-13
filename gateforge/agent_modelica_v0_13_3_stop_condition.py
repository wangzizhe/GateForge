from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_13_3_common import (
    DEFAULT_STOP_CONDITION_OUT_DIR,
    DEFAULT_V131_CLOSEOUT_PATH,
    DEFAULT_V132_CLOSEOUT_PATH,
    EXPECTED_V131_VERSION_DECISION,
    EXPECTED_V132_VERSION_DECISION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v133_stop_condition(
    *,
    v131_closeout_path: str = str(DEFAULT_V131_CLOSEOUT_PATH),
    v132_closeout_path: str = str(DEFAULT_V132_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_STOP_CONDITION_OUT_DIR),
) -> dict:
    c131 = load_json(v131_closeout_path).get("conclusion") or {}
    c132 = load_json(v132_closeout_path).get("conclusion") or {}

    bounded_capability_intervention_effect_answered = (
        str(c131.get("version_decision") or "") == EXPECTED_V131_VERSION_DECISION
    )
    stronger_bounded_capability_intervention_scope_answered = (
        str(c132.get("version_decision") or "") == EXPECTED_V132_VERSION_DECISION
    )
    same_class_reopen_required = not (
        bounded_capability_intervention_effect_answered and stronger_bounded_capability_intervention_scope_answered
    )

    named_reason_if_not_ready = ""
    if not bounded_capability_intervention_effect_answered:
        named_reason_if_not_ready = "first_capability_intervention_pack_result_not_confirmed_side_evidence_only"
    elif not stronger_bounded_capability_intervention_scope_answered:
        named_reason_if_not_ready = "stronger_capability_intervention_scope_not_confirmed_not_in_scope"

    if same_class_reopen_required:
        phase_stop_condition_status = "not_ready_for_closeout"
    elif bounded_capability_intervention_effect_answered and stronger_bounded_capability_intervention_scope_answered:
        # met is future-reserved for current v0.13.x semantics because the first pack was not material.
        phase_stop_condition_status = "nearly_complete_with_caveat"
    else:
        phase_stop_condition_status = "not_ready_for_closeout"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_stop_condition",
        "generated_at_utc": now_utc(),
        "status": "PASS" if phase_stop_condition_status == "nearly_complete_with_caveat" else "FAIL",
        "phase_stop_condition_status": phase_stop_condition_status,
        "bounded_capability_intervention_effect_answered": bounded_capability_intervention_effect_answered,
        "stronger_bounded_capability_intervention_scope_answered": stronger_bounded_capability_intervention_scope_answered,
        "same_class_reopen_required": same_class_reopen_required,
        "named_reason_if_not_ready": named_reason_if_not_ready,
        "phase_stop_condition_checks": {
            "bounded_capability_intervention_effect_answered": bounded_capability_intervention_effect_answered,
            "stronger_bounded_capability_intervention_scope_answered": stronger_bounded_capability_intervention_scope_answered,
            "same_class_reopen_required": same_class_reopen_required,
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.13.3 Stop Condition",
                "",
                f"- phase_stop_condition_status: `{phase_stop_condition_status}`",
                f"- bounded_capability_intervention_effect_answered: `{bounded_capability_intervention_effect_answered}`",
                f"- stronger_bounded_capability_intervention_scope_answered: `{stronger_bounded_capability_intervention_scope_answered}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.13.3 stop condition artifact.")
    parser.add_argument("--v131-closeout", default=str(DEFAULT_V131_CLOSEOUT_PATH))
    parser.add_argument("--v132-closeout", default=str(DEFAULT_V132_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_STOP_CONDITION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v133_stop_condition(
        v131_closeout_path=str(args.v131_closeout),
        v132_closeout_path=str(args.v132_closeout),
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
