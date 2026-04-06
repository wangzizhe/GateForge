from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_6_1_common import (
    DEFAULT_LIVE_RUN_OUT_DIR,
    DEFAULT_PROFILE_CLASSIFICATION_OUT_DIR,
    LEGACY_BUCKETS,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_6_1_live_run import build_v061_live_run


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_profile_classification"


def build_v061_profile_classification(
    *,
    live_run_path: str = str(DEFAULT_LIVE_RUN_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_PROFILE_CLASSIFICATION_OUT_DIR),
) -> dict:
    if not Path(live_run_path).exists():
        build_v061_live_run(out_dir=str(Path(live_run_path).parent))

    live_run = load_json(live_run_path)
    rows = live_run.get("case_result_table") if isinstance(live_run.get("case_result_table"), list) else []

    qualitative_bucket_table = {}
    bucket_counts = {bucket: 0 for bucket in LEGACY_BUCKETS}
    for row in rows:
        if not isinstance(row, dict):
            continue
        task_id = str(row.get("task_id") or "")
        bucket = str(row.get("qualitative_bucket_result") or "unclassified_pending_taxonomy")
        qualitative_bucket_table[task_id] = bucket
        if bucket in bucket_counts:
            bucket_counts[bucket] += 1

    total_count = len(qualitative_bucket_table)
    mapped_count = sum(bucket_counts.values())
    legacy_bucket_mapping_rate_pct = round((100.0 * mapped_count / total_count), 1) if total_count else 0.0
    unclassified_pending_taxonomy_count = total_count - mapped_count
    new_bucket_candidate_count = 0
    profile_interpretability_ok = unclassified_pending_taxonomy_count == 0

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if profile_interpretability_ok else "FAIL",
        "qualitative_bucket_table": qualitative_bucket_table,
        "covered_success_count": bucket_counts["covered_success"],
        "covered_but_fragile_count": bucket_counts["covered_but_fragile"],
        "dispatch_or_policy_limited_count": bucket_counts["dispatch_or_policy_limited"],
        "bounded_uncovered_subtype_candidate_count": bucket_counts["bounded_uncovered_subtype_candidate"],
        "topology_or_open_world_spillover_count": bucket_counts["topology_or_open_world_spillover"],
        "legacy_bucket_mapping_rate_pct": legacy_bucket_mapping_rate_pct,
        "unclassified_pending_taxonomy_count": unclassified_pending_taxonomy_count,
        "new_bucket_candidate_count": new_bucket_candidate_count,
        "profile_interpretability_ok": profile_interpretability_ok,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.6.1 Profile Classification",
                "",
                f"- legacy_bucket_mapping_rate_pct: `{legacy_bucket_mapping_rate_pct}`",
                f"- covered_success_count: `{bucket_counts['covered_success']}`",
                f"- covered_but_fragile_count: `{bucket_counts['covered_but_fragile']}`",
                f"- dispatch_or_policy_limited_count: `{bucket_counts['dispatch_or_policy_limited']}`",
                f"- bounded_uncovered_subtype_candidate_count: `{bucket_counts['bounded_uncovered_subtype_candidate']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.6.1 authority profile classification.")
    parser.add_argument("--live-run", default=str(DEFAULT_LIVE_RUN_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_PROFILE_CLASSIFICATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v061_profile_classification(
        live_run_path=str(args.live_run),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "legacy_bucket_mapping_rate_pct": payload.get("legacy_bucket_mapping_rate_pct")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
