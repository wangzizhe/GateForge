from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_6_3_candidate_adjudication import build_v063_candidate_adjudication
from .agent_modelica_v0_6_3_common import (
    DEFAULT_CANDIDATE_ADJUDICATION_OUT_DIR,
    DEFAULT_DECISION_BASIS_OUT_DIR,
    DEFAULT_DECISION_INPUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_6_3_phase_decision_input import build_v063_phase_decision_input


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_decision_basis"


def build_v063_decision_basis(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    phase_decision_input_path: str = str(DEFAULT_DECISION_INPUT_OUT_DIR / "summary.json"),
    candidate_adjudication_path: str = str(DEFAULT_CANDIDATE_ADJUDICATION_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_DECISION_BASIS_OUT_DIR),
) -> dict:
    if not Path(phase_decision_input_path).exists():
        build_v063_phase_decision_input(out_dir=str(Path(phase_decision_input_path).parent))
    if not Path(candidate_adjudication_path).exists():
        build_v063_candidate_adjudication(
            phase_decision_input_path=phase_decision_input_path,
            out_dir=str(Path(candidate_adjudication_path).parent),
        )

    integrity = load_json(handoff_integrity_path) if Path(handoff_integrity_path).exists() else {"status": "FAIL"}
    phase_input = load_json(phase_decision_input_path)
    candidate = load_json(candidate_adjudication_path)

    open_world = bool(candidate.get("open_world_candidate_supported"))
    targeted = bool(candidate.get("targeted_expansion_candidate_supported"))

    if integrity.get("status") != "PASS":
        decision_basis_status = "invalid"
        phase_decision_basis_gap = "upstream_profile_integrity_invalid"
        can_enter_late_v0_6_phase_decision = False
    elif open_world or targeted:
        decision_basis_status = "ready"
        phase_decision_basis_gap = "none"
        can_enter_late_v0_6_phase_decision = True
    else:
        decision_basis_status = "partial"
        phase_decision_basis_gap = "neither_candidate_threshold_met"
        can_enter_late_v0_6_phase_decision = False

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if decision_basis_status in {"ready", "partial"} else "FAIL",
        "decision_basis_status": decision_basis_status,
        "open_world_candidate_supported": open_world,
        "targeted_expansion_candidate_supported": targeted,
        "dominant_next_phase_pressure_source": candidate.get("dominant_next_phase_pressure_source"),
        "phase_decision_basis_gap": phase_decision_basis_gap,
        "can_enter_late_v0_6_phase_decision": can_enter_late_v0_6_phase_decision,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.6.3 Decision Basis",
                "",
                f"- decision_basis_status: `{decision_basis_status}`",
                f"- open_world_candidate_supported: `{open_world}`",
                f"- targeted_expansion_candidate_supported: `{targeted}`",
                f"- phase_decision_basis_gap: `{phase_decision_basis_gap}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.6.3 decision basis adjudication.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--phase-decision-input", default=str(DEFAULT_DECISION_INPUT_OUT_DIR / "summary.json"))
    parser.add_argument("--candidate-adjudication", default=str(DEFAULT_CANDIDATE_ADJUDICATION_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_DECISION_BASIS_OUT_DIR))
    args = parser.parse_args()
    payload = build_v063_decision_basis(
        handoff_integrity_path=str(args.handoff_integrity),
        phase_decision_input_path=str(args.phase_decision_input),
        candidate_adjudication_path=str(args.candidate_adjudication),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "decision_basis_status": payload.get("decision_basis_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
