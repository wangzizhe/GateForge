from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_9_0_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_DEPTH_PROBE_OUT_DIR,
    DEFAULT_GOVERNANCE_PACK_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V080_CLOSEOUT_PATH,
    DEFAULT_V081_CLOSEOUT_PATH,
    DEFAULT_V086_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_9_0_depth_probe import build_v090_depth_probe
from .agent_modelica_v0_9_0_governance_pack import build_v090_governance_pack
from .agent_modelica_v0_9_0_handoff_integrity import build_v090_handoff_integrity


def build_v090_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    governance_pack_path: str = str(DEFAULT_GOVERNANCE_PACK_OUT_DIR / "summary.json"),
    depth_probe_path: str = str(DEFAULT_DEPTH_PROBE_OUT_DIR / "summary.json"),
    v086_closeout_path: str = str(DEFAULT_V086_CLOSEOUT_PATH),
    v080_closeout_path: str = str(DEFAULT_V080_CLOSEOUT_PATH),
    v081_closeout_path: str = str(DEFAULT_V081_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    build_v090_handoff_integrity(
        v086_closeout_path=v086_closeout_path,
        out_dir=str(Path(handoff_integrity_path).parent),
    )
    handoff = load_json(handoff_integrity_path)
    if handoff.get("handoff_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_9_0_HANDOFF_CANDIDATE_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_9_0_handoff_candidate_inputs_invalid",
                "candidate_pool_governance_status": "invalid",
                "needs_additional_real_sources": None,
                "v0_9_1_handoff_mode": "rebuild_v0_9_handoff_and_governance_pack_first",
            },
            "handoff_integrity": handoff,
        }
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.9.0 Closeout\n\n- version_decision: `v0_9_0_handoff_candidate_inputs_invalid`\n")
        return payload

    build_v090_governance_pack(
        v080_closeout_path=v080_closeout_path,
        v081_closeout_path=v081_closeout_path,
        out_dir=str(Path(governance_pack_path).parent),
    )
    governance = load_json(governance_pack_path)

    build_v090_depth_probe(governance_pack_path=governance_pack_path, out_dir=str(Path(depth_probe_path).parent))
    probe = load_json(depth_probe_path)

    governance_status = str(probe.get("candidate_pool_governance_status") or "invalid")
    if governance_status == "ready":
        version_decision = "v0_9_0_candidate_pool_governance_ready"
        handoff_mode = "freeze_first_expanded_authentic_workflow_substrate"
        status = "PASS"
    elif governance_status == "partial":
        version_decision = "v0_9_0_candidate_pool_governance_partial"
        handoff_mode = "expand_real_candidate_pool_before_substrate_freeze"
        status = "PASS"
    else:
        version_decision = "v0_9_0_handoff_candidate_inputs_invalid"
        handoff_mode = "rebuild_v0_9_handoff_and_governance_pack_first"
        status = "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": version_decision.upper(),
        "conclusion": {
            "version_decision": version_decision,
            "candidate_pool_governance_status": governance_status,
            "candidate_pool_total_count": probe.get("candidate_pool_total_count"),
            "candidate_depth_by_priority_barrier": probe.get("candidate_depth_by_priority_barrier"),
            "needs_additional_real_sources": probe.get("needs_additional_real_sources"),
            "why_this_is_or_is_not_valid": (
                "Governance pack is frozen and the current real pool is authentic, but one or more priority barriers remain below the working minimum depth."
                if governance_status == "partial"
                else "Governance pack and current real pool both satisfy the planned barrier-depth floor."
                if governance_status == "ready"
                else "Handoff or governance-pack inputs are invalid and must be rebuilt before v0.9.x expansion."
            ),
            "v0_9_1_handoff_mode": handoff_mode,
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
                "# v0.9.0 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- candidate_pool_governance_status: `{governance_status}`",
                f"- needs_additional_real_sources: `{probe.get('needs_additional_real_sources')}`",
                f"- v0_9_1_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.0 candidate-pool governance closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--governance-pack", default=str(DEFAULT_GOVERNANCE_PACK_OUT_DIR / "summary.json"))
    parser.add_argument("--depth-probe", default=str(DEFAULT_DEPTH_PROBE_OUT_DIR / "summary.json"))
    parser.add_argument("--v086-closeout", default=str(DEFAULT_V086_CLOSEOUT_PATH))
    parser.add_argument("--v080-closeout", default=str(DEFAULT_V080_CLOSEOUT_PATH))
    parser.add_argument("--v081-closeout", default=str(DEFAULT_V081_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v090_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        governance_pack_path=str(args.governance_pack),
        depth_probe_path=str(args.depth_probe),
        v086_closeout_path=str(args.v086_closeout),
        v080_closeout_path=str(args.v080_closeout),
        v081_closeout_path=str(args.v081_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
