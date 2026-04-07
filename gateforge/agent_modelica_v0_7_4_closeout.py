from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_7_4_adjudication import build_v074_adjudication
from .agent_modelica_v0_7_4_common import (
    DEFAULT_ADJUDICATION_OUT_DIR,
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_7_4_handoff_integrity import build_v074_handoff_integrity


def build_v074_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    adjudication_path: str = str(DEFAULT_ADJUDICATION_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v074_handoff_integrity(out_dir=str(Path(handoff_integrity_path).parent))
    integrity = load_json(handoff_integrity_path)
    if integrity.get("status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_7_4_HANDOFF_SUBSTRATE_INVALID",
            "conclusion": {
                "version_decision": "v0_7_4_handoff_substrate_invalid",
                "readiness_adjudication_status": "invalid",
                "supported_floor_passed": None,
                "partial_floor_passed": None,
                "fallback_floor_passed": None,
                "bounded_uncovered_subtype_candidate_share_pct_reference": None,
                "dominant_pressure_source_reference": None,
                "v0_7_5_handoff_mode": "repair_mid_phase_readiness_substrate_first",
            },
            "handoff_integrity": integrity,
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.7.4 Closeout\n")
        return payload

    if not Path(adjudication_path).exists():
        build_v074_adjudication(out_dir=str(Path(adjudication_path).parent))
    adjudication = load_json(adjudication_path)
    status = str(adjudication.get("readiness_adjudication_status") or "invalid")

    if status == "supported":
        version_decision = "v0_7_4_open_world_readiness_supported"
        handoff_mode = "prepare_late_phase_promotion_or_closeout_inputs"
    elif status == "partial_but_interpretable":
        version_decision = "v0_7_4_open_world_readiness_partial_but_interpretable"
        handoff_mode = "continue_open_world_readiness_refinement_under_same_logic"
    elif status == "fallback_to_targeted_expansion_needed":
        version_decision = "v0_7_4_fallback_to_targeted_expansion_needed"
        handoff_mode = "reassess_targeted_expansion_reentry"
    else:
        version_decision = "v0_7_4_handoff_substrate_invalid"
        handoff_mode = "repair_mid_phase_readiness_substrate_first"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": "PASS" if status != "invalid" else "FAIL",
        "closeout_status": {
            "supported": "V0_7_4_OPEN_WORLD_READINESS_SUPPORTED",
            "partial_but_interpretable": "V0_7_4_OPEN_WORLD_READINESS_PARTIAL_BUT_INTERPRETABLE",
            "fallback_to_targeted_expansion_needed": "V0_7_4_FALLBACK_TO_TARGETED_EXPANSION_NEEDED",
            "invalid": "V0_7_4_HANDOFF_SUBSTRATE_INVALID",
        }[status],
        "conclusion": {
            "version_decision": version_decision,
            "readiness_adjudication_status": status,
            "supported_floor_passed": adjudication.get("supported_floor_passed"),
            "partial_floor_passed": adjudication.get("partial_floor_passed"),
            "fallback_floor_passed": adjudication.get("fallback_floor_passed"),
            "bounded_uncovered_subtype_candidate_share_pct_reference": adjudication.get(
                "bounded_uncovered_subtype_candidate_share_pct_reference"
            ),
            "dominant_pressure_source_reference": adjudication.get("dominant_pressure_source_reference"),
            "v0_7_5_handoff_mode": handoff_mode,
        },
        "handoff_integrity": integrity,
        "adjudication": adjudication,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.4 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- readiness_adjudication_status: `{status}`",
                f"- supported_floor_passed: `{adjudication.get('supported_floor_passed')}`",
                f"- partial_floor_passed: `{adjudication.get('partial_floor_passed')}`",
                f"- fallback_floor_passed: `{adjudication.get('fallback_floor_passed')}`",
                f"- v0_7_5_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.4 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--adjudication", default=str(DEFAULT_ADJUDICATION_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v074_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        adjudication_path=str(args.adjudication),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
