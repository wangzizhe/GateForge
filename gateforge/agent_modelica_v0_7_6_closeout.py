from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_7_6_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_LATE_PHASE_SUPPORT_OUT_DIR,
    DEFAULT_V074_CLOSEOUT_PATH,
    DEFAULT_V075_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_7_6_handoff_integrity import build_v076_handoff_integrity
from .agent_modelica_v0_7_6_late_phase_support import build_v076_late_phase_support


def build_v076_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    late_phase_support_path: str = str(DEFAULT_LATE_PHASE_SUPPORT_OUT_DIR / "summary.json"),
    v075_closeout_path: str = str(DEFAULT_V075_CLOSEOUT_PATH),
    v074_closeout_path: str = str(DEFAULT_V074_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)

    if not Path(handoff_integrity_path).exists():
        build_v076_handoff_integrity(
            v075_closeout_path=v075_closeout_path,
            out_dir=str(Path(handoff_integrity_path).parent),
        )
    integrity = load_json(handoff_integrity_path)
    if integrity.get("status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_7_6_HANDOFF_SUBSTRATE_INVALID",
            "conclusion": {
                "version_decision": "v0_7_6_handoff_substrate_invalid",
                "late_phase_support_status": "invalid",
                "single_gap_still_holds": None,
                "gap_magnitude_pct": None,
                "gap_magnitude_small_enough_for_closeout_support": None,
                "bounded_uncovered_still_subcritical": None,
                "new_multi_gap_signal_present": None,
                "new_targeted_expansion_pressure_present": None,
                "v0_7_7_handoff_mode": "repair_late_phase_partial_closeout_inputs_first",
            },
            "handoff_integrity": integrity,
        }
        write_json(out_root / "summary.json", payload)
        write_text(
            out_root / "summary.md",
            "\n".join(
                [
                    "# v0.7.6 Closeout",
                    "",
                    "- version_decision: `v0_7_6_handoff_substrate_invalid`",
                    "- late_phase_support_status: `invalid`",
                    "- v0_7_7_handoff_mode: `repair_late_phase_partial_closeout_inputs_first`",
                ]
            ),
        )
        return payload

    if not Path(late_phase_support_path).exists():
        build_v076_late_phase_support(
            v075_closeout_path=v075_closeout_path,
            v074_closeout_path=v074_closeout_path,
            out_dir=str(Path(late_phase_support_path).parent),
        )
    support = load_json(late_phase_support_path)

    single_gap_still_holds = bool(support.get("single_gap_still_holds"))
    gap_small = bool(support.get("gap_magnitude_small_enough_for_closeout_support"))
    bounded_uncovered_still_subcritical = bool(support.get("bounded_uncovered_still_subcritical"))
    spillover_still_not_blocking = bool(support.get("spillover_still_not_blocking"))
    legacy_mapping_still_strong = bool(support.get("legacy_mapping_still_strong"))
    new_multi_gap_signal_present = bool(support.get("new_multi_gap_signal_present"))
    new_targeted_expansion_pressure_present = bool(
        support.get("new_targeted_expansion_pressure_present")
    )
    support_basis = str(support.get("late_phase_closeout_support_basis") or "unknown")

    is_invalid = (
        (not single_gap_still_holds)
        or new_multi_gap_signal_present
        or new_targeted_expansion_pressure_present
        or support_basis == "unknown"
    )
    phase_closeout_supported = (
        single_gap_still_holds
        and gap_small
        and bounded_uncovered_still_subcritical
        and spillover_still_not_blocking
        and legacy_mapping_still_strong
        and not new_multi_gap_signal_present
        and not new_targeted_expansion_pressure_present
    )
    partial_but_interpretable = (
        (not phase_closeout_supported)
        and single_gap_still_holds
        and bounded_uncovered_still_subcritical
        and not new_multi_gap_signal_present
    )

    if is_invalid:
        status = "invalid"
        version_decision = "v0_7_6_handoff_substrate_invalid"
        handoff_mode = "repair_late_phase_partial_closeout_inputs_first"
        closeout_status = "V0_7_6_HANDOFF_SUBSTRATE_INVALID"
    elif phase_closeout_supported:
        status = "phase_closeout_supported"
        version_decision = "v0_7_6_phase_closeout_supported"
        handoff_mode = "run_v0_7_phase_synthesis"
        closeout_status = "V0_7_6_PHASE_CLOSEOUT_SUPPORTED"
    elif partial_but_interpretable:
        status = "partial_but_interpretable"
        version_decision = "v0_7_6_open_world_readiness_partial_but_interpretable"
        handoff_mode = "one_last_late_phase_reassessment"
        closeout_status = "V0_7_6_OPEN_WORLD_READINESS_PARTIAL_BUT_INTERPRETABLE"
    else:
        status = "invalid"
        version_decision = "v0_7_6_handoff_substrate_invalid"
        handoff_mode = "repair_late_phase_partial_closeout_inputs_first"
        closeout_status = "V0_7_6_HANDOFF_SUBSTRATE_INVALID"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": "PASS" if status != "invalid" else "FAIL",
        "closeout_status": closeout_status,
        "conclusion": {
            "version_decision": version_decision,
            "late_phase_support_status": status,
            "single_gap_still_holds": single_gap_still_holds,
            "gap_magnitude_pct": support.get("gap_magnitude_pct"),
            "gap_magnitude_small_enough_for_closeout_support": gap_small,
            "bounded_uncovered_still_subcritical": bounded_uncovered_still_subcritical,
            "new_multi_gap_signal_present": new_multi_gap_signal_present,
            "new_targeted_expansion_pressure_present": new_targeted_expansion_pressure_present,
            "v0_7_7_handoff_mode": handoff_mode,
        },
        "handoff_integrity": integrity,
        "late_phase_support": support,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.6 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- late_phase_support_status: `{status}`",
                f"- gap_magnitude_pct: `{support.get('gap_magnitude_pct')}`",
                f"- gap_magnitude_small_enough_for_closeout_support: `{gap_small}`",
                f"- single_gap_still_holds: `{single_gap_still_holds}`",
                f"- v0_7_7_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.6 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--late-phase-support", default=str(DEFAULT_LATE_PHASE_SUPPORT_OUT_DIR / "summary.json"))
    parser.add_argument("--v075-closeout", default=str(DEFAULT_V075_CLOSEOUT_PATH))
    parser.add_argument("--v074-closeout", default=str(DEFAULT_V074_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v076_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        late_phase_support_path=str(args.late_phase_support),
        v075_closeout_path=str(args.v075_closeout),
        v074_closeout_path=str(args.v074_closeout),
        out_dir=str(args.out_dir),
    )
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "version_decision": (payload.get("conclusion") or {}).get("version_decision"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
