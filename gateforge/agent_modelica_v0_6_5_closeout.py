from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_6_5_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_DECISION_MATURITY_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_OPEN_WORLD_RECHECK_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_6_5_decision_maturity import build_v065_decision_maturity
from .agent_modelica_v0_6_5_handoff_integrity import build_v065_handoff_integrity
from .agent_modelica_v0_6_5_open_world_recheck import build_v065_open_world_recheck


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v065_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    open_world_recheck_path: str = str(DEFAULT_OPEN_WORLD_RECHECK_OUT_DIR / "summary.json"),
    decision_maturity_path: str = str(DEFAULT_DECISION_MATURITY_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v065_handoff_integrity(out_dir=str(Path(handoff_integrity_path).parent))

    integrity = load_json(handoff_integrity_path)
    if integrity.get("status") != "PASS":
        version_decision = "v0_6_5_handoff_substrate_invalid"
        handoff_mode = "repair_late_phase_decision_inputs_first"
        payload = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_6_5_HANDOFF_SUBSTRATE_INVALID",
            "conclusion": {
                "version_decision": version_decision,
                "decision_input_maturity": "invalid",
                "open_world_candidate_supported_after_recheck": False,
                "open_world_margin_vs_floor_pct": None,
                "dominant_remaining_authority_gap": "upstream_chain_integrity_invalid",
                "fluid_network_still_not_blocking": None,
                "v0_6_6_handoff_mode": handoff_mode,
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
                    "# v0.6.5 Closeout",
                    "",
                    f"- version_decision: `{version_decision}`",
                    "- decision_input_maturity: `invalid`",
                    f"- v0_6_6_handoff_mode: `{handoff_mode}`",
                ]
            ),
        )
        return payload

    if not Path(open_world_recheck_path).exists():
        build_v065_open_world_recheck(
            handoff_integrity_path=handoff_integrity_path,
            out_dir=str(Path(open_world_recheck_path).parent),
        )
    if not Path(decision_maturity_path).exists():
        build_v065_decision_maturity(
            handoff_integrity_path=handoff_integrity_path,
            open_world_recheck_path=open_world_recheck_path,
            out_dir=str(Path(decision_maturity_path).parent),
        )

    recheck = load_json(open_world_recheck_path)
    maturity = load_json(decision_maturity_path)
    status = str(maturity.get("decision_input_maturity") or "invalid")

    if status == "invalid":
        version_decision = "v0_6_5_handoff_substrate_invalid"
        handoff_mode = "repair_late_phase_decision_inputs_first"
    elif status == "ready":
        version_decision = "v0_6_5_phase_decision_ready"
        handoff_mode = "run_late_v0_6_phase_decision"
    else:
        version_decision = "v0_6_5_phase_decision_partial"
        handoff_mode = "run_one_last_late_phase_gap_closure"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if version_decision != "v0_6_5_handoff_substrate_invalid" else "FAIL",
        "closeout_status": (
            "V0_6_5_PHASE_DECISION_READY"
            if version_decision == "v0_6_5_phase_decision_ready"
            else (
                "V0_6_5_PHASE_DECISION_PARTIAL"
                if version_decision == "v0_6_5_phase_decision_partial"
                else "V0_6_5_HANDOFF_SUBSTRATE_INVALID"
            )
        ),
        "conclusion": {
            "version_decision": version_decision,
            "decision_input_maturity": status,
            "open_world_candidate_supported_after_recheck": recheck.get("open_world_candidate_supported_after_recheck"),
            "open_world_margin_vs_floor_pct": recheck.get("open_world_margin_vs_floor_pct"),
            "dominant_remaining_authority_gap": recheck.get("dominant_remaining_authority_gap"),
            "fluid_network_still_not_blocking": recheck.get("fluid_network_still_not_blocking"),
            "v0_6_6_handoff_mode": handoff_mode,
            "do_not_reopen_v0_5_boundary_pressure_by_default": True,
        },
        "handoff_integrity": integrity,
        "open_world_recheck": recheck,
        "decision_maturity": maturity,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.6.5 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- decision_input_maturity: `{status}`",
                f"- open_world_margin_vs_floor_pct: `{recheck.get('open_world_margin_vs_floor_pct')}`",
                f"- dominant_remaining_authority_gap: `{recheck.get('dominant_remaining_authority_gap')}`",
                f"- v0_6_6_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.6.5 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--open-world-recheck", default=str(DEFAULT_OPEN_WORLD_RECHECK_OUT_DIR / "summary.json"))
    parser.add_argument("--decision-maturity", default=str(DEFAULT_DECISION_MATURITY_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v065_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        open_world_recheck_path=str(args.open_world_recheck),
        decision_maturity_path=str(args.decision_maturity),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
