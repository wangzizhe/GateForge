from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_7_2_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_LIVE_RUN_OUT_DIR,
    DEFAULT_PROFILE_EXTENSION_OUT_DIR,
    DEFAULT_PROFILE_STABILITY_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_7_2_handoff_integrity import build_v072_handoff_integrity
from .agent_modelica_v0_7_2_live_run import build_v072_live_run
from .agent_modelica_v0_7_2_profile_extension import build_v072_profile_extension
from .agent_modelica_v0_7_2_profile_stability import build_v072_profile_stability


def build_v072_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    profile_extension_path: str = str(DEFAULT_PROFILE_EXTENSION_OUT_DIR / "summary.json"),
    live_run_path: str = str(DEFAULT_LIVE_RUN_OUT_DIR / "summary.json"),
    profile_stability_path: str = str(DEFAULT_PROFILE_STABILITY_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v072_handoff_integrity(out_dir=str(Path(handoff_integrity_path).parent))
    integrity = load_json(handoff_integrity_path)
    if integrity.get("status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_7_2_HANDOFF_SUBSTRATE_INVALID",
            "conclusion": {
                "version_decision": "v0_7_2_handoff_substrate_invalid",
                "profile_stability_status": "invalid",
                "slice_extension_mode": None,
                "stable_coverage_share_pct_after_extension": None,
                "spillover_share_pct_after_extension": None,
                "legacy_bucket_mapping_rate_pct_after_extension": None,
                "dominant_pressure_source_after_extension": None,
                "v0_7_3_handoff_mode": "repair_open_world_adjacent_profile_substrate_first",
            },
            "handoff_integrity": integrity,
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.7.2 Closeout\n")
        return payload

    if not Path(profile_extension_path).exists():
        build_v072_profile_extension(out_dir=str(Path(profile_extension_path).parent))
    if not Path(live_run_path).exists():
        build_v072_live_run(
            profile_extension_path=profile_extension_path,
            out_dir=str(Path(live_run_path).parent),
        )
    if not Path(profile_stability_path).exists():
        build_v072_profile_stability(
            live_run_path=live_run_path,
            out_dir=str(Path(profile_stability_path).parent),
        )

    extension = load_json(profile_extension_path)
    stability = load_json(profile_stability_path)
    status = str(stability.get("profile_stability_status") or "invalid")
    if status == "stable":
        version_decision = "v0_7_2_readiness_profile_stable"
        handoff = "prepare_mid_phase_readiness_adjudication_inputs"
    elif status == "partial":
        version_decision = "v0_7_2_readiness_profile_partial"
        handoff = "continue_readiness_profile_stabilization_under_same_logic"
    else:
        version_decision = "v0_7_2_handoff_substrate_invalid"
        handoff = "repair_open_world_adjacent_profile_substrate_first"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": "PASS" if status in {"stable", "partial"} else "FAIL",
        "closeout_status": {
            "stable": "V0_7_2_READINESS_PROFILE_STABLE",
            "partial": "V0_7_2_READINESS_PROFILE_PARTIAL",
            "invalid": "V0_7_2_HANDOFF_SUBSTRATE_INVALID",
        }[status],
        "conclusion": {
            "version_decision": version_decision,
            "profile_stability_status": status,
            "slice_extension_mode": extension.get("slice_extension_mode"),
            "stable_coverage_share_pct_after_extension": stability.get("stable_coverage_share_pct_after_extension"),
            "spillover_share_pct_after_extension": stability.get("spillover_share_pct_after_extension"),
            "legacy_bucket_mapping_rate_pct_after_extension": stability.get("legacy_bucket_mapping_rate_pct_after_extension"),
            "dominant_pressure_source_after_extension": stability.get("dominant_pressure_source_after_extension"),
            "v0_7_3_handoff_mode": handoff,
        },
        "handoff_integrity": integrity,
        "profile_extension": extension,
        "profile_stability": stability,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.2 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- profile_stability_status: `{status}`",
                f"- slice_extension_mode: `{extension.get('slice_extension_mode')}`",
                f"- stable_coverage_share_pct_after_extension: `{stability.get('stable_coverage_share_pct_after_extension')}`",
                f"- spillover_share_pct_after_extension: `{stability.get('spillover_share_pct_after_extension')}`",
                f"- v0_7_3_handoff_mode: `{handoff}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.2 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--profile-extension", default=str(DEFAULT_PROFILE_EXTENSION_OUT_DIR / "summary.json"))
    parser.add_argument("--live-run", default=str(DEFAULT_LIVE_RUN_OUT_DIR / "summary.json"))
    parser.add_argument("--profile-stability", default=str(DEFAULT_PROFILE_STABILITY_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v072_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        profile_extension_path=str(args.profile_extension),
        live_run_path=str(args.live_run),
        profile_stability_path=str(args.profile_stability),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
