from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_14_3_common import (
    DEFAULT_STOP_CONDITION_OUT_DIR,
    DEFAULT_V141_CLOSEOUT_PATH,
    DEFAULT_V142_CLOSEOUT_PATH,
    EXPECTED_V141_VERSION_DECISIONS,
    EXPECTED_V142_VERSION_DECISION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v143_stop_condition(
    *,
    v141_closeout_path: str = str(DEFAULT_V141_CLOSEOUT_PATH),
    v142_closeout_path: str = str(DEFAULT_V142_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_STOP_CONDITION_OUT_DIR),
) -> dict:
    c141 = load_json(v141_closeout_path).get("conclusion") or {}
    c142 = load_json(v142_closeout_path).get("conclusion") or {}

    broader_change_effect_answered = str(c141.get("version_decision") or "") in EXPECTED_V141_VERSION_DECISIONS
    stronger_broader_change_scope_answered = str(c142.get("version_decision") or "") == EXPECTED_V142_VERSION_DECISION
    same_class_reopen_required = not (broader_change_effect_answered and stronger_broader_change_scope_answered)

    named_reason_if_not_ready = ""
    if not broader_change_effect_answered:
        named_reason_if_not_ready = "first_broader_change_pack_result_not_confirmed_non_material_or_side_evidence_only"
    elif not stronger_broader_change_scope_answered:
        named_reason_if_not_ready = "stronger_broader_change_scope_not_confirmed_not_in_scope"

    if same_class_reopen_required:
        phase_stop_condition_status = "not_ready_for_closeout"
    elif broader_change_effect_answered and stronger_broader_change_scope_answered:
        phase_stop_condition_status = "nearly_complete_with_caveat"
    else:
        phase_stop_condition_status = "not_ready_for_closeout"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_stop_condition",
        "generated_at_utc": now_utc(),
        "status": "PASS" if phase_stop_condition_status == "nearly_complete_with_caveat" else "FAIL",
        "phase_stop_condition_status": phase_stop_condition_status,
        "broader_change_effect_answered": broader_change_effect_answered,
        "stronger_broader_change_scope_answered": stronger_broader_change_scope_answered,
        "same_class_reopen_required": same_class_reopen_required,
        "named_reason_if_not_ready": named_reason_if_not_ready,
        "phase_stop_condition_checks": {
            "broader_change_effect_answered": broader_change_effect_answered,
            "stronger_broader_change_scope_answered": stronger_broader_change_scope_answered,
            "same_class_reopen_required": same_class_reopen_required,
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.14.3 Stop Condition",
                "",
                f"- phase_stop_condition_status: `{phase_stop_condition_status}`",
                f"- broader_change_effect_answered: `{broader_change_effect_answered}`",
                f"- stronger_broader_change_scope_answered: `{stronger_broader_change_scope_answered}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.14.3 stop condition artifact.")
    parser.add_argument("--v141-closeout", default=str(DEFAULT_V141_CLOSEOUT_PATH))
    parser.add_argument("--v142-closeout", default=str(DEFAULT_V142_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_STOP_CONDITION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v143_stop_condition(
        v141_closeout_path=str(args.v141_closeout),
        v142_closeout_path=str(args.v142_closeout),
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
