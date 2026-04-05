from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_0_boundary_gate import build_v050_boundary_gate
from .agent_modelica_v0_5_0_candidate_pack import build_v050_candidate_pack
from .agent_modelica_v0_5_0_common import (
    DEFAULT_BOUNDARY_GATE_OUT_DIR,
    DEFAULT_CANDIDATE_PACK_OUT_DIR,
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_DISPATCH_AUDIT_OUT_DIR,
    DEFAULT_WIDENED_SPEC_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_5_0_dispatch_cleanliness_audit import build_v050_dispatch_cleanliness_audit
from .agent_modelica_v0_5_0_widened_spec import build_v050_widened_spec


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v050_closeout(
    *,
    widened_spec_path: str = str(DEFAULT_WIDENED_SPEC_OUT_DIR / "summary.json"),
    candidate_pack_path: str = str(DEFAULT_CANDIDATE_PACK_OUT_DIR / "summary.json"),
    dispatch_cleanliness_audit_path: str = str(DEFAULT_DISPATCH_AUDIT_OUT_DIR / "summary.json"),
    boundary_gate_path: str = str(DEFAULT_BOUNDARY_GATE_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(widened_spec_path).exists():
        build_v050_widened_spec(out_dir=str(Path(widened_spec_path).parent))
    if not Path(candidate_pack_path).exists():
        build_v050_candidate_pack(
            widened_spec_path=str(widened_spec_path),
            out_dir=str(Path(candidate_pack_path).parent),
        )
    if not Path(dispatch_cleanliness_audit_path).exists():
        build_v050_dispatch_cleanliness_audit(
            widened_spec_path=str(widened_spec_path),
            candidate_pack_path=str(candidate_pack_path),
            out_dir=str(Path(dispatch_cleanliness_audit_path).parent),
        )
    if not Path(boundary_gate_path).exists():
        build_v050_boundary_gate(
            widened_spec_path=str(widened_spec_path),
            candidate_pack_path=str(candidate_pack_path),
            dispatch_cleanliness_audit_path=str(dispatch_cleanliness_audit_path),
            out_dir=str(Path(boundary_gate_path).parent),
        )

    spec = load_json(widened_spec_path)
    pack = load_json(candidate_pack_path)
    dispatch = load_json(dispatch_cleanliness_audit_path)
    gate = load_json(boundary_gate_path)

    admission = str(dispatch.get("dispatch_cleanliness_admission") or "")
    qualitative_confirmed = bool(gate.get("qualitative_widening_confirmed"))
    wider_than_targeted = bool(gate.get("wider_than_v0_4_targeted_slice"))
    substrate_ready = bool(pack.get("widened_pack_ready"))
    dispatch_cleanliness_preserved = admission in {"promoted", "degraded_but_executable"}

    if substrate_ready and qualitative_confirmed and admission == "promoted":
        version_decision = "v0_5_0_widened_real_substrate_ready"
        widened_real_substrate_status = "ready"
        handoff_mode = (
            "run_boundary_mapping_first_on_frozen_slice"
            if bool(gate.get("interpretable_failure_bucket_seed_available"))
            else "run_broader_real_validation_on_frozen_slice"
        )
    elif dispatch_cleanliness_preserved and wider_than_targeted:
        version_decision = "v0_5_0_widened_real_substrate_partial"
        widened_real_substrate_status = "partial"
        handoff_mode = "run_broader_real_validation_on_frozen_slice" if admission == "degraded_but_executable" else "repair_widened_real_substrate_gaps_first"
    else:
        version_decision = "v0_5_0_widened_real_substrate_not_ready"
        widened_real_substrate_status = "not_ready"
        handoff_mode = "repair_widened_real_substrate_gaps_first"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": "V0_5_0_WIDENED_REAL_SUBSTRATE_SYNTHESIS_READY",
        "conclusion": {
            "version_decision": version_decision,
            "widened_real_substrate_status": widened_real_substrate_status,
            "qualitative_widening_confirmed": qualitative_confirmed,
            "dispatch_cleanliness_preserved": dispatch_cleanliness_preserved,
            "v0_5_1_handoff_mode": handoff_mode,
            "v0_5_1_primary_eval_question": "On the frozen widened real slice, which currently supported behavior remains stable and which cases begin to expose a real capability boundary?",
        },
        "widened_spec": spec,
        "candidate_pack": pack,
        "dispatch_cleanliness_audit": dispatch,
        "boundary_mapping_gate": gate,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.0 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- widened_real_substrate_status: `{widened_real_substrate_status}`",
                f"- v0_5_1_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.0 widened real-distribution substrate closeout.")
    parser.add_argument("--widened-spec", default=str(DEFAULT_WIDENED_SPEC_OUT_DIR / "summary.json"))
    parser.add_argument("--candidate-pack", default=str(DEFAULT_CANDIDATE_PACK_OUT_DIR / "summary.json"))
    parser.add_argument("--dispatch-cleanliness-audit", default=str(DEFAULT_DISPATCH_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--boundary-gate", default=str(DEFAULT_BOUNDARY_GATE_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v050_closeout(
        widened_spec_path=str(args.widened_spec),
        candidate_pack_path=str(args.candidate_pack),
        dispatch_cleanliness_audit_path=str(args.dispatch_cleanliness_audit),
        boundary_gate_path=str(args.boundary_gate),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
