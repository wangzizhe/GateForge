from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_6_4_candidate_pressure import build_v064_candidate_pressure
from .agent_modelica_v0_6_4_common import (
    DEFAULT_CANDIDATE_PRESSURE_OUT_DIR,
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_DECISION_MATURITY_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_PROFILE_REFINEMENT_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_6_4_decision_maturity import build_v064_decision_maturity
from .agent_modelica_v0_6_4_handoff_integrity import build_v064_handoff_integrity
from .agent_modelica_v0_6_4_profile_refinement import build_v064_profile_refinement


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v064_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    profile_refinement_path: str = str(DEFAULT_PROFILE_REFINEMENT_OUT_DIR / "summary.json"),
    candidate_pressure_path: str = str(DEFAULT_CANDIDATE_PRESSURE_OUT_DIR / "summary.json"),
    decision_maturity_path: str = str(DEFAULT_DECISION_MATURITY_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v064_handoff_integrity(out_dir=str(Path(handoff_integrity_path).parent))
    integrity = load_json(handoff_integrity_path)
    if integrity.get("status") != "PASS":
        version_decision = "v0_6_4_handoff_substrate_invalid"
        handoff_mode = "repair_phase_decision_basis_first"
        payload = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_6_4_HANDOFF_SUBSTRATE_INVALID",
            "conclusion": {
                "version_decision": version_decision,
                "decision_input_maturity": "invalid",
                "maturity_gap": "upstream_chain_integrity_invalid",
                "open_world_candidate_supported": False,
                "targeted_expansion_candidate_supported": False,
                "near_miss_open_world_candidate": False,
                "near_miss_targeted_expansion_candidate": False,
                "fluid_network_extension_blocking_open_world": None,
                "v0_6_5_handoff_mode": handoff_mode,
                "do_not_reopen_v0_5_boundary_pressure_by_default": True,
            },
            "handoff_integrity": integrity,
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", payload)
        write_text(
            out_root / "summary.md",
            "\n".join(
                [
                    "# v0.6.4 Closeout",
                    "",
                    f"- version_decision: `{version_decision}`",
                    "- decision_input_maturity: `invalid`",
                    f"- v0_6_5_handoff_mode: `{handoff_mode}`",
                ]
            ),
        )
        return payload

    if not Path(profile_refinement_path).exists():
        build_v064_profile_refinement(
            handoff_integrity_path=handoff_integrity_path,
            out_dir=str(Path(profile_refinement_path).parent),
        )
    if not Path(candidate_pressure_path).exists():
        build_v064_candidate_pressure(
            profile_refinement_path=profile_refinement_path,
            out_dir=str(Path(candidate_pressure_path).parent),
        )
    if not Path(decision_maturity_path).exists():
        build_v064_decision_maturity(
            handoff_integrity_path=handoff_integrity_path,
            profile_refinement_path=profile_refinement_path,
            candidate_pressure_path=candidate_pressure_path,
            out_dir=str(Path(decision_maturity_path).parent),
        )

    candidate = load_json(candidate_pressure_path)
    maturity = load_json(decision_maturity_path)

    status = str(maturity.get("decision_input_maturity") or "invalid")
    if status == "invalid":
        version_decision = "v0_6_4_handoff_substrate_invalid"
        handoff_mode = "repair_phase_decision_basis_first"
    elif status == "ready":
        version_decision = "v0_6_4_phase_decision_input_ready"
        handoff_mode = "run_late_v0_6_phase_decision"
    else:
        version_decision = "v0_6_4_phase_decision_input_partial"
        handoff_mode = "continue_late_v0_6_decision_preparation"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if version_decision != "v0_6_4_handoff_substrate_invalid" else "FAIL",
        "closeout_status": (
            "V0_6_4_PHASE_DECISION_INPUT_READY"
            if version_decision == "v0_6_4_phase_decision_input_ready"
            else (
                "V0_6_4_PHASE_DECISION_INPUT_PARTIAL"
                if version_decision == "v0_6_4_phase_decision_input_partial"
                else "V0_6_4_HANDOFF_SUBSTRATE_INVALID"
            )
        ),
        "conclusion": {
            "version_decision": version_decision,
            "decision_input_maturity": status,
            "maturity_gap": maturity.get("maturity_gap"),
            "open_world_candidate_supported": candidate.get("open_world_candidate_supported"),
            "targeted_expansion_candidate_supported": candidate.get("targeted_expansion_candidate_supported"),
            "near_miss_open_world_candidate": candidate.get("near_miss_open_world_candidate"),
            "near_miss_targeted_expansion_candidate": candidate.get("near_miss_targeted_expansion_candidate"),
            "fluid_network_extension_blocking_open_world": candidate.get("fluid_network_extension_blocking_open_world"),
            "v0_6_5_handoff_mode": handoff_mode,
            "do_not_reopen_v0_5_boundary_pressure_by_default": True,
        },
        "handoff_integrity": integrity,
        "profile_refinement": load_json(profile_refinement_path),
        "candidate_pressure": candidate,
        "decision_maturity": maturity,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.6.4 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- decision_input_maturity: `{status}`",
                f"- near_miss_open_world_candidate: `{candidate.get('near_miss_open_world_candidate')}`",
                f"- fluid_network_extension_blocking_open_world: `{candidate.get('fluid_network_extension_blocking_open_world')}`",
                f"- v0_6_5_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.6.4 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--profile-refinement", default=str(DEFAULT_PROFILE_REFINEMENT_OUT_DIR / "summary.json"))
    parser.add_argument("--candidate-pressure", default=str(DEFAULT_CANDIDATE_PRESSURE_OUT_DIR / "summary.json"))
    parser.add_argument("--decision-maturity", default=str(DEFAULT_DECISION_MATURITY_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v064_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        profile_refinement_path=str(args.profile_refinement),
        candidate_pressure_path=str(args.candidate_pressure),
        decision_maturity_path=str(args.decision_maturity),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
