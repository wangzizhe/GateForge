from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_9_0_candidate_validator import evaluate_candidate_rows
from .agent_modelica_v0_9_0_common import DEGRADED_MINIMUM_PER_PRIORITY_BARRIER, PRIORITY_BARRIERS, WORKING_MINIMUM_PER_PRIORITY_BARRIER
from .agent_modelica_v0_9_1_candidate_source_admission import build_v091_candidate_source_admission
from .agent_modelica_v0_9_1_common import (
    DEFAULT_POOL_DELTA_OUT_DIR,
    DEFAULT_SOURCE_ADMISSION_OUT_DIR,
    DEFAULT_V090_GOVERNANCE_PACK_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v091_pool_delta(
    *,
    v090_governance_pack_path: str = str(DEFAULT_V090_GOVERNANCE_PACK_PATH),
    source_admission_path: str = str(DEFAULT_SOURCE_ADMISSION_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_POOL_DELTA_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    if not Path(source_admission_path).exists():
        build_v091_candidate_source_admission(out_dir=str(Path(source_admission_path).parent))
    governance = load_json(v090_governance_pack_path)
    source_admission = load_json(source_admission_path)
    baseline_rows = governance.get("baseline_candidate_rows") if isinstance(governance.get("baseline_candidate_rows"), list) else []
    intake = source_admission.get("candidate_source_intake_table") if isinstance(source_admission.get("candidate_source_intake_table"), list) else []

    admitted_sources = [row for row in intake if isinstance(row, dict) and row.get("source_admission_pass")]
    new_candidate_rows = []
    source_contribution_counts = {}
    for source in admitted_sources:
        rows = source.get("candidate_rows") if isinstance(source.get("candidate_rows"), list) else []
        evaluated = evaluate_candidate_rows(rows)
        admitted_rows = [row for row, verdict in zip(rows, evaluated) if verdict.get("admitted")]
        new_candidate_rows.extend(admitted_rows)
        source_contribution_counts[source["source_id"]] = len(admitted_rows)

    combined_rows = list(baseline_rows) + list(new_candidate_rows)
    combined_evaluations = evaluate_candidate_rows(combined_rows)
    admitted_combined = [row for row, verdict in zip(combined_rows, combined_evaluations) if verdict.get("admitted")]

    baseline_depth = {barrier: 0 for barrier in PRIORITY_BARRIERS}
    for row in evaluate_candidate_rows(baseline_rows):
        barrier = str(row.get("target_barrier_family") or "")
        if barrier in baseline_depth and row.get("admitted"):
            baseline_depth[barrier] += 1

    expanded_depth = {barrier: 0 for barrier in PRIORITY_BARRIERS}
    for row in evaluate_candidate_rows(admitted_combined):
        barrier = str(row.get("target_barrier_family") or "")
        if barrier in expanded_depth and row.get("admitted"):
            expanded_depth[barrier] += 1

    depth_delta = {barrier: expanded_depth[barrier] - baseline_depth[barrier] for barrier in PRIORITY_BARRIERS}
    degraded_status = {barrier: expanded_depth[barrier] >= DEGRADED_MINIMUM_PER_PRIORITY_BARRIER for barrier in PRIORITY_BARRIERS}
    working_status = {barrier: expanded_depth[barrier] >= WORKING_MINIMUM_PER_PRIORITY_BARRIER for barrier in PRIORITY_BARRIERS}

    meaningful_growth_source_present = any(count >= 3 for count in source_contribution_counts.values())
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_pool_delta_build",
        "generated_at_utc": now_utc(),
        "status": "PASS" if admitted_sources else "FAIL",
        "baseline_candidate_pool_count": len(baseline_rows),
        "post_expansion_candidate_pool_count": len(admitted_combined),
        "pool_delta_vs_v0_9_0": len(admitted_combined) - len(baseline_rows),
        "admitted_source_count": len(admitted_sources),
        "source_contribution_counts": source_contribution_counts,
        "meaningful_growth_source_present": meaningful_growth_source_present,
        "candidate_depth_by_priority_barrier": expanded_depth,
        "candidate_depth_delta_by_priority_barrier": depth_delta,
        "degraded_floor_status_by_priority_barrier": degraded_status,
        "working_minimum_status_by_priority_barrier": working_status,
        "post_expansion_candidate_pool": admitted_combined,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.1 Pool Delta",
                "",
                f"- post_expansion_candidate_pool_count: `{payload['post_expansion_candidate_pool_count']}`",
                f"- candidate_depth_by_priority_barrier: `{expanded_depth}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.1 pool delta artifact.")
    parser.add_argument("--v090-governance-pack", default=str(DEFAULT_V090_GOVERNANCE_PACK_PATH))
    parser.add_argument("--source-admission", default=str(DEFAULT_SOURCE_ADMISSION_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_POOL_DELTA_OUT_DIR))
    args = parser.parse_args()
    payload = build_v091_pool_delta(
        v090_governance_pack_path=str(args.v090_governance_pack),
        source_admission_path=str(args.source_admission),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "post_expansion_candidate_pool_count": payload.get("post_expansion_candidate_pool_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
