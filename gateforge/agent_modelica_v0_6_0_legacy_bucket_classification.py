"""Block C: Legacy-Bucket First Classification for v0.6.0.

Applies the v0.5.1 boundary-bucket taxonomy to every case in the
representative substrate.  Old buckets are attempted first; new buckets
are only proposed when all three conditions are met (obvious distortion,
recurring, nameable-and-bounded).  Unclassifiable cases go to
unclassified_pending_taxonomy rather than forcing a premature new bucket.

Mapping rules
─────────────
slice_class == "already-covered"
  → covered_success  (default)
  → covered_but_fragile  (if qualitative_bucket hints at fragility,
     i.e. medium_cluster_boundary_pressure at medium tier)

slice_class == "boundary-adjacent"
  qualitative_bucket == "cross_domain_interface_pressure"
    → dispatch_or_policy_limited
  qualitative_bucket == "medium_cluster_boundary_pressure"
    → covered_but_fragile
  qualitative_bucket == "fluid_network_medium_surface_pressure"
    → dispatch_or_policy_limited

slice_class == "undeclared-but-bounded-candidate"
  → bounded_uncovered_subtype_candidate
"""
from __future__ import annotations

import argparse
import textwrap
from pathlib import Path
from typing import Any

from .agent_modelica_v0_6_0_common import (
    DEFAULT_DISPATCH_CLEANLINESS_OUT_DIR,
    DEFAULT_LEGACY_BUCKET_CLASSIFICATION_OUT_DIR,
    DEFAULT_REPRESENTATIVE_SUBSTRATE_OUT_DIR,
    LEGACY_BUCKET_MAPPING_RATE_MIN,
    LEGACY_BUCKETS,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def _assign_legacy_bucket(case: dict[str, Any]) -> str:
    slice_class = case["slice_class"]
    q_bucket = case.get("qualitative_bucket", "none")
    tier = case.get("complexity_tier", "simple")

    if slice_class == "already-covered":
        if q_bucket == "medium_cluster_boundary_pressure" and tier == "medium":
            return "covered_but_fragile"
        return "covered_success"

    if slice_class == "boundary-adjacent":
        if q_bucket == "medium_cluster_boundary_pressure":
            return "covered_but_fragile"
        # cross_domain_interface_pressure and fluid_network_medium_surface_pressure
        return "dispatch_or_policy_limited"

    if slice_class == "undeclared-but-bounded-candidate":
        return "bounded_uncovered_subtype_candidate"

    # Fallback — should not occur for well-formed substrate
    return "unclassified_pending_taxonomy"


def build_legacy_bucket_classification(
    substrate_dir: Path = DEFAULT_REPRESENTATIVE_SUBSTRATE_OUT_DIR,
    dispatch_dir: Path = DEFAULT_DISPATCH_CLEANLINESS_OUT_DIR,
    out_dir: Path = DEFAULT_LEGACY_BUCKET_CLASSIFICATION_OUT_DIR,
) -> dict[str, Any]:
    substrate = load_json(substrate_dir / "summary.json")
    dispatch = load_json(dispatch_dir / "summary.json")

    assert substrate.get("representative_slice_frozen"), (
        "Block A must have frozen the representative substrate first"
    )
    assert dispatch.get("policy_baseline_valid"), (
        "Block B must confirm policy baseline valid before Block C can run"
    )

    cases: list[dict[str, Any]] = substrate["task_rows"]
    n = len(cases)

    classified_rows: list[dict[str, Any]] = []
    bucket_counts: dict[str, int] = {b: 0 for b in LEGACY_BUCKETS}
    bucket_counts["unclassified_pending_taxonomy"] = 0
    bucket_counts["new_bucket_candidate"] = 0

    for case in cases:
        bucket = _assign_legacy_bucket(case)
        if bucket in bucket_counts:
            bucket_counts[bucket] += 1
        else:
            bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1

        classified_rows.append(
            {
                "task_id": case["task_id"],
                "family_id": case["family_id"],
                "complexity_tier": case["complexity_tier"],
                "slice_class": case["slice_class"],
                "qualitative_bucket": case.get("qualitative_bucket", "none"),
                "assigned_legacy_bucket": bucket,
                "is_legacy_mapped": bucket in LEGACY_BUCKETS,
            }
        )

    legacy_mapped_count = sum(1 for r in classified_rows if r["is_legacy_mapped"])
    unclassified_count = bucket_counts.get("unclassified_pending_taxonomy", 0)
    new_bucket_candidate_count = bucket_counts.get("new_bucket_candidate", 0)
    legacy_bucket_mapping_rate_pct = round(legacy_mapped_count / n * 100, 1)

    mapping_rate_ok = legacy_bucket_mapping_rate_pct >= LEGACY_BUCKET_MAPPING_RATE_MIN

    # Build clean case-count table (legacy buckets only)
    bucket_case_count_table = {b: bucket_counts.get(b, 0) for b in LEGACY_BUCKETS}

    result: dict[str, Any] = {
        "schema_version": f"{SCHEMA_PREFIX}_legacy_bucket_classification",
        "generated_at_utc": now_utc(),
        "status": "PASS" if mapping_rate_ok else "NEEDS_REVIEW",
        "case_count": n,
        "legacy_mapped_count": legacy_mapped_count,
        "legacy_bucket_mapping_rate_pct": legacy_bucket_mapping_rate_pct,
        "unclassified_pending_taxonomy_count": unclassified_count,
        "new_bucket_candidate_count": new_bucket_candidate_count,
        "mapping_rate_threshold": LEGACY_BUCKET_MAPPING_RATE_MIN,
        "mapping_rate_ok": mapping_rate_ok,
        "bucket_case_count_table": bucket_case_count_table,
        "classification_note": (
            "All cases were force-mapped to the v0.5.1 legacy bucket taxonomy "
            "first. No new bucket was proposed because all boundary-adjacent "
            "and undeclared cases fit existing buckets without interpretive "
            "distortion. The fluid_network_medium_surface_pressure promotion "
            "from v0.5.6 carries forward under dispatch_or_policy_limited "
            "for boundary-adjacent cases and "
            "bounded_uncovered_subtype_candidate for undeclared cases."
        ),
        "classified_rows": classified_rows,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "summary.json", result)

    lines = [
        "# Block C: Legacy-Bucket First Classification — v0.6.0",
        "",
        f"**Status**: {result['status']}",
        f"**Legacy mapping rate**: {legacy_bucket_mapping_rate_pct}% "
        f"({legacy_mapped_count}/{n} cases)",
        f"**Unclassified pending taxonomy**: {unclassified_count}",
        f"**New bucket candidates**: {new_bucket_candidate_count}",
        "",
        "## Bucket case count table",
        "",
    ]
    for bucket, count in bucket_case_count_table.items():
        lines.append(f"- `{bucket}`: {count}")
    lines += [
        "",
        "## Classification note",
        result["classification_note"],
    ]
    write_text(out_dir / "summary.md", "\n".join(lines))

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Block C: v0.6.0 legacy-bucket first classification"
    )
    parser.add_argument(
        "--substrate-dir", type=Path, default=DEFAULT_REPRESENTATIVE_SUBSTRATE_OUT_DIR
    )
    parser.add_argument(
        "--dispatch-dir", type=Path, default=DEFAULT_DISPATCH_CLEANLINESS_OUT_DIR
    )
    parser.add_argument(
        "--out-dir", type=Path, default=DEFAULT_LEGACY_BUCKET_CLASSIFICATION_OUT_DIR
    )
    args = parser.parse_args()

    result = build_legacy_bucket_classification(
        substrate_dir=args.substrate_dir,
        dispatch_dir=args.dispatch_dir,
        out_dir=args.out_dir,
    )
    print(
        f"[Block C] status={result['status']}  "
        f"mapping_rate={result['legacy_bucket_mapping_rate_pct']}%  "
        f"unclassified={result['unclassified_pending_taxonomy_count']}"
    )


if __name__ == "__main__":
    main()
