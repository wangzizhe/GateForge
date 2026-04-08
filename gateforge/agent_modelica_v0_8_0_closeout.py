from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_8_0_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_PILOT_PROFILE_OUT_DIR,
    DEFAULT_SUBSTRATE_ADMISSION_OUT_DIR,
    DEFAULT_V077_CLOSEOUT_PATH,
    DEFAULT_WORKFLOW_SUBSTRATE_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_8_0_handoff_integrity import build_v080_handoff_integrity
from .agent_modelica_v0_8_0_pilot_workflow_profile import build_v080_pilot_workflow_profile
from .agent_modelica_v0_8_0_workflow_proximal_substrate import (
    build_v080_workflow_proximal_substrate,
)
from .agent_modelica_v0_8_0_workflow_substrate_admission import (
    build_v080_workflow_substrate_admission,
)


def build_v080_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    substrate_path: str = str(DEFAULT_WORKFLOW_SUBSTRATE_OUT_DIR / "summary.json"),
    pilot_profile_path: str = str(DEFAULT_PILOT_PROFILE_OUT_DIR / "summary.json"),
    admission_path: str = str(DEFAULT_SUBSTRATE_ADMISSION_OUT_DIR / "summary.json"),
    v077_closeout_path: str = str(DEFAULT_V077_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v080_handoff_integrity(
            v077_closeout_path=v077_closeout_path,
            out_dir=str(Path(handoff_integrity_path).parent),
        )
    integrity = load_json(handoff_integrity_path)
    if integrity.get("status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_8_0_HANDOFF_SUBSTRATE_INVALID",
            "conclusion": {
                "version_decision": "v0_8_0_handoff_substrate_invalid",
                "workflow_substrate_admission_status": "invalid",
                "goal_level_success_definition_frozen": False,
                "legacy_bucket_mapping_rate_pct": None,
                "spillover_share_pct": None,
                "unclassified_pending_taxonomy_count": None,
                "why_not_error_distribution_equivalent": None,
                "v0_8_1_handoff_mode": "rebuild_workflow_proximal_substrate_first",
            },
            "handoff_integrity": integrity,
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", payload)
        write_text(
            out_root / "summary.md",
            "# v0.8.0 Closeout\n\n- version_decision: `v0_8_0_handoff_substrate_invalid`\n",
        )
        return payload

    if not Path(substrate_path).exists():
        build_v080_workflow_proximal_substrate(out_dir=str(Path(substrate_path).parent))
    if not Path(pilot_profile_path).exists():
        build_v080_pilot_workflow_profile(
            substrate_path=substrate_path,
            out_dir=str(Path(pilot_profile_path).parent),
        )
    if not Path(admission_path).exists():
        build_v080_workflow_substrate_admission(
            substrate_path=substrate_path,
            pilot_profile_path=pilot_profile_path,
            out_dir=str(Path(admission_path).parent),
        )

    substrate = load_json(substrate_path)
    pilot = load_json(pilot_profile_path)
    admission = load_json(admission_path)

    status = str(admission.get("workflow_substrate_admission_status") or "invalid")
    if status == "ready":
        version_decision = "v0_8_0_workflow_proximal_substrate_ready"
        handoff = "characterize_workflow_readiness_profile_on_frozen_substrate"
    elif status == "partial":
        version_decision = "v0_8_0_workflow_proximal_substrate_partial"
        handoff = "repair_workflow_proximal_substrate_gaps_first"
    else:
        version_decision = "v0_8_0_workflow_proximal_substrate_invalid"
        handoff = "rebuild_workflow_proximal_substrate_first"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": "PASS" if status in {"ready", "partial"} else "FAIL",
        "closeout_status": {
            "ready": "V0_8_0_WORKFLOW_PROXIMAL_SUBSTRATE_READY",
            "partial": "V0_8_0_WORKFLOW_PROXIMAL_SUBSTRATE_PARTIAL",
            "invalid": "V0_8_0_WORKFLOW_PROXIMAL_SUBSTRATE_INVALID",
        }[status],
        "conclusion": {
            "version_decision": version_decision,
            "workflow_substrate_admission_status": status,
            "goal_level_success_definition_frozen": bool(
                admission.get("goal_level_success_definition_frozen")
            ),
            "legacy_bucket_mapping_rate_pct": pilot.get("legacy_bucket_mapping_rate_pct"),
            "spillover_share_pct": pilot.get("spillover_share_pct"),
            "unclassified_pending_taxonomy_count": pilot.get("unclassified_pending_taxonomy_count"),
            "why_not_error_distribution_equivalent": pilot.get("why_not_error_distribution_equivalent"),
            "v0_8_1_handoff_mode": handoff,
        },
        "handoff_integrity": integrity,
        "workflow_proximal_substrate": substrate,
        "pilot_workflow_profile": pilot,
        "workflow_substrate_admission": admission,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.8.0 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- workflow_substrate_admission_status: `{status}`",
                f"- workflow_proximity_audit_pass_rate_pct: `{substrate.get('workflow_proximity_audit_pass_rate_pct')}`",
                f"- workflow_resolution_rate_pct: `{pilot.get('workflow_resolution_rate_pct')}`",
                f"- goal_alignment_rate_pct: `{pilot.get('goal_alignment_rate_pct')}`",
                f"- v0_8_1_handoff_mode: `{handoff}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.8.0 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--substrate-path", default=str(DEFAULT_WORKFLOW_SUBSTRATE_OUT_DIR / "summary.json"))
    parser.add_argument("--pilot-profile", default=str(DEFAULT_PILOT_PROFILE_OUT_DIR / "summary.json"))
    parser.add_argument("--admission-path", default=str(DEFAULT_SUBSTRATE_ADMISSION_OUT_DIR / "summary.json"))
    parser.add_argument("--v077-closeout", default=str(DEFAULT_V077_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v080_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        substrate_path=str(args.substrate_path),
        pilot_profile_path=str(args.pilot_profile),
        admission_path=str(args.admission_path),
        v077_closeout_path=str(args.v077_closeout),
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
