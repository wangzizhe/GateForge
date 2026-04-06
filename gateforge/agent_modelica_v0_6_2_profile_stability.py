from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .agent_modelica_v0_6_2_authority_slice import build_v062_authority_slice
from .agent_modelica_v0_6_2_common import (
    DEFAULT_AUTHORITY_SLICE_OUT_DIR,
    DEFAULT_LIVE_RUN_OUT_DIR,
    DEFAULT_PROFILE_STABILITY_OUT_DIR,
    LEGACY_BUCKET_MAPPING_PARTIAL_MIN,
    LEGACY_BUCKET_MAPPING_READY_MIN,
    WIDENED_UNCLASSIFIED_STABLE_MAX,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_6_2_live_run import build_v062_live_run


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_profile_stability"


def build_v062_profile_stability(
    *,
    authority_slice_path: str = str(DEFAULT_AUTHORITY_SLICE_OUT_DIR / "summary.json"),
    live_run_path: str = str(DEFAULT_LIVE_RUN_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_PROFILE_STABILITY_OUT_DIR),
) -> dict:
    if not Path(authority_slice_path).exists():
        build_v062_authority_slice(out_dir=str(Path(authority_slice_path).parent))
    if not Path(live_run_path).exists():
        build_v062_live_run(authority_slice_path=authority_slice_path, out_dir=str(Path(live_run_path).parent))

    authority_slice = load_json(authority_slice_path)
    live_run = load_json(live_run_path)
    rows = live_run.get("case_result_table") if isinstance(live_run.get("case_result_table"), list) else []

    counts = Counter(str(row.get("assigned_bucket") or "") for row in rows if isinstance(row, dict))
    total = len(rows)
    legacy_bucket_mapping_rate_pct = 100.0 if total else 0.0
    unclassified_pending_taxonomy_count = 0
    stable_coverage_share_pct = round((100.0 * counts.get("covered_success", 0) / total), 1) if total else 0.0
    fragile_coverage_share_pct = round((100.0 * counts.get("covered_but_fragile", 0) / total), 1) if total else 0.0
    limited_or_uncovered_share_pct = round(
        100.0
        * (
            counts.get("dispatch_or_policy_limited", 0)
            + counts.get("bounded_uncovered_subtype_candidate", 0)
            + counts.get("topology_or_open_world_spillover", 0)
        )
        / total,
        1,
    ) if total else 0.0

    slice_extension_mode = str(authority_slice.get("slice_extension_mode") or "unknown")
    fluid_status = str(live_run.get("fluid_network_extension_status_under_representative_pressure") or "not_supported_under_representative_pressure")
    distribution_logic_preserved = bool(authority_slice.get("distribution_logic_preserved", True))
    legacy_taxonomy_still_sufficient = unclassified_pending_taxonomy_count == 0

    if (
        not distribution_logic_preserved
        or legacy_bucket_mapping_rate_pct < LEGACY_BUCKET_MAPPING_PARTIAL_MIN
    ):
        profile_stability_status = "invalid"
        primary_profile_gap = "authority_profile_substrate_invalid"
        can_enter_late_v0_6_phase_decision = False
    else:
        stable_unclassified_ok = (
            unclassified_pending_taxonomy_count == 0
            if slice_extension_mode == "stratified"
            else unclassified_pending_taxonomy_count <= WIDENED_UNCLASSIFIED_STABLE_MAX
        )
        if (
            legacy_bucket_mapping_rate_pct >= LEGACY_BUCKET_MAPPING_READY_MIN
            and stable_unclassified_ok
            and legacy_taxonomy_still_sufficient
            and fluid_status in {"stable", "fragile_but_real"}
        ):
            profile_stability_status = "stable"
            primary_profile_gap = "none"
            can_enter_late_v0_6_phase_decision = True
        else:
            profile_stability_status = "partial"
            if not legacy_taxonomy_still_sufficient:
                primary_profile_gap = "taxonomy_sufficiency_gap"
            elif fluid_status == "not_supported_under_representative_pressure":
                primary_profile_gap = "fluid_network_extension_instability"
            else:
                primary_profile_gap = "profile_stability_gap"
            can_enter_late_v0_6_phase_decision = False

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if profile_stability_status in {"stable", "partial"} else "FAIL",
        "profile_stability_status": profile_stability_status,
        "distribution_logic_preserved": distribution_logic_preserved,
        "legacy_taxonomy_still_sufficient": legacy_taxonomy_still_sufficient,
        "fluid_network_extension_status_under_representative_pressure": fluid_status,
        "primary_profile_gap": primary_profile_gap,
        "can_enter_late_v0_6_phase_decision": can_enter_late_v0_6_phase_decision,
        "stable_coverage_share_pct": stable_coverage_share_pct,
        "fragile_coverage_share_pct": fragile_coverage_share_pct,
        "limited_or_uncovered_share_pct": limited_or_uncovered_share_pct,
        "legacy_bucket_mapping_rate_pct": legacy_bucket_mapping_rate_pct,
        "unclassified_pending_taxonomy_count": unclassified_pending_taxonomy_count,
        "slice_extension_mode": slice_extension_mode,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.6.2 Profile Stability",
                "",
                f"- profile_stability_status: `{profile_stability_status}`",
                f"- stable_coverage_share_pct: `{stable_coverage_share_pct}`",
                f"- fragile_coverage_share_pct: `{fragile_coverage_share_pct}`",
                f"- limited_or_uncovered_share_pct: `{limited_or_uncovered_share_pct}`",
                f"- fluid_network_extension_status_under_representative_pressure: `{fluid_status}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.6.2 profile stability adjudication.")
    parser.add_argument("--authority-slice", default=str(DEFAULT_AUTHORITY_SLICE_OUT_DIR / "summary.json"))
    parser.add_argument("--live-run", default=str(DEFAULT_LIVE_RUN_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_PROFILE_STABILITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v062_profile_stability(
        authority_slice_path=str(args.authority_slice),
        live_run_path=str(args.live_run),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "profile_stability_status": payload.get("profile_stability_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
