from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_12_0_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_GOVERNANCE_PACK_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V111_CLOSEOUT_PATH,
    DEFAULT_V112_CLOSEOUT_PATH,
    DEFAULT_V115_CLOSEOUT_PATH,
    DEFAULT_V117_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_12_0_governance_pack import build_v120_governance_pack
from .agent_modelica_v0_12_0_handoff_integrity import build_v120_handoff_integrity


def build_v120_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    governance_pack_path: str = str(DEFAULT_GOVERNANCE_PACK_OUT_DIR / "summary.json"),
    v111_closeout_path: str = str(DEFAULT_V111_CLOSEOUT_PATH),
    v112_closeout_path: str = str(DEFAULT_V112_CLOSEOUT_PATH),
    v115_closeout_path: str = str(DEFAULT_V115_CLOSEOUT_PATH),
    v117_closeout_path: str = str(DEFAULT_V117_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    handoff_path_obj = Path(handoff_integrity_path)
    governance_path_obj = Path(governance_pack_path)

    if not handoff_path_obj.exists():
        build_v120_handoff_integrity(
            v111_closeout_path=v111_closeout_path,
            v112_closeout_path=v112_closeout_path,
            v115_closeout_path=v115_closeout_path,
            v117_closeout_path=v117_closeout_path,
            out_dir=str(handoff_path_obj.parent),
        )
    handoff = load_json(handoff_integrity_path)
    if handoff.get("handoff_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_12_0_OPERATIONAL_REMEDY_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_12_0_operational_remedy_inputs_invalid",
                "operational_remedy_governance_status": "invalid",
                "v0_12_1_handoff_mode": "rebuild_operational_remedy_governance_first",
            },
            "handoff_integrity": handoff,
        }
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.12.0 Closeout\n\n- version_decision: `v0_12_0_operational_remedy_inputs_invalid`\n")
        return payload

    if not governance_path_obj.exists():
        build_v120_governance_pack(
            v111_closeout_path=v111_closeout_path,
            v112_closeout_path=v112_closeout_path,
            v115_closeout_path=v115_closeout_path,
            v117_closeout_path=v117_closeout_path,
            out_dir=str(governance_path_obj.parent),
        )
    governance = load_json(governance_pack_path)

    governance_status = governance.get("operational_remedy_governance_status", "invalid")
    governance_ready_for_runtime_execution = bool(governance.get("governance_ready_for_runtime_execution"))
    named_first_remedy_pack_ready = bool(governance.get("named_first_remedy_pack_ready"))

    if governance_status == "invalid":
        version_decision = "v0_12_0_operational_remedy_inputs_invalid"
        handoff_mode = "rebuild_operational_remedy_governance_first"
        status = "FAIL"
        why = "The carried handoff or the operational-remedy governance layer is invalid, so no runtime remedy execution should begin."
    elif (
        governance_status == "governance_ready"
        and governance_ready_for_runtime_execution
        and named_first_remedy_pack_ready
    ):
        version_decision = "v0_12_0_operational_remedy_governance_ready"
        handoff_mode = "execute_first_bounded_operational_remedy_pack"
        status = "PASS"
        why = "The carried baseline, remedy registry, admission rules, comparison protocol, and runtime remedy-evaluation contract are frozen cleanly enough to begin first-pass real remedy execution."
    elif governance_status == "governance_partial":
        version_decision = "v0_12_0_operational_remedy_governance_partial"
        handoff_mode = "finish_operational_remedy_governance_before_runtime_execution"
        status = "PASS"
        why = "The direction is valid, but at least one minimum governance signal remains incomplete and runtime remedy execution should not begin yet."
    else:
        version_decision = "v0_12_0_operational_remedy_inputs_invalid"
        handoff_mode = "rebuild_operational_remedy_governance_first"
        status = "FAIL"
        why = "The governance closeout state is not internally coherent."

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": version_decision.upper(),
        "conclusion": {
            "version_decision": version_decision,
            "operational_remedy_governance_status": governance_status,
            "governance_ready_for_runtime_execution": governance_ready_for_runtime_execution,
            "minimum_completion_signal_pass": governance.get("minimum_completion_signal_pass"),
            "named_first_remedy_pack_ready": named_first_remedy_pack_ready,
            "why_this_is_or_is_not_ready": why,
            "v0_12_1_handoff_mode": handoff_mode,
        },
        "handoff_integrity": handoff,
        "governance_pack": governance,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.12.0 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- operational_remedy_governance_status: `{governance_status}`",
                f"- v0_12_1_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.12.0 operational-remedy governance closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--governance-pack", default=str(DEFAULT_GOVERNANCE_PACK_OUT_DIR / "summary.json"))
    parser.add_argument("--v111-closeout", default=str(DEFAULT_V111_CLOSEOUT_PATH))
    parser.add_argument("--v112-closeout", default=str(DEFAULT_V112_CLOSEOUT_PATH))
    parser.add_argument("--v115-closeout", default=str(DEFAULT_V115_CLOSEOUT_PATH))
    parser.add_argument("--v117-closeout", default=str(DEFAULT_V117_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v120_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        governance_pack_path=str(args.governance_pack),
        v111_closeout_path=str(args.v111_closeout),
        v112_closeout_path=str(args.v112_closeout),
        v115_closeout_path=str(args.v115_closeout),
        v117_closeout_path=str(args.v117_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
