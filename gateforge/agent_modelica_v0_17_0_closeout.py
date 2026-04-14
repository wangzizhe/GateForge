from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_17_0_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_GOVERNANCE_PACK_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V112_CLOSEOUT_PATH,
    DEFAULT_V160_CLOSEOUT_PATH,
    DEFAULT_V161_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_17_0_governance_pack import build_v170_governance_pack
from .agent_modelica_v0_17_0_handoff_integrity import build_v170_handoff_integrity


def build_v170_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    governance_pack_path: str = str(DEFAULT_GOVERNANCE_PACK_OUT_DIR / "summary.json"),
    v112_closeout_path: str = str(DEFAULT_V112_CLOSEOUT_PATH),
    v160_closeout_path: str = str(DEFAULT_V160_CLOSEOUT_PATH),
    v161_closeout_path: str = str(DEFAULT_V161_CLOSEOUT_PATH),
    continuity_check_mode: str = "schema_only",
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    handoff_path_obj = Path(handoff_integrity_path)
    governance_path_obj = Path(governance_pack_path)

    if not handoff_path_obj.exists():
        build_v170_handoff_integrity(
            v161_closeout_path=v161_closeout_path,
            out_dir=str(handoff_path_obj.parent),
        )
    handoff = load_json(handoff_integrity_path)
    if handoff.get("handoff_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_17_0_HANDOFF_PHASE_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_17_0_handoff_phase_inputs_invalid",
                "transition_governance_status": "invalid",
                "governance_ready_for_runtime_execution": False,
                "minimum_completion_signal_pass": False,
                "transition_arc_viability_status": "invalid",
                "transition_governance_outcome": "invalid",
                "v0_17_1_handoff_mode": "rebuild_v0_17_0_phase_inputs_first",
            },
            "handoff_integrity": handoff,
        }
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.17.0 Closeout\n\n- version_decision: `v0_17_0_handoff_phase_inputs_invalid`\n")
        return payload

    if not governance_path_obj.exists():
        build_v170_governance_pack(
            v112_closeout_path=v112_closeout_path,
            v160_closeout_path=v160_closeout_path,
            v161_closeout_path=v161_closeout_path,
            continuity_check_mode=continuity_check_mode,
            out_dir=str(governance_path_obj.parent),
        )
    governance = load_json(governance_pack_path)
    governance_status = governance.get("transition_governance_status", "invalid")
    governance_ready_for_runtime_execution = bool(governance.get("governance_ready_for_runtime_execution"))
    minimum_completion_signal_pass = bool(governance.get("minimum_completion_signal_pass"))
    named_first_transition_pack_ready = bool(governance.get("named_first_transition_pack_ready"))
    viability_object = governance.get("transition_arc_viability", {})
    viability_status = viability_object.get("transition_arc_viability_status", "invalid")
    governance_outcome = (governance.get("governance_outcome") or {}).get("transition_governance_outcome", "invalid")

    if governance_outcome == "no_honest_transition_question_remains":
        version_decision = "v0_17_0_no_honest_transition_question_remains"
        handoff_mode = "prepare_v0_17_phase_synthesis"
        status = "PASS"
        why = (
            "The governance layer froze successfully enough to conclude that no honest transition question remains beyond the "
            "carried baseline evidence-exhaustion readout."
        )
    elif minimum_completion_signal_pass and viability_status == "justified" and governance_outcome == "next_honest_transition_question_exists":
        version_decision = "v0_17_0_transition_governance_ready"
        handoff_mode = "execute_first_transition_question_pack"
        status = "PASS"
        why = (
            "A named transition question survived admission, preserved an honest transition protocol, and justified opening a "
            "transition arc."
        )
    elif handoff.get("handoff_integrity_status") == "PASS":
        version_decision = "v0_17_0_transition_governance_partial"
        handoff_mode = "resolve_v0_17_0_governance_or_viability_gaps_first"
        status = "PASS"
        why = (
            "The transition-governance direction is readable, but it has not yet frozen into either a justified transition arc "
            "or a terminal no-honest-transition conclusion."
        )
    else:
        version_decision = "v0_17_0_handoff_phase_inputs_invalid"
        handoff_mode = "rebuild_v0_17_0_phase_inputs_first"
        status = "FAIL"
        why = "The carried handoff or transition governance layer is invalid."

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": version_decision.upper(),
        "conclusion": {
            "version_decision": version_decision,
            "transition_governance_status": governance_status,
            "governance_ready_for_runtime_execution": governance_ready_for_runtime_execution,
            "minimum_completion_signal_pass": minimum_completion_signal_pass,
            "named_first_transition_pack_ready": named_first_transition_pack_ready,
            "transition_arc_viability_status": viability_status,
            "transition_governance_outcome": governance_outcome,
            "why_this_is_or_is_not_ready": why,
            "v0_17_1_handoff_mode": handoff_mode,
        },
        "handoff_integrity": handoff,
        "governance_pack": governance,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.17.0 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- transition_governance_status: `{governance_status}`",
                f"- transition_arc_viability_status: `{viability_status}`",
                f"- transition_governance_outcome: `{governance_outcome}`",
                f"- v0_17_1_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.17.0 transition-governance closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--governance-pack", default=str(DEFAULT_GOVERNANCE_PACK_OUT_DIR / "summary.json"))
    parser.add_argument("--v112-closeout", default=str(DEFAULT_V112_CLOSEOUT_PATH))
    parser.add_argument("--v160-closeout", default=str(DEFAULT_V160_CLOSEOUT_PATH))
    parser.add_argument("--v161-closeout", default=str(DEFAULT_V161_CLOSEOUT_PATH))
    parser.add_argument("--continuity-check-mode", default="schema_only")
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v170_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        governance_pack_path=str(args.governance_pack),
        v112_closeout_path=str(args.v112_closeout),
        v160_closeout_path=str(args.v160_closeout),
        v161_closeout_path=str(args.v161_closeout),
        continuity_check_mode=str(args.continuity_check_mode),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
