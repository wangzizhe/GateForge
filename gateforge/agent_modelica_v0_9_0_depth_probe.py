from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_9_0_candidate_validator import evaluate_candidate_rows
from .agent_modelica_v0_9_0_common import (
    DEFAULT_DEPTH_PROBE_OUT_DIR,
    DEFAULT_GOVERNANCE_PACK_OUT_DIR,
    DEGRADED_MINIMUM_PER_PRIORITY_BARRIER,
    PRIORITY_BARRIERS,
    SCHEMA_PREFIX,
    WORKING_MINIMUM_PER_PRIORITY_BARRIER,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_9_0_governance_pack import build_v090_governance_pack


def build_v090_depth_probe(
    *,
    governance_pack_path: str = str(DEFAULT_GOVERNANCE_PACK_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_DEPTH_PROBE_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    if not Path(governance_pack_path).exists():
        build_v090_governance_pack(out_dir=str(Path(governance_pack_path).parent))
    governance = load_json(governance_pack_path)
    candidate_rows = governance.get("baseline_candidate_rows") if isinstance(governance.get("baseline_candidate_rows"), list) else []
    evaluations = evaluate_candidate_rows(candidate_rows)

    admitted_rows = [row for row in evaluations if row.get("admitted")]
    rejected_rows = [row for row in evaluations if not row.get("admitted")]
    depth_by_barrier: dict[str, int] = {barrier: 0 for barrier in PRIORITY_BARRIERS}
    for row in admitted_rows:
        barrier = str(row.get("target_barrier_family") or "")
        if barrier in depth_by_barrier:
            depth_by_barrier[barrier] += 1

    sufficiency_by_barrier = {}
    for barrier, count in depth_by_barrier.items():
        sufficiency_by_barrier[barrier] = {
            "candidate_count": count,
            "promoted_floor_met": count >= WORKING_MINIMUM_PER_PRIORITY_BARRIER,
            "degraded_floor_met": count >= DEGRADED_MINIMUM_PER_PRIORITY_BARRIER,
            "hard_invalid_zero_count": count == 0,
        }

    zero_count_barriers = [barrier for barrier, count in depth_by_barrier.items() if count == 0]
    ready = all(count >= WORKING_MINIMUM_PER_PRIORITY_BARRIER for count in depth_by_barrier.values())
    degraded_floor_fully_met = all(count >= DEGRADED_MINIMUM_PER_PRIORITY_BARRIER for count in depth_by_barrier.values())
    partial_route_usable = all(count >= 1 for count in depth_by_barrier.values())
    if zero_count_barriers:
        governance_status = "invalid"
    elif ready:
        governance_status = "ready"
    elif partial_route_usable:
        governance_status = "partial"
    else:
        governance_status = "invalid"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_depth_probe",
        "generated_at_utc": now_utc(),
        "status": "PASS" if governance_status in {"ready", "partial"} else "FAIL",
        "candidate_pool_total_count": len(candidate_rows),
        "admitted_candidate_count": len(admitted_rows),
        "rejected_candidate_count": len(rejected_rows),
        "candidate_depth_by_priority_barrier": depth_by_barrier,
        "candidate_depth_sufficiency_by_priority_barrier": sufficiency_by_barrier,
        "needs_additional_real_sources": governance_status != "ready",
        "candidate_pool_governance_status": governance_status,
        "degraded_floor_fully_met": degraded_floor_fully_met,
        "working_minimum_per_priority_barrier": WORKING_MINIMUM_PER_PRIORITY_BARRIER,
        "degraded_minimum_per_priority_barrier": DEGRADED_MINIMUM_PER_PRIORITY_BARRIER,
        "projected_later_substrate_size_range": "20-30",
        "priority_barriers_below_working_minimum": [
            barrier for barrier, count in depth_by_barrier.items() if count < WORKING_MINIMUM_PER_PRIORITY_BARRIER
        ],
        "zero_count_priority_barriers": zero_count_barriers,
        "candidate_row_evaluations": evaluations,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.0 Depth Probe",
                "",
                f"- candidate_pool_governance_status: `{governance_status}`",
                f"- candidate_pool_total_count: `{len(candidate_rows)}`",
                f"- candidate_depth_by_priority_barrier: `{depth_by_barrier}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.0 candidate-pool depth probe artifact.")
    parser.add_argument("--governance-pack", default=str(DEFAULT_GOVERNANCE_PACK_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_DEPTH_PROBE_OUT_DIR))
    args = parser.parse_args()
    payload = build_v090_depth_probe(governance_pack_path=str(args.governance_pack), out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "candidate_pool_governance_status": payload.get("candidate_pool_governance_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
