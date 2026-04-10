from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_10_0_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_DEPTH_PROBE_OUT_DIR,
    DEFAULT_GOVERNANCE_PACK_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V097_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_10_0_depth_probe import build_v1000_depth_probe
from .agent_modelica_v0_10_0_governance_pack import build_v1000_governance_pack
from .agent_modelica_v0_10_0_handoff_integrity import build_v1000_handoff_integrity


def build_v1000_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    governance_pack_path: str = str(DEFAULT_GOVERNANCE_PACK_OUT_DIR / "summary.json"),
    depth_probe_path: str = str(DEFAULT_DEPTH_PROBE_OUT_DIR / "summary.json"),
    v097_closeout_path: str = str(DEFAULT_V097_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    handoff_path_obj = Path(handoff_integrity_path)
    governance_path_obj = Path(governance_pack_path)
    depth_probe_path_obj = Path(depth_probe_path)

    if not handoff_path_obj.exists():
        build_v1000_handoff_integrity(
            v097_closeout_path=v097_closeout_path,
            out_dir=str(handoff_path_obj.parent),
        )
    handoff = load_json(handoff_integrity_path)
    if handoff.get("handoff_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_10_0_HANDOFF_CANDIDATE_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_10_0_handoff_candidate_inputs_invalid",
                "real_origin_candidate_governance_status": "invalid",
                "needs_additional_real_origin_sources": None,
                "v0_10_1_handoff_mode": "rebuild_v0_10_0_candidate_inputs_first",
            },
            "handoff_integrity": handoff,
        }
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.10.0 Closeout\n\n- version_decision: `v0_10_0_handoff_candidate_inputs_invalid`\n")
        return payload

    if not governance_path_obj.exists():
        build_v1000_governance_pack(out_dir=str(governance_path_obj.parent))
    governance = load_json(governance_pack_path)

    if not depth_probe_path_obj.exists():
        build_v1000_depth_probe(governance_pack_path=governance_pack_path, out_dir=str(depth_probe_path_obj.parent))
    probe = load_json(depth_probe_path)

    governance_status = str(probe.get("real_origin_candidate_governance_status") or "invalid")
    if governance_status == "governance_ready":
        version_decision = "v0_10_0_real_origin_candidate_governance_ready"
        handoff_mode = "freeze_first_real_origin_workflow_substrate"
        status = "PASS"
    elif governance_status == "governance_partial":
        version_decision = "v0_10_0_real_origin_candidate_governance_partial"
        handoff_mode = "expand_real_origin_candidate_pool_before_substrate_freeze"
        status = "PASS"
    else:
        version_decision = "v0_10_0_handoff_candidate_inputs_invalid"
        handoff_mode = "rebuild_v0_10_0_candidate_inputs_first"
        status = "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": version_decision.upper(),
        "conclusion": {
            "version_decision": version_decision,
            "real_origin_candidate_governance_status": governance_status,
            "mainline_real_origin_candidate_count": probe.get("mainline_real_origin_candidate_count"),
            "candidate_depth_by_workflow_family": probe.get("candidate_depth_by_workflow_family"),
            "candidate_depth_by_source_origin_class": probe.get("candidate_depth_by_source_origin_class"),
            "needs_additional_real_origin_sources": probe.get("needs_additional_real_origin_sources"),
            "why_this_is_or_is_not_valid": (
                "Real-origin governance is frozen and the current mainline pool is clean enough to start the phase, but real-origin depth and source diversity remain below the promoted substrate-freeze floor."
                if governance_status == "governance_partial"
                else "Real-origin governance is frozen and the current mainline pool already satisfies the promoted floor for first substrate freeze."
                if governance_status == "governance_ready"
                else "Handoff or real-origin governance inputs are invalid and must be rebuilt before the new phase can proceed."
            ),
            "v0_10_1_handoff_mode": handoff_mode,
        },
        "handoff_integrity": handoff,
        "governance_pack": governance,
        "depth_probe": probe,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.10.0 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- real_origin_candidate_governance_status: `{governance_status}`",
                f"- needs_additional_real_origin_sources: `{probe.get('needs_additional_real_origin_sources')}`",
                f"- v0_10_1_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.10.0 real-origin candidate governance closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--governance-pack", default=str(DEFAULT_GOVERNANCE_PACK_OUT_DIR / "summary.json"))
    parser.add_argument("--depth-probe", default=str(DEFAULT_DEPTH_PROBE_OUT_DIR / "summary.json"))
    parser.add_argument("--v097-closeout", default=str(DEFAULT_V097_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v1000_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        governance_pack_path=str(args.governance_pack),
        depth_probe_path=str(args.depth_probe),
        v097_closeout_path=str(args.v097_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
