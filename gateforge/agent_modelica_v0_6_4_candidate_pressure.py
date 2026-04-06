from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_6_4_common import (
    DEFAULT_CANDIDATE_PRESSURE_OUT_DIR,
    DEFAULT_PROFILE_REFINEMENT_OUT_DIR,
    DEFAULT_V062_CLOSEOUT_PATH,
    DEFAULT_V063_CLOSEOUT_PATH,
    OPEN_WORLD_NEAR_MISS_STABLE_COVERAGE_MIN,
    OPEN_WORLD_READY_STABLE_COVERAGE_MIN,
    OPEN_WORLD_SPILLOVER_MAX,
    SCHEMA_PREFIX,
    TARGETED_EXPANSION_NEAR_MISS_BOUNDED_UNCOVERED_MIN,
    TARGETED_EXPANSION_READY_BOUNDED_UNCOVERED_MIN,
    DOMINANT_PRESSURE_SHARE_MIN,
    FLUID_NETWORK_BLOCKING_CASE_MIN,
    count_rows,
    load_json,
    now_utc,
    pct,
    write_json,
    write_text,
)
from .agent_modelica_v0_6_4_profile_refinement import build_v064_profile_refinement


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_candidate_pressure"


def _dominant_source(counter: dict[str, int], total_pressure: int) -> tuple[str | None, bool]:
    if total_pressure <= 0 or not counter:
        return None, False
    name, count = max(counter.items(), key=lambda item: item[1])
    return name, pct(count, total_pressure) >= DOMINANT_PRESSURE_SHARE_MIN


def build_v064_candidate_pressure(
    *,
    profile_refinement_path: str = str(DEFAULT_PROFILE_REFINEMENT_OUT_DIR / "summary.json"),
    v062_closeout_path: str = str(DEFAULT_V062_CLOSEOUT_PATH),
    v063_closeout_path: str = str(DEFAULT_V063_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_CANDIDATE_PRESSURE_OUT_DIR),
) -> dict:
    if not Path(profile_refinement_path).exists():
        build_v064_profile_refinement(out_dir=str(Path(profile_refinement_path).parent))

    refinement = load_json(profile_refinement_path)
    v062_closeout = load_json(v062_closeout_path)

    stable_coverage_share_pct = float(((v062_closeout.get("profile_stability") or {}).get("stable_coverage_share_pct")) or 0.0)
    bounded_uncovered_subtype_candidate_share_pct = float(
        ((v062_closeout.get("live_run") or {}).get("case_result_table") is None and 0.0)
    )
    # compute directly from refinement-backed live aggregation
    total_pressure = int(refinement.get("total_pressure_case_count") or 0)
    family_pressure_counts = refinement.get("family_pressure_counts") or {}
    complexity_pressure_counts = refinement.get("complexity_pressure_counts") or {}
    fluid_subprofile = refinement.get("fluid_network_pressure_subprofile") or {}

    # use v0.6.3 style inputs from actual closeout
    v063 = load_json(v063_closeout_path)
    phase_input = v063.get("phase_decision_input") or {}
    bounded_uncovered_subtype_candidate_share_pct = float(phase_input.get("bounded_uncovered_signal_share_pct") or 0.0)
    topology_or_open_world_spillover_share_pct = float(phase_input.get("topology_or_open_world_spillover_share_pct") or 0.0)

    dominant_family_source, dominant_family_is_actionable = _dominant_source(family_pressure_counts, total_pressure)
    dominant_complexity_source, dominant_complexity_is_actionable = _dominant_source(complexity_pressure_counts, total_pressure)

    if dominant_family_is_actionable:
        dominant_fragility_source = f"family_id:{dominant_family_source}"
    elif dominant_complexity_is_actionable:
        dominant_fragility_source = f"complexity_tier:{dominant_complexity_source}"
    else:
        dominant_fragility_source = "none"

    dominant_limited_or_uncovered_source = (
        f"family_id:{dominant_family_source}" if family_pressure_counts else "none"
    )

    fluid_network_extension_blocking_open_world = (
        int(fluid_subprofile.get("systemic_failure_case_count") or 0) >= FLUID_NETWORK_BLOCKING_CASE_MIN
        and not bool(fluid_subprofile.get("failures_cleanly_explained_by_legacy_buckets"))
    )

    open_world_candidate_supported = (
        stable_coverage_share_pct >= OPEN_WORLD_READY_STABLE_COVERAGE_MIN
        and topology_or_open_world_spillover_share_pct <= OPEN_WORLD_SPILLOVER_MAX
        and not fluid_network_extension_blocking_open_world
    )
    targeted_expansion_candidate_supported = (
        bounded_uncovered_subtype_candidate_share_pct >= TARGETED_EXPANSION_READY_BOUNDED_UNCOVERED_MIN
    )

    near_miss_open_world_candidate = (
        not open_world_candidate_supported
        and stable_coverage_share_pct >= OPEN_WORLD_NEAR_MISS_STABLE_COVERAGE_MIN
        and topology_or_open_world_spillover_share_pct <= OPEN_WORLD_SPILLOVER_MAX
    )
    near_miss_targeted_expansion_candidate = (
        not targeted_expansion_candidate_supported
        and bounded_uncovered_subtype_candidate_share_pct >= TARGETED_EXPANSION_NEAR_MISS_BOUNDED_UNCOVERED_MIN
    )

    bounded_uncovered_pattern_coherent = False

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "open_world_candidate_supported": open_world_candidate_supported,
        "targeted_expansion_candidate_supported": targeted_expansion_candidate_supported,
        "fluid_network_extension_blocking_open_world": fluid_network_extension_blocking_open_world,
        "dominant_fragility_source": dominant_fragility_source,
        "dominant_limited_or_uncovered_source": dominant_limited_or_uncovered_source,
        "near_miss_open_world_candidate": near_miss_open_world_candidate,
        "near_miss_targeted_expansion_candidate": near_miss_targeted_expansion_candidate,
        "stable_coverage_share_pct": stable_coverage_share_pct,
        "bounded_uncovered_subtype_candidate_share_pct": bounded_uncovered_subtype_candidate_share_pct,
        "topology_or_open_world_spillover_share_pct": topology_or_open_world_spillover_share_pct,
        "bounded_uncovered_pattern_coherent": bounded_uncovered_pattern_coherent,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.6.4 Candidate Pressure",
                "",
                f"- open_world_candidate_supported: `{open_world_candidate_supported}`",
                f"- targeted_expansion_candidate_supported: `{targeted_expansion_candidate_supported}`",
                f"- near_miss_open_world_candidate: `{near_miss_open_world_candidate}`",
                f"- dominant_fragility_source: `{dominant_fragility_source}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.6.4 candidate pressure adjudication.")
    parser.add_argument("--profile-refinement", default=str(DEFAULT_PROFILE_REFINEMENT_OUT_DIR / "summary.json"))
    parser.add_argument("--v062-closeout", default=str(DEFAULT_V062_CLOSEOUT_PATH))
    parser.add_argument("--v063-closeout", default=str(DEFAULT_V063_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CANDIDATE_PRESSURE_OUT_DIR))
    args = parser.parse_args()
    payload = build_v064_candidate_pressure(
        profile_refinement_path=str(args.profile_refinement),
        v062_closeout_path=str(args.v062_closeout),
        v063_closeout_path=str(args.v063_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "near_miss_open_world_candidate": payload.get("near_miss_open_world_candidate")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
