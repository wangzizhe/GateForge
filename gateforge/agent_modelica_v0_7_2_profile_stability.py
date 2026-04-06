from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_7_2_common import (
    DEFAULT_LIVE_RUN_OUT_DIR,
    DEFAULT_PROFILE_STABILITY_OUT_DIR,
    DEFAULT_V071_CLOSEOUT_PATH,
    LEGACY_BUCKET_MAPPING_PARTIAL_MIN,
    LEGACY_BUCKET_MAPPING_STABLE_MIN,
    SCHEMA_PREFIX,
    SPILLOVER_INVALID_MAX,
    SPILLOVER_STABLE_MAX,
    STABLE_COVERAGE_STABLE_MIN,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v072_profile_stability(
    *,
    v071_closeout_path: str = str(DEFAULT_V071_CLOSEOUT_PATH),
    live_run_path: str = str(DEFAULT_LIVE_RUN_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_PROFILE_STABILITY_OUT_DIR),
) -> dict:
    v071 = load_json(v071_closeout_path)
    live_run = load_json(live_run_path)
    rows = list(live_run.get("case_result_table") or [])
    total = len(rows)

    counts = {
        "covered_success": 0,
        "covered_but_fragile": 0,
        "dispatch_or_policy_limited": 0,
        "bounded_uncovered_subtype_candidate": 0,
        "topology_or_open_world_spillover": 0,
        "unclassified_pending_taxonomy": 0,
    }
    family_breakdown = {}
    complexity_breakdown = {}
    for row in rows:
        bucket = row.get("legacy_bucket_after_live_run") or "unclassified_pending_taxonomy"
        counts[bucket] = counts.get(bucket, 0) + 1
        fam = family_breakdown.setdefault(row["family_id"], {"stable": 0, "fragile": 0, "limited_or_uncovered": 0})
        comp = complexity_breakdown.setdefault(row["complexity_tier"], {"stable": 0, "fragile": 0, "limited_or_uncovered": 0})
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
    stable_coverage_share_pct_after_extension = round((100.0 * stable / total), 1) if total else 0.0
    fragile_but_usable_share_pct_after_extension = round((100.0 * fragile / total), 1) if total else 0.0
    spillover_share_pct_after_extension = round((100.0 * counts["topology_or_open_world_spillover"] / total), 1) if total else 0.0
    legacy_bucket_mapping_rate_pct_after_extension = round(
        (100.0 * (total - counts["unclassified_pending_taxonomy"]) / total), 1
    ) if total else 0.0

    pressure_scores = {}
    for family, values in family_breakdown.items():
        pressure_scores[f"family:{family}"] = values["limited_or_uncovered"]
    for complexity, values in complexity_breakdown.items():
        pressure_scores[f"complexity:{complexity}"] = values["limited_or_uncovered"]
    dominant_pressure_source_after_extension = max(pressure_scores.items(), key=lambda item: item[1])[0] if pressure_scores else "unknown"
    if pressure_scores and pressure_scores[dominant_pressure_source_after_extension] == 0:
        dominant_pressure_source_after_extension = "unknown"

    previous_dominant = str((v071.get("conclusion") or {}).get("dominant_pressure_source") or "unknown")
    consistent_or_extension = (
        dominant_pressure_source_after_extension == previous_dominant
        or (
            previous_dominant.startswith("complexity:")
            and dominant_pressure_source_after_extension.startswith("complexity:")
        )
    )

    if (
        legacy_bucket_mapping_rate_pct_after_extension < LEGACY_BUCKET_MAPPING_PARTIAL_MIN
        or spillover_share_pct_after_extension > SPILLOVER_INVALID_MAX
        or stable_coverage_share_pct_after_extension == 0
        or dominant_pressure_source_after_extension == "unknown"
    ):
        status = "invalid"
    elif (
        legacy_bucket_mapping_rate_pct_after_extension >= LEGACY_BUCKET_MAPPING_STABLE_MIN
        and spillover_share_pct_after_extension <= SPILLOVER_STABLE_MAX
        and stable_coverage_share_pct_after_extension >= STABLE_COVERAGE_STABLE_MIN
        and consistent_or_extension
    ):
        status = "stable"
    else:
        status = "partial"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_profile_stability",
        "generated_at_utc": now_utc(),
        "status": "PASS" if status in {"stable", "partial"} else "FAIL",
        "profile_stability_status": status,
        "slice_extension_mode": live_run.get("slice_extension_mode"),
        "stable_coverage_share_pct_after_extension": stable_coverage_share_pct_after_extension,
        "fragile_but_usable_share_pct_after_extension": fragile_but_usable_share_pct_after_extension,
        "spillover_share_pct_after_extension": spillover_share_pct_after_extension,
        "legacy_bucket_mapping_rate_pct_after_extension": legacy_bucket_mapping_rate_pct_after_extension,
        "dominant_pressure_source_after_extension": dominant_pressure_source_after_extension,
        "dominant_pressure_structure_consistent_or_extension": consistent_or_extension,
        "family_breakdown_after_extension": family_breakdown,
        "complexity_breakdown_after_extension": complexity_breakdown,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.2 Profile Stability",
                "",
                f"- profile_stability_status: `{status}`",
                f"- stable_coverage_share_pct_after_extension: `{stable_coverage_share_pct_after_extension}`",
                f"- spillover_share_pct_after_extension: `{spillover_share_pct_after_extension}`",
                f"- dominant_pressure_source_after_extension: `{dominant_pressure_source_after_extension}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.2 profile stability.")
    parser.add_argument("--v071-closeout", default=str(DEFAULT_V071_CLOSEOUT_PATH))
    parser.add_argument("--live-run", default=str(DEFAULT_LIVE_RUN_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_PROFILE_STABILITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v072_profile_stability(
        v071_closeout_path=str(args.v071_closeout),
        live_run_path=str(args.live_run),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
