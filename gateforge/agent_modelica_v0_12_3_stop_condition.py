from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_12_3_common import (
    DEFAULT_STOP_CONDITION_OUT_DIR,
    DEFAULT_V120_CLOSEOUT_PATH,
    DEFAULT_V121_CLOSEOUT_PATH,
    DEFAULT_V122_CLOSEOUT_PATH,
    EXPECTED_V121_VERSION_DECISION,
    EXPECTED_V122_VERSION_DECISION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v123_stop_condition(
    *,
    v120_closeout_path: str = str(DEFAULT_V120_CLOSEOUT_PATH),
    v121_closeout_path: str = str(DEFAULT_V121_CLOSEOUT_PATH),
    v122_closeout_path: str = str(DEFAULT_V122_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_STOP_CONDITION_OUT_DIR),
) -> dict:
    c121 = (load_json(v121_closeout_path).get("conclusion") or {})
    c122 = (load_json(v122_closeout_path).get("conclusion") or {})

    bounded_operational_remedy_effect_answered = (
        str(c121.get("version_decision") or "") == EXPECTED_V121_VERSION_DECISION
    )
    stronger_bounded_remedy_scope_answered = (
        str(c122.get("version_decision") or "") == EXPECTED_V122_VERSION_DECISION
    )
    # same_class_reopen_required is false when the chain closed both questions cleanly
    same_class_reopen_required = not (
        bounded_operational_remedy_effect_answered and stronger_bounded_remedy_scope_answered
    )

    checks = {
        "bounded_operational_remedy_effect_answered": bounded_operational_remedy_effect_answered,
        "stronger_bounded_remedy_scope_answered": stronger_bounded_remedy_scope_answered,
        "same_class_reopen_required": same_class_reopen_required,
    }

    named_reason_if_not_ready = ""
    if not bounded_operational_remedy_effect_answered:
        named_reason_if_not_ready = "first_remedy_pack_result_not_confirmed_non_material"
    elif not stronger_bounded_remedy_scope_answered:
        named_reason_if_not_ready = "stronger_remedy_scope_not_confirmed_not_in_scope"

    # met is future-reserved: the current v0.12.x chain always closes as nearly_complete_with_caveat
    # because the first pack was non_material (not mainline_improving).
    if same_class_reopen_required:
        phase_stop_condition_status = "not_ready_for_closeout"
    elif bounded_operational_remedy_effect_answered and stronger_bounded_remedy_scope_answered:
        phase_stop_condition_status = "nearly_complete_with_caveat"
    else:
        phase_stop_condition_status = "not_ready_for_closeout"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_stop_condition",
        "generated_at_utc": now_utc(),
        "status": "PASS" if phase_stop_condition_status == "nearly_complete_with_caveat" else "FAIL",
        "phase_stop_condition_status": phase_stop_condition_status,
        "bounded_operational_remedy_effect_answered": bounded_operational_remedy_effect_answered,
        "stronger_bounded_remedy_scope_answered": stronger_bounded_remedy_scope_answered,
        "same_class_reopen_required": same_class_reopen_required,
        "named_reason_if_not_ready": named_reason_if_not_ready,
        "phase_stop_condition_checks": checks,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.12.3 Stop Condition",
                "",
                f"- phase_stop_condition_status: `{phase_stop_condition_status}`",
                f"- bounded_operational_remedy_effect_answered: `{bounded_operational_remedy_effect_answered}`",
                f"- stronger_bounded_remedy_scope_answered: `{stronger_bounded_remedy_scope_answered}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.12.3 stop condition artifact.")
    parser.add_argument("--v120-closeout", default=str(DEFAULT_V120_CLOSEOUT_PATH))
    parser.add_argument("--v121-closeout", default=str(DEFAULT_V121_CLOSEOUT_PATH))
    parser.add_argument("--v122-closeout", default=str(DEFAULT_V122_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_STOP_CONDITION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v123_stop_condition(
        v120_closeout_path=str(args.v120_closeout),
        v121_closeout_path=str(args.v121_closeout),
        v122_closeout_path=str(args.v122_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({
        "status": payload.get("status"),
        "phase_stop_condition_status": payload.get("phase_stop_condition_status"),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
