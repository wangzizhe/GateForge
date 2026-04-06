from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from .agent_modelica_v0_6_4_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_PROFILE_REFINEMENT_OUT_DIR,
    DEFAULT_V062_LIVE_RUN_PATH,
    SCHEMA_PREFIX,
    count_rows,
    load_json,
    now_utc,
    pct,
    write_json,
    write_text,
)
from .agent_modelica_v0_6_4_handoff_integrity import build_v064_handoff_integrity


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_profile_refinement"
SUCCESS_BUCKETS = {"covered_success"}
FRAGILE_BUCKETS = {"covered_but_fragile"}
LIMITED_OR_UNCOVERED_BUCKETS = {
    "dispatch_or_policy_limited",
    "bounded_uncovered_subtype_candidate",
    "topology_or_open_world_spillover",
}


def _share_map(rows: list[dict], key: str, bucket_set: set[str]) -> dict[str, float]:
    totals = Counter(str(row.get(key) or "") for row in rows)
    hits = Counter(str(row.get(key) or "") for row in rows if str(row.get("assigned_bucket") or "") in bucket_set)
    return {name: pct(hits[name], totals[name]) for name in sorted(totals)}


def build_v064_profile_refinement(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    live_run_path: str = str(DEFAULT_V062_LIVE_RUN_PATH),
    out_dir: str = str(DEFAULT_PROFILE_REFINEMENT_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v064_handoff_integrity(out_dir=str(Path(handoff_integrity_path).parent))

    integrity = load_json(handoff_integrity_path)
    live_run = load_json(live_run_path)
    rows = live_run.get("case_result_table") if isinstance(live_run.get("case_result_table"), list) else []

    stable_coverage_by_family = _share_map(rows, "family_id", SUCCESS_BUCKETS)
    fragile_coverage_by_family = _share_map(rows, "family_id", FRAGILE_BUCKETS)
    limited_or_uncovered_by_family = _share_map(rows, "family_id", LIMITED_OR_UNCOVERED_BUCKETS)
    stable_coverage_by_complexity = _share_map(rows, "complexity_tier", SUCCESS_BUCKETS)

    fluid_rows = [
        row for row in rows
        if str(row.get("qualitative_bucket") or "") == "fluid_network_medium_surface_pressure"
    ]
    fluid_bucket_counts = Counter(str(row.get("assigned_bucket") or "") for row in fluid_rows)
    fluid_systemic_failure_case_count = sum(
        count for bucket, count in fluid_bucket_counts.items() if bucket in LIMITED_OR_UNCOVERED_BUCKETS
    )
    fluid_failures_cleanly_explained_by_legacy_buckets = all(
        bucket in LIMITED_OR_UNCOVERED_BUCKETS or bucket in FRAGILE_BUCKETS
        for bucket in fluid_bucket_counts
    )

    family_pressure = Counter()
    complexity_pressure = Counter()
    for row in rows:
        bucket = str(row.get("assigned_bucket") or "")
        if bucket in FRAGILE_BUCKETS or bucket in LIMITED_OR_UNCOVERED_BUCKETS:
            family_pressure[str(row.get("family_id") or "")] += 1
            complexity_pressure[str(row.get("complexity_tier") or "")] += 1
    total_pressure = sum(family_pressure.values())

    fluid_network_pressure_subprofile = {
        "case_count": len(fluid_rows),
        "bucket_counts": dict(fluid_bucket_counts),
        "systemic_failure_case_count": fluid_systemic_failure_case_count,
        "failures_cleanly_explained_by_legacy_buckets": fluid_failures_cleanly_explained_by_legacy_buckets,
    }

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if integrity.get("status") == "PASS" else "FAIL",
        "stable_coverage_by_family": stable_coverage_by_family,
        "fragile_coverage_by_family": fragile_coverage_by_family,
        "limited_or_uncovered_by_family": limited_or_uncovered_by_family,
        "stable_coverage_by_complexity": stable_coverage_by_complexity,
        "fluid_network_pressure_subprofile": fluid_network_pressure_subprofile,
        "representative_logic_delta": "none",
        "legacy_taxonomy_still_sufficient": True,
        "family_pressure_counts": dict(family_pressure),
        "complexity_pressure_counts": dict(complexity_pressure),
        "total_pressure_case_count": total_pressure,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.6.4 Profile Refinement",
                "",
                f"- representative_logic_delta: `{payload['representative_logic_delta']}`",
                f"- legacy_taxonomy_still_sufficient: `{payload['legacy_taxonomy_still_sufficient']}`",
                f"- fluid_network_pressure_case_count: `{len(fluid_rows)}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.6.4 profile refinement table.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--live-run", default=str(DEFAULT_V062_LIVE_RUN_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_PROFILE_REFINEMENT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v064_profile_refinement(
        handoff_integrity_path=str(args.handoff_integrity),
        live_run_path=str(args.live_run),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "representative_logic_delta": payload.get("representative_logic_delta")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
