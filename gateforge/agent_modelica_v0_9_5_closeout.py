from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_9_5_adjudication_input_table import build_v095_adjudication_input_table
from .agent_modelica_v0_9_5_common import (
    DEFAULT_ADJUDICATION_INPUT_TABLE_OUT_DIR,
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_EXPANDED_WORKFLOW_ADJUDICATION_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V093_CLOSEOUT_PATH,
    DEFAULT_V094_CLOSEOUT_PATH,
    DEFAULT_V094_EXPANDED_THRESHOLD_PACK_PATH,
    DEFAULT_V094_THRESHOLD_INPUT_TABLE_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_9_5_expanded_workflow_adjudication import build_v095_expanded_workflow_adjudication
from .agent_modelica_v0_9_5_handoff_integrity import build_v095_handoff_integrity


def build_v095_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    adjudication_input_table_path: str = str(DEFAULT_ADJUDICATION_INPUT_TABLE_OUT_DIR / "summary.json"),
    expanded_workflow_adjudication_path: str = str(DEFAULT_EXPANDED_WORKFLOW_ADJUDICATION_OUT_DIR / "summary.json"),
    v094_closeout_path: str = str(DEFAULT_V094_CLOSEOUT_PATH),
    v094_threshold_input_table_path: str = str(DEFAULT_V094_THRESHOLD_INPUT_TABLE_PATH),
    v094_expanded_threshold_pack_path: str = str(DEFAULT_V094_EXPANDED_THRESHOLD_PACK_PATH),
    v093_closeout_path: str = str(DEFAULT_V093_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    build_v095_handoff_integrity(v094_closeout_path=v094_closeout_path, out_dir=str(Path(handoff_integrity_path).parent))
    integrity = load_json(handoff_integrity_path)
    if integrity.get("handoff_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_9_5_ADJUDICATION_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_9_5_adjudication_inputs_invalid",
                "v0_9_6_handoff_mode": "rebuild_v0_9_5_inputs_first",
            },
            "handoff_integrity": integrity,
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.9.5 Closeout\n\n- version_decision: `v0_9_5_adjudication_inputs_invalid`\n")
        return payload

    if not Path(adjudication_input_table_path).exists():
        build_v095_adjudication_input_table(
            v093_closeout_path=v093_closeout_path,
            v094_threshold_input_table_path=v094_threshold_input_table_path,
            v094_expanded_threshold_pack_path=v094_expanded_threshold_pack_path,
            out_dir=str(Path(adjudication_input_table_path).parent),
        )
    if not Path(expanded_workflow_adjudication_path).exists():
        build_v095_expanded_workflow_adjudication(
            adjudication_input_table_path=adjudication_input_table_path,
            v093_closeout_path=v093_closeout_path,
            out_dir=str(Path(expanded_workflow_adjudication_path).parent),
        )

    adjudication_input = load_json(adjudication_input_table_path)
    adjudication = load_json(expanded_workflow_adjudication_path)

    route_count = int(adjudication.get("adjudication_route_count") or 0)
    route = str(adjudication.get("final_adjudication_label") or "")
    posture_ok = bool(adjudication.get("execution_posture_semantics_preserved"))

    if route_count != 1 or not posture_ok:
        decision = "v0_9_5_adjudication_inputs_invalid"
        handoff = "rebuild_v0_9_5_inputs_first"
        status = "FAIL"
        closeout_status = "V0_9_5_ADJUDICATION_INPUTS_INVALID"
    elif route == "expanded_workflow_readiness_supported":
        decision = "v0_9_5_expanded_workflow_readiness_supported"
        handoff = "evaluate_whether_v0_9_phase_stop_condition_is_near"
        status = "PASS"
        closeout_status = "V0_9_5_EXPANDED_WORKFLOW_READINESS_SUPPORTED"
    elif route == "expanded_workflow_readiness_partial_but_interpretable":
        decision = "v0_9_5_expanded_workflow_readiness_partial_but_interpretable"
        handoff = "decide_whether_more_authentic_expansion_is_still_worth_it"
        status = "PASS"
        closeout_status = "V0_9_5_EXPANDED_WORKFLOW_READINESS_PARTIAL_BUT_INTERPRETABLE"
    elif route == "fallback_to_profile_clarification_or_expansion_needed":
        decision = "v0_9_5_fallback_to_profile_clarification_or_expansion_needed"
        handoff = "repair_or_expand_before_any_phase_closeout_claim"
        status = "PASS"
        closeout_status = "V0_9_5_FALLBACK_TO_PROFILE_CLARIFICATION_OR_EXPANSION_NEEDED"
    else:
        decision = "v0_9_5_adjudication_inputs_invalid"
        handoff = "rebuild_v0_9_5_inputs_first"
        status = "FAIL"
        closeout_status = "V0_9_5_ADJUDICATION_INPUTS_INVALID"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": closeout_status,
        "conclusion": {
            "version_decision": decision,
            "final_adjudication_label": route,
            "adjudication_route_count": route_count,
            "execution_posture_semantics_preserved": posture_ok,
            "dominant_workflow_barrier_family": adjudication.get("dominant_workflow_barrier_family"),
            "why_this_label_is_correct": adjudication.get("why_this_label_is_correct"),
            "v0_9_6_handoff_mode": handoff,
        },
        "handoff_integrity": integrity,
        "adjudication_input_table": adjudication_input,
        "expanded_workflow_adjudication": adjudication,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.5 Closeout",
                "",
                f"- version_decision: `{decision}`",
                f"- final_adjudication_label: `{route}`",
                f"- dominant_workflow_barrier_family: `{adjudication.get('dominant_workflow_barrier_family')}`",
                f"- v0_9_6_handoff_mode: `{handoff}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.5 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--adjudication-input-table", default=str(DEFAULT_ADJUDICATION_INPUT_TABLE_OUT_DIR / "summary.json"))
    parser.add_argument("--expanded-workflow-adjudication", default=str(DEFAULT_EXPANDED_WORKFLOW_ADJUDICATION_OUT_DIR / "summary.json"))
    parser.add_argument("--v094-closeout", default=str(DEFAULT_V094_CLOSEOUT_PATH))
    parser.add_argument("--v094-threshold-input-table", default=str(DEFAULT_V094_THRESHOLD_INPUT_TABLE_PATH))
    parser.add_argument("--v094-expanded-threshold-pack", default=str(DEFAULT_V094_EXPANDED_THRESHOLD_PACK_PATH))
    parser.add_argument("--v093-closeout", default=str(DEFAULT_V093_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v095_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        adjudication_input_table_path=str(args.adjudication_input_table),
        expanded_workflow_adjudication_path=str(args.expanded_workflow_adjudication),
        v094_closeout_path=str(args.v094_closeout),
        v094_threshold_input_table_path=str(args.v094_threshold_input_table),
        v094_expanded_threshold_pack_path=str(args.v094_expanded_threshold_pack),
        v093_closeout_path=str(args.v093_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
