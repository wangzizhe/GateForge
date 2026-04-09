from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_9_1_candidate_source_admission import build_v091_candidate_source_admission
from .agent_modelica_v0_9_1_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_POOL_DELTA_OUT_DIR,
    DEFAULT_SOURCE_ADMISSION_OUT_DIR,
    DEFAULT_V090_CLOSEOUT_PATH,
    DEFAULT_V090_GOVERNANCE_PACK_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_9_1_handoff_integrity import build_v091_handoff_integrity
from .agent_modelica_v0_9_1_pool_delta_build import build_v091_pool_delta


def build_v091_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    source_admission_path: str = str(DEFAULT_SOURCE_ADMISSION_OUT_DIR / "summary.json"),
    pool_delta_path: str = str(DEFAULT_POOL_DELTA_OUT_DIR / "summary.json"),
    v090_closeout_path: str = str(DEFAULT_V090_CLOSEOUT_PATH),
    v090_governance_pack_path: str = str(DEFAULT_V090_GOVERNANCE_PACK_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    build_v091_handoff_integrity(v090_closeout_path=v090_closeout_path, out_dir=str(Path(handoff_integrity_path).parent))
    handoff = load_json(handoff_integrity_path)
    if handoff.get("handoff_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_9_1_SOURCE_EXPANSION_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_9_1_source_expansion_inputs_invalid",
                "candidate_source_expansion_status": "invalid",
                "v0_9_2_handoff_mode": "rebuild_v0_9_1_source_expansion_inputs_first",
            },
            "handoff_integrity": handoff,
        }
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.9.1 Closeout\n\n- version_decision: `v0_9_1_source_expansion_inputs_invalid`\n")
        return payload

    if not Path(source_admission_path).exists():
        build_v091_candidate_source_admission(out_dir=str(Path(source_admission_path).parent))
    source_admission = load_json(source_admission_path)
    build_v091_pool_delta(
        v090_governance_pack_path=v090_governance_pack_path,
        source_admission_path=source_admission_path,
        out_dir=str(Path(pool_delta_path).parent),
    )
    pool_delta = load_json(pool_delta_path)

    admitted_source_count = int(pool_delta.get("admitted_source_count") or 0)
    pool_count = int(pool_delta.get("post_expansion_candidate_pool_count") or 0)
    depth = pool_delta.get("candidate_depth_by_priority_barrier") if isinstance(pool_delta.get("candidate_depth_by_priority_barrier"), dict) else {}
    meaningful_growth_source_present = bool(pool_delta.get("meaningful_growth_source_present"))
    no_zero_barrier = all(int(depth.get(key) or 0) > 0 for key in depth)
    every_barrier_at_least_five = all(int(depth.get(key) or 0) >= 5 for key in depth)

    if admitted_source_count >= 1 and meaningful_growth_source_present and pool_count > 10 and every_barrier_at_least_five:
        version_decision = "v0_9_1_real_candidate_source_expansion_ready"
        expansion_status = "ready"
        handoff_mode = "freeze_first_expanded_authentic_workflow_substrate"
        status = "PASS"
    elif admitted_source_count >= 1 and meaningful_growth_source_present and pool_count > 10 and no_zero_barrier:
        version_decision = "v0_9_1_real_candidate_source_expansion_partial"
        expansion_status = "partial"
        handoff_mode = "continue_expanding_real_candidate_sources"
        status = "PASS"
    else:
        version_decision = "v0_9_1_source_expansion_inputs_invalid"
        expansion_status = "invalid"
        handoff_mode = "rebuild_v0_9_1_source_expansion_inputs_first"
        status = "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": version_decision.upper(),
        "conclusion": {
            "version_decision": version_decision,
            "candidate_source_expansion_status": expansion_status,
            "admitted_source_count": admitted_source_count,
            "post_expansion_candidate_pool_count": pool_count,
            "candidate_depth_by_priority_barrier": depth,
            "candidate_depth_delta_by_priority_barrier": pool_delta.get("candidate_depth_delta_by_priority_barrier"),
            "meaningful_growth_source_present": meaningful_growth_source_present,
            "v0_9_2_handoff_mode": handoff_mode,
        },
        "handoff_integrity": handoff,
        "source_admission": source_admission,
        "pool_delta": pool_delta,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.1 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- admitted_source_count: `{admitted_source_count}`",
                f"- post_expansion_candidate_pool_count: `{pool_count}`",
                f"- v0_9_2_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.1 source expansion closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--source-admission", default=str(DEFAULT_SOURCE_ADMISSION_OUT_DIR / "summary.json"))
    parser.add_argument("--pool-delta", default=str(DEFAULT_POOL_DELTA_OUT_DIR / "summary.json"))
    parser.add_argument("--v090-closeout", default=str(DEFAULT_V090_CLOSEOUT_PATH))
    parser.add_argument("--v090-governance-pack", default=str(DEFAULT_V090_GOVERNANCE_PACK_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v091_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        source_admission_path=str(args.source_admission),
        pool_delta_path=str(args.pool_delta),
        v090_closeout_path=str(args.v090_closeout),
        v090_governance_pack_path=str(args.v090_governance_pack),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
