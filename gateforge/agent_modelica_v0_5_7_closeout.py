from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_7_boundary_synthesis import build_v057_boundary_synthesis
from .agent_modelica_v0_5_7_common import (
    DEFAULT_BOUNDARY_SYNTHESIS_OUT_DIR,
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_PHASE_LEDGER_OUT_DIR,
    DEFAULT_STOP_AUDIT_OUT_DIR,
    DEFAULT_V0_6_HANDOFF_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_5_7_phase_ledger import build_v057_phase_ledger
from .agent_modelica_v0_5_7_stop_condition_audit import build_v057_stop_condition_audit
from .agent_modelica_v0_5_7_v0_6_handoff import build_v057_v0_6_handoff


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v057_closeout(
    *,
    phase_ledger_path: str = str(DEFAULT_PHASE_LEDGER_OUT_DIR / "summary.json"),
    stop_audit_path: str = str(DEFAULT_STOP_AUDIT_OUT_DIR / "summary.json"),
    boundary_synthesis_path: str = str(DEFAULT_BOUNDARY_SYNTHESIS_OUT_DIR / "summary.json"),
    v0_6_handoff_path: str = str(DEFAULT_V0_6_HANDOFF_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(phase_ledger_path).exists():
        build_v057_phase_ledger(out_dir=str(Path(phase_ledger_path).parent))
    if not Path(stop_audit_path).exists():
        build_v057_stop_condition_audit(out_dir=str(Path(stop_audit_path).parent))
    if not Path(boundary_synthesis_path).exists():
        build_v057_boundary_synthesis(out_dir=str(Path(boundary_synthesis_path).parent))
    if not Path(v0_6_handoff_path).exists():
        build_v057_v0_6_handoff(
            stop_audit_path=str(stop_audit_path),
            boundary_synthesis_path=str(boundary_synthesis_path),
            out_dir=str(Path(v0_6_handoff_path).parent),
        )

    ledger = load_json(phase_ledger_path)
    stop_audit = load_json(stop_audit_path)
    boundary = load_json(boundary_synthesis_path)
    handoff = load_json(v0_6_handoff_path)

    if not bool(ledger.get("phase_ledger_integrity_ok")):
        version_decision = "v0_5_7_handoff_substrate_invalid"
        phase_status = "v0_5_phase_integrity_invalid"
    elif bool(stop_audit.get("overall_stop_condition_met")):
        version_decision = "v0_5_phase_complete_prepare_v0_6"
        phase_status = "post_learning_generalization_and_boundary_mapping_complete"
    elif int(stop_audit.get("remaining_gap_count") or 0) == 1:
        version_decision = "v0_5_phase_partial_one_gap_remaining"
        phase_status = "post_learning_generalization_and_boundary_mapping_nearly_complete"
    else:
        version_decision = "v0_5_phase_not_ready_for_closeout"
        phase_status = "post_learning_generalization_and_boundary_mapping_incomplete"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": "V0_5_PHASE_SYNTHESIS_READY",
        "conclusion": {
            "version_decision": version_decision,
            "phase_status": phase_status,
            "remaining_gap_count": stop_audit.get("remaining_gap_count"),
            "v0_6_primary_phase_question": handoff.get("v0_6_primary_phase_question"),
            "v0_6_0_handoff_mode": handoff.get("v0_6_0_handoff_mode"),
            "do_not_continue_v0_5_branch_expansion_by_default": version_decision == "v0_5_phase_complete_prepare_v0_6",
            "explained_failure_count": boundary.get("explained_failure_count"),
            "deferred_boundary_count": boundary.get("deferred_boundary_count"),
        },
        "phase_ledger": ledger,
        "stop_condition_audit": stop_audit,
        "boundary_synthesis": boundary,
        "v0_6_handoff": handoff,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.7 Closeout",
                "",
                f"- version_decision: `{(payload.get('conclusion') or {}).get('version_decision')}`",
                f"- phase_status: `{(payload.get('conclusion') or {}).get('phase_status')}`",
                f"- v0_6_primary_phase_question: `{(payload.get('conclusion') or {}).get('v0_6_primary_phase_question')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.7 phase closeout.")
    parser.add_argument("--phase-ledger", default=str(DEFAULT_PHASE_LEDGER_OUT_DIR / "summary.json"))
    parser.add_argument("--stop-audit", default=str(DEFAULT_STOP_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--boundary-synthesis", default=str(DEFAULT_BOUNDARY_SYNTHESIS_OUT_DIR / "summary.json"))
    parser.add_argument("--v0-6-handoff", default=str(DEFAULT_V0_6_HANDOFF_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v057_closeout(
        phase_ledger_path=str(args.phase_ledger),
        stop_audit_path=str(args.stop_audit),
        boundary_synthesis_path=str(args.boundary_synthesis),
        v0_6_handoff_path=str(args.v0_6_handoff),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
