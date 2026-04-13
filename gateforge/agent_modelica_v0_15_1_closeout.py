from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_15_1_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V150_CLOSEOUT_PATH,
    DEFAULT_VIABILITY_RESOLUTION_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_15_1_handoff_integrity import build_v151_handoff_integrity
from .agent_modelica_v0_15_1_viability_resolution import build_v151_viability_resolution


def build_v151_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    viability_resolution_path: str = str(DEFAULT_VIABILITY_RESOLUTION_OUT_DIR / "summary.json"),
    v150_closeout_path: str = str(DEFAULT_V150_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    handoff_path_obj = Path(handoff_integrity_path)
    if not handoff_path_obj.exists():
        build_v151_handoff_integrity(
            v150_closeout_path=v150_closeout_path,
            out_dir=str(handoff_path_obj.parent),
        )
    handoff = load_json(handoff_integrity_path)
    if handoff.get("handoff_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_15_1_HANDOFF_PHASE_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_15_1_handoff_phase_inputs_invalid",
                "execution_arc_viability_status": "invalid",
                "named_first_even_broader_change_pack_ready": False,
                "named_reason_if_not_justified": "handoff_phase_inputs_invalid",
                "v0_15_2_handoff_mode": "rebuild_v0_15_1_phase_inputs_first",
            },
            "handoff_integrity": handoff,
        }
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.15.1 Closeout\n\n- version_decision: `v0_15_1_handoff_phase_inputs_invalid`\n")
        return payload

    viability_path_obj = Path(viability_resolution_path)
    if not viability_path_obj.exists():
        build_v151_viability_resolution(
            v150_closeout_path=v150_closeout_path,
            out_dir=str(viability_path_obj.parent),
        )
    viability = load_json(viability_resolution_path)
    viability_obj = viability.get("execution_arc_viability_reassessment_object") if isinstance(viability.get("execution_arc_viability_reassessment_object"), dict) else {}
    pack_obj = viability.get("first_even_broader_pack_readiness_object") if isinstance(viability.get("first_even_broader_pack_readiness_object"), dict) else {}

    execution_arc_viability_status = str(viability_obj.get("execution_arc_viability_status") or "invalid")
    named_first_even_broader_change_pack_ready = bool(pack_obj.get("named_first_even_broader_change_pack_ready"))
    named_reason_if_not_justified = str(viability_obj.get("named_reason_if_not_justified") or "")

    if execution_arc_viability_status == "justified" and named_first_even_broader_change_pack_ready:
        version_decision = "v0_15_1_even_broader_execution_ready"
        handoff_mode = "execute_first_even_broader_change_pack"
        status = "PASS"
    elif execution_arc_viability_status == "invalid":
        version_decision = "v0_15_1_handoff_phase_inputs_invalid"
        handoff_mode = "rebuild_v0_15_1_phase_inputs_first"
        status = "FAIL"
    else:
        version_decision = "v0_15_1_even_broader_execution_not_justified"
        handoff_mode = "prepare_v0_15_phase_synthesis"
        status = "PASS"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": version_decision.upper(),
        "conclusion": {
            "version_decision": version_decision,
            "execution_arc_viability_status": execution_arc_viability_status,
            "named_first_even_broader_change_pack_ready": named_first_even_broader_change_pack_ready,
            "named_reason_if_not_justified": named_reason_if_not_justified,
            "v0_15_2_handoff_mode": handoff_mode,
        },
        "handoff_integrity": handoff,
        "viability_resolution": viability,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.15.1 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- execution_arc_viability_status: `{execution_arc_viability_status}`",
                f"- v0_15_2_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.15.1 viability-resolution closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--viability-resolution", default=str(DEFAULT_VIABILITY_RESOLUTION_OUT_DIR / "summary.json"))
    parser.add_argument("--v150-closeout", default=str(DEFAULT_V150_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v151_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        viability_resolution_path=str(args.viability_resolution),
        v150_closeout_path=str(args.v150_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
