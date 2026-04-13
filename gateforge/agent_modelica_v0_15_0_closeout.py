from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_15_0_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_GOVERNANCE_PACK_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V112_CLOSEOUT_PATH,
    DEFAULT_V141_CLOSEOUT_PATH,
    DEFAULT_V142_CLOSEOUT_PATH,
    DEFAULT_V143_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_15_0_governance_pack import build_v150_governance_pack
from .agent_modelica_v0_15_0_handoff_integrity import build_v150_handoff_integrity


def build_v150_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    governance_pack_path: str = str(DEFAULT_GOVERNANCE_PACK_OUT_DIR / "summary.json"),
    v112_closeout_path: str = str(DEFAULT_V112_CLOSEOUT_PATH),
    v141_closeout_path: str = str(DEFAULT_V141_CLOSEOUT_PATH),
    v142_closeout_path: str = str(DEFAULT_V142_CLOSEOUT_PATH),
    v143_closeout_path: str = str(DEFAULT_V143_CLOSEOUT_PATH),
    continuity_check_mode: str = "schema_only",
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    handoff_path_obj = Path(handoff_integrity_path)
    governance_path_obj = Path(governance_pack_path)

    if not handoff_path_obj.exists():
        build_v150_handoff_integrity(
            v143_closeout_path=v143_closeout_path,
            out_dir=str(handoff_path_obj.parent),
        )
    handoff = load_json(handoff_integrity_path)
    if handoff.get("handoff_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_15_0_HANDOFF_PHASE_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_15_0_handoff_phase_inputs_invalid",
                "even_broader_change_governance_status": "invalid",
                "execution_arc_viability_status": "invalid",
                "named_reason_if_not_justified": "handoff_phase_inputs_invalid",
                "v0_15_1_handoff_mode": "rebuild_v0_15_0_phase_inputs_first",
            },
            "handoff_integrity": handoff,
        }
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.15.0 Closeout\n\n- version_decision: `v0_15_0_handoff_phase_inputs_invalid`\n")
        return payload

    if not governance_path_obj.exists():
        build_v150_governance_pack(
            v112_closeout_path=v112_closeout_path,
            v141_closeout_path=v141_closeout_path,
            v142_closeout_path=v142_closeout_path,
            v143_closeout_path=v143_closeout_path,
            continuity_check_mode=continuity_check_mode,
            out_dir=str(governance_path_obj.parent),
        )
    governance = load_json(governance_pack_path)

    governance_status = governance.get("even_broader_change_governance_status", "invalid")
    governance_ready_for_runtime_execution = bool(governance.get("governance_ready_for_runtime_execution"))
    named_first_even_broader_change_pack_ready = bool(governance.get("named_first_even_broader_change_pack_ready"))
    minimum_completion_signal_pass = bool(governance.get("minimum_completion_signal_pass"))
    viability_object = governance.get("execution_arc_viability", {})
    viability_status = viability_object.get("execution_arc_viability_status", "invalid")
    reason_if_not = viability_object.get("named_reason_if_not_justified", "")

    if minimum_completion_signal_pass and viability_status == "justified":
        version_decision = "v0_15_0_even_broader_change_governance_ready"
        handoff_mode = "execute_first_even_broader_change_pack"
        status = "PASS"
        why = (
            "The carried baseline anchor, continuity mode, even-broader lever map, family separation rule, "
            "admission rules, comparison protocol, and viability gate are frozen cleanly enough to begin a first execution arc."
        )
    elif handoff.get("handoff_integrity_status") == "PASS":
        version_decision = "v0_15_0_even_broader_change_governance_partial"
        handoff_mode = "resolve_v0_15_0_governance_or_viability_gaps_first"
        status = "PASS"
        why = (
            "The governance direction is readable, but at least one minimum completion signal or the execution-arc viability gate "
            "does not yet support opening a new even-broader execution arc."
        )
    else:
        version_decision = "v0_15_0_handoff_phase_inputs_invalid"
        handoff_mode = "rebuild_v0_15_0_phase_inputs_first"
        status = "FAIL"
        why = "The carried handoff or even-broader governance layer is invalid."

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": version_decision.upper(),
        "conclusion": {
            "version_decision": version_decision,
            "even_broader_change_governance_status": governance_status,
            "governance_ready_for_runtime_execution": governance_ready_for_runtime_execution,
            "minimum_completion_signal_pass": minimum_completion_signal_pass,
            "named_first_even_broader_change_pack_ready": named_first_even_broader_change_pack_ready,
            "execution_arc_viability_status": viability_status,
            "named_reason_if_not_justified": reason_if_not,
            "why_this_is_or_is_not_ready": why,
            "v0_15_1_handoff_mode": handoff_mode,
        },
        "handoff_integrity": handoff,
        "governance_pack": governance,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.15.0 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- even_broader_change_governance_status: `{governance_status}`",
                f"- execution_arc_viability_status: `{viability_status}`",
                f"- v0_15_1_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.15.0 even-broader-change governance closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--governance-pack", default=str(DEFAULT_GOVERNANCE_PACK_OUT_DIR / "summary.json"))
    parser.add_argument("--v112-closeout", default=str(DEFAULT_V112_CLOSEOUT_PATH))
    parser.add_argument("--v141-closeout", default=str(DEFAULT_V141_CLOSEOUT_PATH))
    parser.add_argument("--v142-closeout", default=str(DEFAULT_V142_CLOSEOUT_PATH))
    parser.add_argument("--v143-closeout", default=str(DEFAULT_V143_CLOSEOUT_PATH))
    parser.add_argument("--continuity-check-mode", default="schema_only")
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v150_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        governance_pack_path=str(args.governance_pack),
        v112_closeout_path=str(args.v112_closeout),
        v141_closeout_path=str(args.v141_closeout),
        v142_closeout_path=str(args.v142_closeout),
        v143_closeout_path=str(args.v143_closeout),
        continuity_check_mode=str(args.continuity_check_mode),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
