from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_6_3_candidate_adjudication import build_v063_candidate_adjudication
from .agent_modelica_v0_6_3_common import (
    DEFAULT_CANDIDATE_ADJUDICATION_OUT_DIR,
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_DECISION_BASIS_OUT_DIR,
    DEFAULT_DECISION_INPUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_6_3_decision_basis import build_v063_decision_basis
from .agent_modelica_v0_6_3_handoff_integrity import build_v063_handoff_integrity
from .agent_modelica_v0_6_3_phase_decision_input import build_v063_phase_decision_input


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v063_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    phase_decision_input_path: str = str(DEFAULT_DECISION_INPUT_OUT_DIR / "summary.json"),
    candidate_adjudication_path: str = str(DEFAULT_CANDIDATE_ADJUDICATION_OUT_DIR / "summary.json"),
    decision_basis_path: str = str(DEFAULT_DECISION_BASIS_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v063_handoff_integrity(out_dir=str(Path(handoff_integrity_path).parent))
    if not Path(phase_decision_input_path).exists():
        build_v063_phase_decision_input(
            handoff_integrity_path=handoff_integrity_path,
            out_dir=str(Path(phase_decision_input_path).parent),
        )
    if not Path(candidate_adjudication_path).exists():
        build_v063_candidate_adjudication(
            phase_decision_input_path=phase_decision_input_path,
            out_dir=str(Path(candidate_adjudication_path).parent),
        )
    if not Path(decision_basis_path).exists():
        build_v063_decision_basis(
            handoff_integrity_path=handoff_integrity_path,
            phase_decision_input_path=phase_decision_input_path,
            candidate_adjudication_path=candidate_adjudication_path,
            out_dir=str(Path(decision_basis_path).parent),
        )

    integrity = load_json(handoff_integrity_path)
    candidate = load_json(candidate_adjudication_path)
    decision = load_json(decision_basis_path)

    status = str(decision.get("decision_basis_status") or "invalid")
    if integrity.get("status") != "PASS" or status == "invalid":
        version_decision = "v0_6_3_handoff_substrate_invalid"
        handoff_mode = "repair_phase_decision_basis_first"
    elif status == "partial":
        version_decision = "v0_6_3_phase_decision_basis_partial"
        handoff_mode = "continue_late_v0_6_decision_preparation"
    else:
        version_decision = "v0_6_3_phase_decision_basis_ready"
        handoff_mode = "run_late_v0_6_phase_decision"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if version_decision != "v0_6_3_handoff_substrate_invalid" else "FAIL",
        "closeout_status": (
            "V0_6_3_PHASE_DECISION_BASIS_READY"
            if version_decision == "v0_6_3_phase_decision_basis_ready"
            else (
                "V0_6_3_PHASE_DECISION_BASIS_PARTIAL"
                if version_decision == "v0_6_3_phase_decision_basis_partial"
                else "V0_6_3_HANDOFF_SUBSTRATE_INVALID"
            )
        ),
        "conclusion": {
            "version_decision": version_decision,
            "decision_basis_status": status,
            "phase_decision_basis_gap": decision.get("phase_decision_basis_gap"),
            "open_world_candidate_supported": candidate.get("open_world_candidate_supported"),
            "targeted_expansion_candidate_supported": candidate.get("targeted_expansion_candidate_supported"),
            "dominant_next_phase_pressure_source": candidate.get("dominant_next_phase_pressure_source"),
            "v0_6_4_handoff_mode": handoff_mode,
            "do_not_reopen_v0_5_boundary_pressure_by_default": True,
        },
        "handoff_integrity": integrity,
        "phase_decision_input": load_json(phase_decision_input_path),
        "candidate_adjudication": candidate,
        "decision_basis": decision,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.6.3 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- decision_basis_status: `{status}`",
                f"- open_world_candidate_supported: `{candidate.get('open_world_candidate_supported')}`",
                f"- targeted_expansion_candidate_supported: `{candidate.get('targeted_expansion_candidate_supported')}`",
                f"- v0_6_4_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.6.3 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--phase-decision-input", default=str(DEFAULT_DECISION_INPUT_OUT_DIR / "summary.json"))
    parser.add_argument("--candidate-adjudication", default=str(DEFAULT_CANDIDATE_ADJUDICATION_OUT_DIR / "summary.json"))
    parser.add_argument("--decision-basis", default=str(DEFAULT_DECISION_BASIS_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v063_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        phase_decision_input_path=str(args.phase_decision_input),
        candidate_adjudication_path=str(args.candidate_adjudication),
        decision_basis_path=str(args.decision_basis),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
