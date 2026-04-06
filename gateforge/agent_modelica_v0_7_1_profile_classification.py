from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_7_1_common import (
    DEFAULT_LIVE_RUN_OUT_DIR,
    DEFAULT_PROFILE_CLASSIFICATION_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v071_profile_classification(
    *,
    live_run_path: str = str(DEFAULT_LIVE_RUN_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_PROFILE_CLASSIFICATION_OUT_DIR),
) -> dict:
    live_run = load_json(live_run_path)
    rows = list(live_run.get("case_result_table") or [])
    total = len(rows)

    counts = {
        "covered_success": 0,
        "covered_but_fragile": 0,
        "dispatch_or_policy_limited": 0,
        "bounded_uncovered_subtype_candidate": 0,
        "topology_or_open_world_spillover": 0,
    }
    unclassified = 0
    family_breakdown = {}
    complexity_breakdown = {}

    for row in rows:
        bucket = row.get("legacy_bucket_after_live_run")
        if bucket in counts:
            counts[bucket] += 1
        else:
            unclassified += 1

        family = row["family_id"]
        complexity = row["complexity_tier"]
        fam = family_breakdown.setdefault(
            family,
            {
                "stable": 0,
                "fragile": 0,
                "limited_or_uncovered": 0,
            },
        )
        comp = complexity_breakdown.setdefault(
            complexity,
            {
                "stable": 0,
                "fragile": 0,
                "limited_or_uncovered": 0,
            },
        )

        if bucket == "covered_success":
            fam["stable"] += 1
            comp["stable"] += 1
        elif bucket == "covered_but_fragile":
            fam["fragile"] += 1
            comp["fragile"] += 1
        else:
            fam["limited_or_uncovered"] += 1
            comp["limited_or_uncovered"] += 1

    stable = counts["covered_success"]
    fragile = counts["covered_but_fragile"]
    limited_or_uncovered = (
        counts["dispatch_or_policy_limited"]
        + counts["bounded_uncovered_subtype_candidate"]
        + counts["topology_or_open_world_spillover"]
        + unclassified
    )
    stable_coverage_share_pct = round((100.0 * stable / total), 1) if total else 0.0
    fragile_but_usable_share_pct = round((100.0 * fragile / total), 1) if total else 0.0
    dispatch_or_policy_limited_share_pct = round((100.0 * counts["dispatch_or_policy_limited"] / total), 1) if total else 0.0
    bounded_uncovered_share_pct = round((100.0 * counts["bounded_uncovered_subtype_candidate"] / total), 1) if total else 0.0
    spillover_share_pct_after_live_run = round((100.0 * counts["topology_or_open_world_spillover"] / total), 1) if total else 0.0
    legacy_bucket_mapping_rate_pct_after_live_run = round((100.0 * (total - unclassified) / total), 1) if total else 0.0

    pressure_scores = {}
    for family, values in family_breakdown.items():
        pressure_scores[f"family:{family}"] = values["limited_or_uncovered"]
    for complexity, values in complexity_breakdown.items():
        pressure_scores[f"complexity:{complexity}"] = values["limited_or_uncovered"]
    dominant_pressure_source = "unknown"
    if pressure_scores:
        dominant_pressure_source = max(pressure_scores.items(), key=lambda item: item[1])[0]
        if pressure_scores[dominant_pressure_source] == 0:
            dominant_pressure_source = "unknown"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_profile_classification",
        "generated_at_utc": now_utc(),
        "status": "PASS" if stable_coverage_share_pct > 0 else "FAIL",
        "stable_coverage_share_pct": stable_coverage_share_pct,
        "fragile_but_usable_share_pct": fragile_but_usable_share_pct,
        "dispatch_or_policy_limited_share_pct": dispatch_or_policy_limited_share_pct,
        "bounded_uncovered_share_pct": bounded_uncovered_share_pct,
        "spillover_share_pct_after_live_run": spillover_share_pct_after_live_run,
        "legacy_bucket_mapping_rate_pct_after_live_run": legacy_bucket_mapping_rate_pct_after_live_run,
        "unclassified_pending_taxonomy_count_after_live_run": unclassified,
        "dominant_pressure_source": dominant_pressure_source,
        "family_breakdown_after_live_run": family_breakdown,
        "complexity_breakdown_after_live_run": complexity_breakdown,
        "bucket_counts": counts,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.1 Profile Classification",
                "",
                f"- stable_coverage_share_pct: `{stable_coverage_share_pct}`",
                f"- fragile_but_usable_share_pct: `{fragile_but_usable_share_pct}`",
                f"- spillover_share_pct_after_live_run: `{spillover_share_pct_after_live_run}`",
                f"- legacy_bucket_mapping_rate_pct_after_live_run: `{legacy_bucket_mapping_rate_pct_after_live_run}`",
                f"- dominant_pressure_source: `{dominant_pressure_source}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.1 readiness profile classification.")
    parser.add_argument("--live-run", default=str(DEFAULT_LIVE_RUN_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_PROFILE_CLASSIFICATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v071_profile_classification(
        live_run_path=str(args.live_run),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
