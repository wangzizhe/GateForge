from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_6_6_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_COMPLEX_GAP_RECHECK_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_TERMINAL_DECISION_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_6_6_complex_gap_recheck import build_v066_complex_gap_recheck
from .agent_modelica_v0_6_6_handoff_integrity import build_v066_handoff_integrity
from .agent_modelica_v0_6_6_terminal_decision import build_v066_terminal_decision


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v066_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    complex_gap_recheck_path: str = str(DEFAULT_COMPLEX_GAP_RECHECK_OUT_DIR / "summary.json"),
    terminal_decision_path: str = str(DEFAULT_TERMINAL_DECISION_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v066_handoff_integrity(out_dir=str(Path(handoff_integrity_path).parent))

    integrity = load_json(handoff_integrity_path)
    if integrity.get("status") != "PASS":
        version_decision = "v0_6_6_handoff_substrate_invalid"
        handoff_mode = "repair_late_phase_decision_inputs_first"
        payload = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_6_6_HANDOFF_SUBSTRATE_INVALID",
            "conclusion": {
                "version_decision": version_decision,
                "decision_terminal_status": "invalid",
                "open_world_candidate_supported_after_gap_recheck": False,
                "open_world_margin_vs_floor_pct_rechecked": None,
                "remaining_gap_still_single": None,
                "phase_closeout_supported": False,
                "v0_6_7_handoff_mode": handoff_mode,
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
                    "# v0.6.6 Closeout",
                    "",
                    f"- version_decision: `{version_decision}`",
                    "- decision_terminal_status: `invalid`",
                    f"- v0_6_7_handoff_mode: `{handoff_mode}`",
                ]
            ),
        )
        return payload

    if not Path(complex_gap_recheck_path).exists():
        build_v066_complex_gap_recheck(
            handoff_integrity_path=handoff_integrity_path,
            out_dir=str(Path(complex_gap_recheck_path).parent),
        )
    if not Path(terminal_decision_path).exists():
        build_v066_terminal_decision(
            handoff_integrity_path=handoff_integrity_path,
            complex_gap_recheck_path=complex_gap_recheck_path,
            out_dir=str(Path(terminal_decision_path).parent),
        )

    recheck = load_json(complex_gap_recheck_path)
    terminal = load_json(terminal_decision_path)
    status = str(terminal.get("decision_terminal_status") or "invalid")

    if status == "invalid":
        version_decision = "v0_6_6_handoff_substrate_invalid"
        handoff_mode = "repair_late_phase_decision_inputs_first"
    elif status == "ready":
        version_decision = "v0_6_6_phase_decision_ready"
        handoff_mode = "run_late_v0_6_phase_decision"
    elif status == "phase_closeout_supported":
        version_decision = "v0_6_6_phase_closeout_supported"
        handoff_mode = "run_v0_6_phase_synthesis"
    else:
        version_decision = "v0_6_6_phase_decision_partial"
        handoff_mode = "decide_if_one_more_late_phase_version_is_worth_it"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if version_decision != "v0_6_6_handoff_substrate_invalid" else "FAIL",
        "closeout_status": (
            "V0_6_6_PHASE_DECISION_READY"
            if version_decision == "v0_6_6_phase_decision_ready"
            else (
                "V0_6_6_PHASE_CLOSEOUT_SUPPORTED"
                if version_decision == "v0_6_6_phase_closeout_supported"
                else (
                    "V0_6_6_PHASE_DECISION_PARTIAL"
                    if version_decision == "v0_6_6_phase_decision_partial"
                    else "V0_6_6_HANDOFF_SUBSTRATE_INVALID"
                )
            )
        ),
        "conclusion": {
            "version_decision": version_decision,
            "decision_terminal_status": status,
            "open_world_candidate_supported_after_gap_recheck": recheck.get("open_world_candidate_supported_after_gap_recheck"),
            "open_world_margin_vs_floor_pct_rechecked": recheck.get("open_world_margin_vs_floor_pct_rechecked"),
            "remaining_gap_still_single": recheck.get("remaining_gap_still_single"),
            "phase_closeout_supported": recheck.get("phase_closeout_supported"),
            "v0_6_7_handoff_mode": handoff_mode,
            "do_not_reopen_v0_5_boundary_pressure_by_default": True,
        },
        "handoff_integrity": integrity,
        "complex_gap_recheck": recheck,
        "terminal_decision": terminal,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.6.6 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- decision_terminal_status: `{status}`",
                f"- open_world_margin_vs_floor_pct_rechecked: `{recheck.get('open_world_margin_vs_floor_pct_rechecked')}`",
                f"- phase_closeout_supported: `{recheck.get('phase_closeout_supported')}`",
                f"- v0_6_7_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.6.6 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--complex-gap-recheck", default=str(DEFAULT_COMPLEX_GAP_RECHECK_OUT_DIR / "summary.json"))
    parser.add_argument("--terminal-decision", default=str(DEFAULT_TERMINAL_DECISION_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v066_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        complex_gap_recheck_path=str(args.complex_gap_recheck),
        terminal_decision_path=str(args.terminal_decision),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
