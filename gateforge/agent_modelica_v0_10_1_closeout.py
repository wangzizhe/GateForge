from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_10_1_candidate_source_admission import build_v101_candidate_source_admission
from .agent_modelica_v0_10_1_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_POOL_DELTA_OUT_DIR,
    DEFAULT_SOURCE_ADMISSION_OUT_DIR,
    DEFAULT_V1000_CLOSEOUT_PATH,
    DEFAULT_V1000_GOVERNANCE_PACK_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_10_1_handoff_integrity import build_v101_handoff_integrity
from .agent_modelica_v0_10_1_pool_delta_and_diversity_report import build_v101_pool_delta_and_diversity_report


def build_v101_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    source_admission_path: str = str(DEFAULT_SOURCE_ADMISSION_OUT_DIR / "summary.json"),
    pool_delta_path: str = str(DEFAULT_POOL_DELTA_OUT_DIR / "summary.json"),
    v1000_closeout_path: str = str(DEFAULT_V1000_CLOSEOUT_PATH),
    v1000_governance_pack_path: str = str(DEFAULT_V1000_GOVERNANCE_PACK_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    handoff_path_obj = Path(handoff_integrity_path)
    source_admission_path_obj = Path(source_admission_path)
    pool_delta_path_obj = Path(pool_delta_path)
    default_handoff_path = DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"
    default_source_admission_path = DEFAULT_SOURCE_ADMISSION_OUT_DIR / "summary.json"
    default_pool_delta_path = DEFAULT_POOL_DELTA_OUT_DIR / "summary.json"

    if not handoff_path_obj.exists() or handoff_path_obj == default_handoff_path:
        build_v101_handoff_integrity(
            v1000_closeout_path=v1000_closeout_path,
            out_dir=str(handoff_path_obj.parent),
        )
    handoff = load_json(handoff_integrity_path)
    if handoff.get("handoff_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_10_1_SOURCE_EXPANSION_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_10_1_source_expansion_inputs_invalid",
                "real_origin_source_expansion_status": "invalid",
                "v0_10_2_handoff_mode": "rebuild_v0_10_1_source_expansion_inputs_first",
            },
            "handoff_integrity": handoff,
        }
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.10.1 Closeout\n\n- version_decision: `v0_10_1_source_expansion_inputs_invalid`\n")
        return payload

    if not source_admission_path_obj.exists() or source_admission_path_obj == default_source_admission_path:
        build_v101_candidate_source_admission(out_dir=str(source_admission_path_obj.parent))
    source_admission = load_json(source_admission_path)

    if not pool_delta_path_obj.exists() or pool_delta_path_obj == default_pool_delta_path:
        build_v101_pool_delta_and_diversity_report(
            v1000_closeout_path=v1000_closeout_path,
            v1000_governance_pack_path=v1000_governance_pack_path,
            source_admission_path=source_admission_path,
            out_dir=str(pool_delta_path_obj.parent),
        )
    pool_delta = load_json(pool_delta_path)

    expansion_status = str(pool_delta.get("real_origin_source_expansion_status") or "invalid")
    if expansion_status == "expansion_ready":
        version_decision = "v0_10_1_real_origin_source_expansion_ready"
        handoff_mode = "freeze_first_real_origin_workflow_substrate"
        status = "PASS"
    elif expansion_status == "expansion_partial":
        version_decision = "v0_10_1_real_origin_source_expansion_partial"
        handoff_mode = "continue_expanding_real_origin_candidate_pool"
        status = "PASS"
    else:
        version_decision = "v0_10_1_source_expansion_inputs_invalid"
        handoff_mode = "rebuild_v0_10_1_source_expansion_inputs_first"
        status = "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": version_decision.upper(),
        "conclusion": {
            "version_decision": version_decision,
            "real_origin_source_expansion_status": expansion_status,
            "post_expansion_mainline_real_origin_candidate_count": pool_delta.get(
                "post_expansion_mainline_real_origin_candidate_count"
            ),
            "candidate_depth_by_workflow_family": pool_delta.get("candidate_depth_by_workflow_family"),
            "candidate_depth_by_source_origin_class": pool_delta.get("candidate_depth_by_source_origin_class"),
            "max_single_source_share_pct": pool_delta.get("max_single_source_share_pct"),
            "needs_additional_real_origin_sources": pool_delta.get("needs_additional_real_origin_sources"),
            "why_this_is_or_is_not_valid": (
                "The frozen governance pack now admits additional real-origin sources and lowers single-source concentration, but the pool still remains below the promoted substrate-freeze floor."
                if expansion_status == "expansion_partial"
                else "The frozen governance pack now supports a deep enough and diverse enough mainline real-origin pool for first substrate freeze."
                if expansion_status == "expansion_ready"
                else "Handoff or source-expansion inputs are invalid and must be rebuilt before real-origin substrate freeze can proceed."
            ),
            "v0_10_2_handoff_mode": handoff_mode,
        },
        "handoff_integrity": handoff,
        "source_admission": source_admission,
        "pool_delta_and_diversity_report": pool_delta,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.10.1 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- post_expansion_mainline_real_origin_candidate_count: `{pool_delta.get('post_expansion_mainline_real_origin_candidate_count')}`",
                f"- max_single_source_share_pct: `{pool_delta.get('max_single_source_share_pct')}`",
                f"- v0_10_2_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.10.1 source expansion closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--source-admission", default=str(DEFAULT_SOURCE_ADMISSION_OUT_DIR / "summary.json"))
    parser.add_argument("--pool-delta", default=str(DEFAULT_POOL_DELTA_OUT_DIR / "summary.json"))
    parser.add_argument("--v1000-closeout", default=str(DEFAULT_V1000_CLOSEOUT_PATH))
    parser.add_argument("--v1000-governance-pack", default=str(DEFAULT_V1000_GOVERNANCE_PACK_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v101_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        source_admission_path=str(args.source_admission),
        pool_delta_path=str(args.pool_delta),
        v1000_closeout_path=str(args.v1000_closeout),
        v1000_governance_pack_path=str(args.v1000_governance_pack),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
