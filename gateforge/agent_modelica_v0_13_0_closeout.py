from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_13_0_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_GOVERNANCE_PACK_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V112_CLOSEOUT_PATH,
    DEFAULT_V115_CLOSEOUT_PATH,
    DEFAULT_V123_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_13_0_governance_pack import build_v130_governance_pack
from .agent_modelica_v0_13_0_handoff_integrity import build_v130_handoff_integrity


def build_v130_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    governance_pack_path: str = str(DEFAULT_GOVERNANCE_PACK_OUT_DIR / "summary.json"),
    v112_closeout_path: str = str(DEFAULT_V112_CLOSEOUT_PATH),
    v115_closeout_path: str = str(DEFAULT_V115_CLOSEOUT_PATH),
    v123_closeout_path: str = str(DEFAULT_V123_CLOSEOUT_PATH),
    continuity_check_mode: str = "schema_only",
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    handoff_path_obj = Path(handoff_integrity_path)
    governance_path_obj = Path(governance_pack_path)

    if not handoff_path_obj.exists():
        build_v130_handoff_integrity(
            v123_closeout_path=v123_closeout_path,
            out_dir=str(handoff_path_obj.parent),
        )
    handoff = load_json(handoff_integrity_path)
    if handoff.get("handoff_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_13_0_HANDOFF_PHASE_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_13_0_handoff_phase_inputs_invalid",
                "capability_intervention_governance_status": "invalid",
                "v0_13_1_handoff_mode": "rebuild_v0_13_0_phase_inputs_first",
            },
            "handoff_integrity": handoff,
        }
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.13.0 Closeout\n\n- version_decision: `v0_13_0_handoff_phase_inputs_invalid`\n")
        return payload

    if not governance_path_obj.exists():
        build_v130_governance_pack(
            v112_closeout_path=v112_closeout_path,
            v115_closeout_path=v115_closeout_path,
            v123_closeout_path=v123_closeout_path,
            continuity_check_mode=continuity_check_mode,
            out_dir=str(governance_path_obj.parent),
        )
    governance = load_json(governance_pack_path)

    governance_status = governance.get("capability_intervention_governance_status", "invalid")
    governance_ready_for_runtime_execution = bool(governance.get("governance_ready_for_runtime_execution"))
    named_first_intervention_pack_ready = bool(governance.get("named_first_intervention_pack_ready"))

    if governance_status == "invalid":
        version_decision = "v0_13_0_handoff_phase_inputs_invalid"
        handoff_mode = "rebuild_v0_13_0_phase_inputs_first"
        status = "FAIL"
        why = "The carried handoff or the capability-intervention governance layer is invalid, so no runtime intervention execution should begin."
    elif (
        governance_status == "governance_ready"
        and governance_ready_for_runtime_execution
        and named_first_intervention_pack_ready
    ):
        version_decision = "v0_13_0_capability_intervention_governance_ready"
        handoff_mode = "execute_first_bounded_capability_intervention_pack"
        status = "PASS"
        why = "The carried baseline, baseline continuity mode, lever map, family separation rule, admission rules, and comparison protocol are frozen cleanly enough to begin first-pass bounded capability-intervention execution."
    elif governance_status == "governance_partial":
        version_decision = "v0_13_0_capability_intervention_governance_partial"
        handoff_mode = "finish_capability_intervention_governance_first"
        status = "PASS"
        why = "The direction is valid, but at least one minimum capability-intervention governance signal remains incomplete and runtime execution should not begin yet."
    else:
        version_decision = "v0_13_0_handoff_phase_inputs_invalid"
        handoff_mode = "rebuild_v0_13_0_phase_inputs_first"
        status = "FAIL"
        why = "The governance closeout state is not internally coherent."

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": version_decision.upper(),
        "conclusion": {
            "version_decision": version_decision,
            "capability_intervention_governance_status": governance_status,
            "governance_ready_for_runtime_execution": governance_ready_for_runtime_execution,
            "minimum_completion_signal_pass": governance.get("minimum_completion_signal_pass"),
            "named_first_intervention_pack_ready": named_first_intervention_pack_ready,
            "why_this_is_or_is_not_ready": why,
            "v0_13_1_handoff_mode": handoff_mode,
        },
        "handoff_integrity": handoff,
        "governance_pack": governance,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.13.0 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- capability_intervention_governance_status: `{governance_status}`",
                f"- v0_13_1_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.13.0 capability-intervention governance closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--governance-pack", default=str(DEFAULT_GOVERNANCE_PACK_OUT_DIR / "summary.json"))
    parser.add_argument("--v112-closeout", default=str(DEFAULT_V112_CLOSEOUT_PATH))
    parser.add_argument("--v115-closeout", default=str(DEFAULT_V115_CLOSEOUT_PATH))
    parser.add_argument("--v123-closeout", default=str(DEFAULT_V123_CLOSEOUT_PATH))
    parser.add_argument("--continuity-check-mode", default="schema_only")
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v130_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        governance_pack_path=str(args.governance_pack),
        v112_closeout_path=str(args.v112_closeout),
        v115_closeout_path=str(args.v115_closeout),
        v123_closeout_path=str(args.v123_closeout),
        continuity_check_mode=str(args.continuity_check_mode),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
