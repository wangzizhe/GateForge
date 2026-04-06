from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_7_0_common import (
    DEFAULT_LEGACY_BUCKET_AUDIT_OUT_DIR,
    DEFAULT_OPEN_WORLD_ADJACENT_SUBSTRATE_OUT_DIR,
    DISPATCH_AMBIGUITY_PARTIAL_MAX,
    DISPATCH_AMBIGUITY_PROMOTED_MAX,
    LEGACY_BUCKETS,
    LEGACY_BUCKET_MAPPING_RATE_MIN,
    SCHEMA_PREFIX,
    UNCLASSIFIED_PENDING_MAX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def _dispatch_cleanliness_level(ambiguity_rate_pct: float) -> str:
    if ambiguity_rate_pct <= DISPATCH_AMBIGUITY_PROMOTED_MAX:
        return "promoted"
    if ambiguity_rate_pct <= DISPATCH_AMBIGUITY_PARTIAL_MAX:
        return "degraded_but_executable"
    return "failed"


def build_v070_legacy_bucket_audit(
    *,
    substrate_path: str = str(DEFAULT_OPEN_WORLD_ADJACENT_SUBSTRATE_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_LEGACY_BUCKET_AUDIT_OUT_DIR),
) -> dict:
    substrate = load_json(substrate_path)
    rows = list(substrate["task_rows"])
    total = len(rows)

    counts = {bucket: 0 for bucket in LEGACY_BUCKETS}
    unclassified_count = 0
    ambiguous_count = 0
    for row in rows:
        bucket = row["legacy_bucket_hint"]
        if bucket in counts:
            counts[bucket] += 1
        elif bucket == "unclassified_pending_taxonomy":
            unclassified_count += 1
        if row["dispatch_risk"] == "ambiguous":
            ambiguous_count += 1

    legacy_mapped_count = sum(counts.values())
    legacy_bucket_mapping_rate_pct = round(legacy_mapped_count / total * 100, 1)
    ambiguity_rate_pct = round(ambiguous_count / total * 100, 1)
    dispatch_cleanliness_level = _dispatch_cleanliness_level(ambiguity_rate_pct)
    spillover_share_pct = round(counts["topology_or_open_world_spillover"] / total * 100, 1)
    bounded_uncovered_share_pct = round(counts["bounded_uncovered_subtype_candidate"] / total * 100, 1)
    covered_success_share_pct = round(counts["covered_success"] / total * 100, 1)
    covered_but_fragile_share_pct = round(counts["covered_but_fragile"] / total * 100, 1)
    dispatch_or_policy_limited_share_pct = round(counts["dispatch_or_policy_limited"] / total * 100, 1)

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_legacy_bucket_audit",
        "generated_at_utc": now_utc(),
        "status": "PASS"
        if (
            legacy_bucket_mapping_rate_pct >= LEGACY_BUCKET_MAPPING_RATE_MIN
            and unclassified_count <= UNCLASSIFIED_PENDING_MAX
            and dispatch_cleanliness_level != "failed"
        )
        else "FAIL",
        "legacy_bucket_mapping_rate_pct": legacy_bucket_mapping_rate_pct,
        "unclassified_pending_taxonomy_count": unclassified_count,
        "dispatch_cleanliness_level": dispatch_cleanliness_level,
        "attribution_ambiguity_rate_pct": ambiguity_rate_pct,
        "spillover_share_pct": spillover_share_pct,
        "bounded_uncovered_share_pct": bounded_uncovered_share_pct,
        "covered_success_share_pct": covered_success_share_pct,
        "covered_but_fragile_share_pct": covered_but_fragile_share_pct,
        "dispatch_or_policy_limited_share_pct": dispatch_or_policy_limited_share_pct,
        "bucket_case_count_table": counts,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.0 Legacy Bucket Audit",
                "",
                f"- legacy_bucket_mapping_rate_pct: `{legacy_bucket_mapping_rate_pct}`",
                f"- dispatch_cleanliness_level: `{dispatch_cleanliness_level}`",
                f"- spillover_share_pct: `{spillover_share_pct}`",
                f"- unclassified_pending_taxonomy_count: `{unclassified_count}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.0 legacy bucket audit.")
    parser.add_argument(
        "--substrate-path",
        default=str(DEFAULT_OPEN_WORLD_ADJACENT_SUBSTRATE_OUT_DIR / "summary.json"),
    )
    parser.add_argument("--out-dir", default=str(DEFAULT_LEGACY_BUCKET_AUDIT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v070_legacy_bucket_audit(
        substrate_path=str(args.substrate_path),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
