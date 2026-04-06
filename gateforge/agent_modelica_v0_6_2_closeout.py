from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_6_2_authority_slice import build_v062_authority_slice
from .agent_modelica_v0_6_2_common import (
    DEFAULT_AUTHORITY_SLICE_OUT_DIR,
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_LIVE_RUN_OUT_DIR,
    DEFAULT_PROFILE_STABILITY_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_6_2_handoff_integrity import build_v062_handoff_integrity
from .agent_modelica_v0_6_2_live_run import build_v062_live_run
from .agent_modelica_v0_6_2_profile_stability import build_v062_profile_stability


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v062_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    authority_slice_path: str = str(DEFAULT_AUTHORITY_SLICE_OUT_DIR / "summary.json"),
    live_run_path: str = str(DEFAULT_LIVE_RUN_OUT_DIR / "summary.json"),
    profile_stability_path: str = str(DEFAULT_PROFILE_STABILITY_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v062_handoff_integrity(out_dir=str(Path(handoff_integrity_path).parent))
    if not Path(authority_slice_path).exists():
        build_v062_authority_slice(
            handoff_integrity_path=handoff_integrity_path,
            out_dir=str(Path(authority_slice_path).parent),
        )
    if not Path(live_run_path).exists():
        build_v062_live_run(
            authority_slice_path=authority_slice_path,
            out_dir=str(Path(live_run_path).parent),
        )
    if not Path(profile_stability_path).exists():
        build_v062_profile_stability(
            authority_slice_path=authority_slice_path,
            live_run_path=live_run_path,
            out_dir=str(Path(profile_stability_path).parent),
        )

    integrity = load_json(handoff_integrity_path)
    authority_slice = load_json(authority_slice_path)
    live_run = load_json(live_run_path)
    stability = load_json(profile_stability_path)

    if integrity.get("status") != "PASS":
        version_decision = "v0_6_2_handoff_substrate_invalid"
        handoff_mode = "repair_authority_profile_substrate_first"
        profile_status = "invalid"
    else:
        profile_status = str(stability.get("profile_stability_status") or "invalid")
        if profile_status == "stable":
            version_decision = "v0_6_2_authority_profile_stable"
            handoff_mode = "prepare_phase_level_authority_decision_inputs"
        elif profile_status == "partial":
            version_decision = "v0_6_2_authority_profile_partial"
            handoff_mode = "continue_authority_profile_characterization_with_gap_focus"
        else:
            version_decision = "v0_6_2_handoff_substrate_invalid"
            handoff_mode = "repair_authority_profile_substrate_first"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if version_decision != "v0_6_2_handoff_substrate_invalid" else "FAIL",
        "closeout_status": (
            "V0_6_2_AUTHORITY_PROFILE_STABLE"
            if version_decision == "v0_6_2_authority_profile_stable"
            else (
                "V0_6_2_AUTHORITY_PROFILE_PARTIAL"
                if version_decision == "v0_6_2_authority_profile_partial"
                else "V0_6_2_HANDOFF_SUBSTRATE_INVALID"
            )
        ),
        "conclusion": {
            "version_decision": version_decision,
            "profile_stability_status": profile_status,
            "primary_profile_gap": stability.get("primary_profile_gap"),
            "legacy_taxonomy_still_sufficient": stability.get("legacy_taxonomy_still_sufficient"),
            "fluid_network_extension_status_under_representative_pressure": stability.get("fluid_network_extension_status_under_representative_pressure"),
            "v0_6_3_handoff_mode": handoff_mode,
            "do_not_reopen_v0_5_boundary_pressure_by_default": True,
        },
        "handoff_integrity": integrity,
        "authority_slice": {
            "slice_extension_mode": authority_slice.get("slice_extension_mode"),
            "case_count": authority_slice.get("case_count"),
            "fluid_network_extension_observable_case_count": authority_slice.get("fluid_network_extension_observable_case_count"),
        },
        "live_run": {
            "live_run_case_count": live_run.get("live_run_case_count"),
            "fluid_network_extension_status_under_representative_pressure": live_run.get("fluid_network_extension_status_under_representative_pressure"),
        },
        "profile_stability": stability,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.6.2 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- profile_stability_status: `{profile_status}`",
                f"- fluid_network_extension_status_under_representative_pressure: `{stability.get('fluid_network_extension_status_under_representative_pressure')}`",
                f"- v0_6_3_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.6.2 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--authority-slice", default=str(DEFAULT_AUTHORITY_SLICE_OUT_DIR / "summary.json"))
    parser.add_argument("--live-run", default=str(DEFAULT_LIVE_RUN_OUT_DIR / "summary.json"))
    parser.add_argument("--profile-stability", default=str(DEFAULT_PROFILE_STABILITY_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v062_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        authority_slice_path=str(args.authority_slice),
        live_run_path=str(args.live_run),
        profile_stability_path=str(args.profile_stability),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
