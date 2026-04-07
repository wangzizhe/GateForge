"""Block B: Stop-Condition Audit.

Derives the five boolean stop-condition fields from upstream closeout data
and adjudicates phase_stop_condition_status per the routing table in PLAN_V0_7_7.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_7_7_common import (
    DEFAULT_STOP_CONDITION_OUT_DIR,
    DEFAULT_V070_CLOSEOUT_PATH,
    DEFAULT_V071_CLOSEOUT_PATH,
    DEFAULT_V072_CLOSEOUT_PATH,
    DEFAULT_V074_CLOSEOUT_PATH,
    DEFAULT_V076_CLOSEOUT_PATH,
    LEGACY_TAXONOMY_DOMINANT_FLOOR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v077_stop_condition(
    *,
    v070_closeout_path: str = str(DEFAULT_V070_CLOSEOUT_PATH),
    v071_closeout_path: str = str(DEFAULT_V071_CLOSEOUT_PATH),
    v072_closeout_path: str = str(DEFAULT_V072_CLOSEOUT_PATH),
    v074_closeout_path: str = str(DEFAULT_V074_CLOSEOUT_PATH),
    v076_closeout_path: str = str(DEFAULT_V076_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_STOP_CONDITION_OUT_DIR),
) -> dict:
    v070 = load_json(v070_closeout_path)
    v070c = v070.get("conclusion") or {}
    v071 = load_json(v071_closeout_path)
    v071c = v071.get("conclusion") or {}
    v072 = load_json(v072_closeout_path)
    v072c = v072.get("conclusion") or {}
    v074 = load_json(v074_closeout_path)
    v074c = v074.get("conclusion") or {}
    v076 = load_json(v076_closeout_path)
    v076c = v076.get("conclusion") or {}

    # weaker_curated_substrate_supported: v0.7.0 substrate was admitted as ready
    # and weaker curation was confirmed.
    weaker_curated_substrate_supported = (
        v070c.get("substrate_admission_status") == "ready"
        and bool(v070c.get("weaker_curation_confirmed"))
    )

    # readiness_profile_supported: v0.7.1 produced a ready profile AND v0.7.2
    # confirmed it is stable under the extension run.
    readiness_profile_supported = (
        v071c.get("version_decision") == "v0_7_1_readiness_profile_ready"
        and v072c.get("version_decision") == "v0_7_2_readiness_profile_stable"
    )

    # legacy_taxonomy_dominant_enough: the legacy bucket mapping rate on the
    # open-world-adjacent substrate meets the roadmap floor of >=70%.
    legacy_mapping_rate = float(v070c.get("legacy_bucket_mapping_rate_pct") or 0.0)
    legacy_taxonomy_dominant_enough = legacy_mapping_rate >= LEGACY_TAXONOMY_DOMINANT_FLOOR

    # fallback_not_triggered: v0.7.4 adjudication did NOT pass the fallback floor,
    # meaning targeted expansion was never required.
    fallback_not_triggered = v074c.get("fallback_floor_passed") is not True

    # late_phase_closeout_supported: v0.7.6 confirmed phase closeout is supported.
    late_phase_closeout_supported = (
        v076c.get("late_phase_support_status") == "phase_closeout_supported"
    )

    # Routing table per PLAN_V0_7_7 Block B.
    if all(
        [
            weaker_curated_substrate_supported,
            readiness_profile_supported,
            legacy_taxonomy_dominant_enough,
            fallback_not_triggered,
            late_phase_closeout_supported,
        ]
    ):
        phase_stop_condition_status = "phase_stop_condition_met"
    elif (
        weaker_curated_substrate_supported
        and readiness_profile_supported
        and legacy_taxonomy_dominant_enough
        and fallback_not_triggered
        and not late_phase_closeout_supported
    ):
        phase_stop_condition_status = "nearly_complete_with_caveat"
    else:
        # Any of the foundational conditions (substrate, profile, legacy, fallback)
        # is not met — cannot proceed to closeout.
        phase_stop_condition_status = "not_ready_for_closeout"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_stop_condition",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "weaker_curated_substrate_supported": weaker_curated_substrate_supported,
        "readiness_profile_supported": readiness_profile_supported,
        "legacy_taxonomy_dominant_enough": legacy_taxonomy_dominant_enough,
        "legacy_bucket_mapping_rate_pct": legacy_mapping_rate,
        "fallback_not_triggered": fallback_not_triggered,
        "late_phase_closeout_supported": late_phase_closeout_supported,
        "phase_stop_condition_status": phase_stop_condition_status,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.7 Stop-Condition Audit",
                "",
                f"- phase_stop_condition_status: `{phase_stop_condition_status}`",
                f"- weaker_curated_substrate_supported: `{weaker_curated_substrate_supported}`",
                f"- readiness_profile_supported: `{readiness_profile_supported}`",
                f"- legacy_taxonomy_dominant_enough: `{legacy_taxonomy_dominant_enough}`"
                f" (rate={legacy_mapping_rate:.1f}%)",
                f"- fallback_not_triggered: `{fallback_not_triggered}`",
                f"- late_phase_closeout_supported: `{late_phase_closeout_supported}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.7 stop-condition audit.")
    parser.add_argument("--v070-closeout", default=str(DEFAULT_V070_CLOSEOUT_PATH))
    parser.add_argument("--v071-closeout", default=str(DEFAULT_V071_CLOSEOUT_PATH))
    parser.add_argument("--v072-closeout", default=str(DEFAULT_V072_CLOSEOUT_PATH))
    parser.add_argument("--v074-closeout", default=str(DEFAULT_V074_CLOSEOUT_PATH))
    parser.add_argument("--v076-closeout", default=str(DEFAULT_V076_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_STOP_CONDITION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v077_stop_condition(
        v070_closeout_path=str(args.v070_closeout),
        v071_closeout_path=str(args.v071_closeout),
        v072_closeout_path=str(args.v072_closeout),
        v074_closeout_path=str(args.v074_closeout),
        v076_closeout_path=str(args.v076_closeout),
        out_dir=str(args.out_dir),
    )
    print(payload["phase_stop_condition_status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
