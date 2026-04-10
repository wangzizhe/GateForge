from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_10_6_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_FIRST_REAL_ORIGIN_WORKFLOW_ADJUDICATION_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_REAL_ORIGIN_ADJUDICATION_INPUT_TABLE_OUT_DIR,
    DEFAULT_V104_CLOSEOUT_PATH,
    DEFAULT_V105_CLOSEOUT_PATH,
    DEFAULT_V105_THRESHOLD_INPUT_TABLE_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_10_6_first_real_origin_workflow_adjudication import (
    build_v106_first_real_origin_workflow_adjudication,
)
from .agent_modelica_v0_10_6_handoff_integrity import build_v106_handoff_integrity
from .agent_modelica_v0_10_6_real_origin_adjudication_input_table import (
    build_v106_real_origin_adjudication_input_table,
)


def build_v106_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    real_origin_adjudication_input_table_path: str = str(
        DEFAULT_REAL_ORIGIN_ADJUDICATION_INPUT_TABLE_OUT_DIR / "summary.json"
    ),
    first_real_origin_workflow_adjudication_path: str = str(
        DEFAULT_FIRST_REAL_ORIGIN_WORKFLOW_ADJUDICATION_OUT_DIR / "summary.json"
    ),
    v105_closeout_path: str = str(DEFAULT_V105_CLOSEOUT_PATH),
    v105_threshold_input_table_path: str = str(DEFAULT_V105_THRESHOLD_INPUT_TABLE_PATH),
    v104_closeout_path: str = str(DEFAULT_V104_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    build_v106_handoff_integrity(
        v105_closeout_path=v105_closeout_path,
        out_dir=str(Path(handoff_integrity_path).parent),
    )
    integrity = load_json(handoff_integrity_path)
    if integrity.get("handoff_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_10_6_REAL_ORIGIN_ADJUDICATION_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_10_6_real_origin_adjudication_inputs_invalid",
                "v0_10_7_handoff_mode": "rebuild_v0_10_6_inputs_first",
            },
            "handoff_integrity": integrity,
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", payload)
        write_text(
            out_root / "summary.md",
            "# v0.10.6 Closeout\n\n- version_decision: `v0_10_6_real_origin_adjudication_inputs_invalid`\n",
        )
        return payload

    if not Path(real_origin_adjudication_input_table_path).exists():
        build_v106_real_origin_adjudication_input_table(
            v105_closeout_path=v105_closeout_path,
            v105_threshold_input_table_path=v105_threshold_input_table_path,
            v104_closeout_path=v104_closeout_path,
            out_dir=str(Path(real_origin_adjudication_input_table_path).parent),
        )
    if not Path(first_real_origin_workflow_adjudication_path).exists():
        build_v106_first_real_origin_workflow_adjudication(
            real_origin_adjudication_input_table_path=real_origin_adjudication_input_table_path,
            out_dir=str(Path(first_real_origin_workflow_adjudication_path).parent),
        )

    adjudication_input = load_json(real_origin_adjudication_input_table_path)
    adjudication = load_json(first_real_origin_workflow_adjudication_path)

    route_count = int(adjudication.get("adjudication_route_count") or 0)
    route = str(adjudication.get("final_adjudication_label") or "")
    posture_ok = bool(adjudication.get("execution_posture_semantics_preserved"))

    if route_count != 1 or not posture_ok:
        decision = "v0_10_6_real_origin_adjudication_inputs_invalid"
        handoff = "rebuild_v0_10_6_inputs_first"
        status = "FAIL"
        closeout_status = "V0_10_6_REAL_ORIGIN_ADJUDICATION_INPUTS_INVALID"
    elif route == "real_origin_workflow_readiness_supported":
        decision = "v0_10_6_first_real_origin_workflow_readiness_supported"
        handoff = "decide_whether_v0_10_phase_synthesis_is_already_justified"
        status = "PASS"
        closeout_status = "V0_10_6_FIRST_REAL_ORIGIN_WORKFLOW_READINESS_SUPPORTED"
    elif route == "real_origin_workflow_readiness_partial_but_interpretable":
        decision = "v0_10_6_first_real_origin_workflow_readiness_partial_but_interpretable"
        handoff = "decide_whether_one_more_bounded_real_origin_step_is_still_worth_it"
        status = "PASS"
        closeout_status = "V0_10_6_FIRST_REAL_ORIGIN_WORKFLOW_READINESS_PARTIAL_BUT_INTERPRETABLE"
    elif route == "real_origin_workflow_readiness_fallback":
        decision = "v0_10_6_first_real_origin_workflow_readiness_fallback_to_profile_clarification_or_source_expansion_needed"
        handoff = "decide_whether_profile_clarification_or_bounded_source_repair_is_next"
        status = "PASS"
        closeout_status = "V0_10_6_FIRST_REAL_ORIGIN_WORKFLOW_READINESS_FALLBACK_TO_PROFILE_CLARIFICATION_OR_SOURCE_EXPANSION_NEEDED"
    else:
        decision = "v0_10_6_real_origin_adjudication_inputs_invalid"
        handoff = "rebuild_v0_10_6_inputs_first"
        status = "FAIL"
        closeout_status = "V0_10_6_REAL_ORIGIN_ADJUDICATION_INPUTS_INVALID"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": closeout_status,
        "conclusion": {
            "version_decision": decision,
            "final_adjudication_label": route,
            "supported_check_pass": adjudication.get("supported_check_pass"),
            "partial_check_pass": adjudication.get("partial_check_pass"),
            "fallback_triggered": adjudication.get("fallback_triggered"),
            "execution_posture_semantics_preserved": posture_ok,
            "dominant_non_success_label_family": adjudication.get("dominant_non_success_label_family"),
            "why_this_label_is_correct": adjudication.get("why_this_label_is_correct"),
            "v0_10_7_handoff_mode": handoff,
        },
        "handoff_integrity": integrity,
        "real_origin_adjudication_input_table": adjudication_input,
        "first_real_origin_workflow_adjudication": adjudication,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.10.6 Closeout",
                "",
                f"- version_decision: `{decision}`",
                f"- final_adjudication_label: `{route}`",
                f"- dominant_non_success_label_family: `{adjudication.get('dominant_non_success_label_family')}`",
                f"- v0_10_7_handoff_mode: `{handoff}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.10.6 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument(
        "--real-origin-adjudication-input-table",
        default=str(DEFAULT_REAL_ORIGIN_ADJUDICATION_INPUT_TABLE_OUT_DIR / "summary.json"),
    )
    parser.add_argument(
        "--first-real-origin-workflow-adjudication",
        default=str(DEFAULT_FIRST_REAL_ORIGIN_WORKFLOW_ADJUDICATION_OUT_DIR / "summary.json"),
    )
    parser.add_argument("--v105-closeout", default=str(DEFAULT_V105_CLOSEOUT_PATH))
    parser.add_argument("--v105-threshold-input-table", default=str(DEFAULT_V105_THRESHOLD_INPUT_TABLE_PATH))
    parser.add_argument("--v104-closeout", default=str(DEFAULT_V104_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v106_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        real_origin_adjudication_input_table_path=str(args.real_origin_adjudication_input_table),
        first_real_origin_workflow_adjudication_path=str(args.first_real_origin_workflow_adjudication),
        v105_closeout_path=str(args.v105_closeout),
        v105_threshold_input_table_path=str(args.v105_threshold_input_table),
        v104_closeout_path=str(args.v104_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
