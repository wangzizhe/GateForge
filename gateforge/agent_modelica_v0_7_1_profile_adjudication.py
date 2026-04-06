from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_7_1_common import (
    DEFAULT_PROFILE_ADJUDICATION_OUT_DIR,
    DEFAULT_PROFILE_CLASSIFICATION_OUT_DIR,
    LEGACY_BUCKET_MAPPING_READY_MIN,
    SCHEMA_PREFIX,
    SPILLOVER_INVALID_MAX,
    SPILLOVER_READY_MAX,
    STABLE_COVERAGE_READY_MIN,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v071_profile_adjudication(
    *,
    profile_classification_path: str = str(DEFAULT_PROFILE_CLASSIFICATION_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_PROFILE_ADJUDICATION_OUT_DIR),
) -> dict:
    classification = load_json(profile_classification_path)

    mapping = float(classification.get("legacy_bucket_mapping_rate_pct_after_live_run") or 0.0)
    spillover = float(classification.get("spillover_share_pct_after_live_run") or 0.0)
    stable = float(classification.get("stable_coverage_share_pct") or 0.0)
    dominant = str(classification.get("dominant_pressure_source") or "unknown")
    fragile = float(classification.get("fragile_but_usable_share_pct") or 0.0)
    limited_or_uncovered = round(
        100.0 - stable - fragile,
        1,
    )

    if (
        mapping < LEGACY_BUCKET_MAPPING_READY_MIN
        or spillover > SPILLOVER_INVALID_MAX
        or stable == 0
        or dominant == "unknown"
    ):
        status = "invalid"
        gap = "profile_substrate_invalid"
    elif (
        mapping >= LEGACY_BUCKET_MAPPING_READY_MIN
        and spillover <= SPILLOVER_READY_MAX
        and stable >= STABLE_COVERAGE_READY_MIN
        and dominant != "unknown"
    ):
        status = "ready"
        gap = "none"
    else:
        status = "partial"
        gap = "readiness_profile_not_yet_strong_enough"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_profile_adjudication",
        "generated_at_utc": now_utc(),
        "status": "PASS" if status in {"ready", "partial"} else "FAIL",
        "profile_admission_status": status,
        "stable_coverage_share_pct": stable,
        "fragile_but_usable_share_pct": fragile,
        "limited_or_uncovered_share_pct": limited_or_uncovered,
        "spillover_share_pct_after_live_run": spillover,
        "legacy_bucket_mapping_rate_pct_after_live_run": mapping,
        "dominant_pressure_source": dominant,
        "primary_profile_gap": gap,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.1 Profile Adjudication",
                "",
                f"- profile_admission_status: `{status}`",
                f"- stable_coverage_share_pct: `{stable}`",
                f"- spillover_share_pct_after_live_run: `{spillover}`",
                f"- dominant_pressure_source: `{dominant}`",
                f"- primary_profile_gap: `{gap}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.1 profile adjudication.")
    parser.add_argument(
        "--profile-classification",
        default=str(DEFAULT_PROFILE_CLASSIFICATION_OUT_DIR / "summary.json"),
    )
    parser.add_argument("--out-dir", default=str(DEFAULT_PROFILE_ADJUDICATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v071_profile_adjudication(
        profile_classification_path=str(args.profile_classification),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
