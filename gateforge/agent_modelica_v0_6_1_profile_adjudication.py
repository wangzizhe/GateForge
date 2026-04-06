from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_6_1_common import (
    DEFAULT_LIVE_RUN_OUT_DIR,
    DEFAULT_PROFILE_ADJUDICATION_OUT_DIR,
    DEFAULT_PROFILE_CLASSIFICATION_OUT_DIR,
    LEGACY_BUCKET_MAPPING_PARTIAL_MIN,
    LEGACY_BUCKET_MAPPING_READY_MIN,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_6_1_live_run import build_v061_live_run
from .agent_modelica_v0_6_1_profile_classification import build_v061_profile_classification


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_profile_adjudication"


def build_v061_profile_adjudication(
    *,
    live_run_path: str = str(DEFAULT_LIVE_RUN_OUT_DIR / "summary.json"),
    profile_classification_path: str = str(DEFAULT_PROFILE_CLASSIFICATION_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_PROFILE_ADJUDICATION_OUT_DIR),
) -> dict:
    if not Path(live_run_path).exists():
        build_v061_live_run(out_dir=str(Path(live_run_path).parent))
    if not Path(profile_classification_path).exists():
        build_v061_profile_classification(
            live_run_path=live_run_path,
            out_dir=str(Path(profile_classification_path).parent),
        )

    live_run = load_json(live_run_path)
    classification = load_json(profile_classification_path)

    dispatch_cleanliness_level_effective = str(
        live_run.get("dispatch_cleanliness_level_after_live_run") or "failed"
    )
    legacy_bucket_mapping_rate_pct = float(classification.get("legacy_bucket_mapping_rate_pct") or 0.0)
    profile_interpretability_ok = bool(classification.get("profile_interpretability_ok"))
    policy_baseline_valid = bool(live_run.get("policy_baseline_valid"))

    total = int(live_run.get("live_run_case_count") or 0)
    stable = int(classification.get("covered_success_count") or 0)
    fragile = int(classification.get("covered_but_fragile_count") or 0)
    limited_or_uncovered = (
        int(classification.get("dispatch_or_policy_limited_count") or 0)
        + int(classification.get("bounded_uncovered_subtype_candidate_count") or 0)
        + int(classification.get("topology_or_open_world_spillover_count") or 0)
    )

    stable_coverage_share_pct = round((100.0 * stable / total), 1) if total else 0.0
    fragile_coverage_share_pct = round((100.0 * fragile / total), 1) if total else 0.0
    limited_or_uncovered_share_pct = round((100.0 * limited_or_uncovered / total), 1) if total else 0.0

    representative_profile_auditable = (
        dispatch_cleanliness_level_effective == "promoted"
        and policy_baseline_valid
        and profile_interpretability_ok
    )

    if (
        dispatch_cleanliness_level_effective != "promoted"
        or not policy_baseline_valid
        or not profile_interpretability_ok
        or legacy_bucket_mapping_rate_pct < LEGACY_BUCKET_MAPPING_PARTIAL_MIN
    ):
        profile_status = "invalid"
        primary_profile_gap = "profile_substrate_invalid"
        can_enter_mid_v0_6_authority_phase = False
    elif legacy_bucket_mapping_rate_pct >= LEGACY_BUCKET_MAPPING_READY_MIN:
        profile_status = "ready"
        primary_profile_gap = "none"
        can_enter_mid_v0_6_authority_phase = True
    else:
        profile_status = "partial"
        primary_profile_gap = "legacy_bucket_mapping_below_ready_floor"
        can_enter_mid_v0_6_authority_phase = False

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if profile_status in {"ready", "partial"} else "FAIL",
        "profile_status": profile_status,
        "stable_coverage_share_pct": stable_coverage_share_pct,
        "fragile_coverage_share_pct": fragile_coverage_share_pct,
        "limited_or_uncovered_share_pct": limited_or_uncovered_share_pct,
        "representative_profile_auditable": representative_profile_auditable,
        "primary_profile_gap": primary_profile_gap,
        "can_enter_mid_v0_6_authority_phase": can_enter_mid_v0_6_authority_phase,
        "dispatch_cleanliness_level_effective": dispatch_cleanliness_level_effective,
        "policy_baseline_valid": policy_baseline_valid,
        "legacy_bucket_mapping_rate_pct": legacy_bucket_mapping_rate_pct,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.6.1 Profile Adjudication",
                "",
                f"- profile_status: `{profile_status}`",
                f"- stable_coverage_share_pct: `{stable_coverage_share_pct}`",
                f"- fragile_coverage_share_pct: `{fragile_coverage_share_pct}`",
                f"- limited_or_uncovered_share_pct: `{limited_or_uncovered_share_pct}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.6.1 profile adjudication.")
    parser.add_argument("--live-run", default=str(DEFAULT_LIVE_RUN_OUT_DIR / "summary.json"))
    parser.add_argument("--profile-classification", default=str(DEFAULT_PROFILE_CLASSIFICATION_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_PROFILE_ADJUDICATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v061_profile_adjudication(
        live_run_path=str(args.live_run),
        profile_classification_path=str(args.profile_classification),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "profile_status": payload.get("profile_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
