from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_8_1_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_PROFILE_CHARACTERIZATION_OUT_DIR,
    DEFAULT_PROFILE_REPLAY_PACK_OUT_DIR,
    DEFAULT_V080_CLOSEOUT_PATH,
    DEFAULT_V080_PILOT_PROFILE_PATH,
    DEFAULT_V080_SUBSTRATE_PATH,
    DEGRADED_CASE_CONSISTENCY_MIN,
    DEGRADED_GOAL_ALIGNMENT_RANGE_MAX,
    DEGRADED_PROFILE_RUN_COUNT_MIN,
    DEGRADED_WORKFLOW_RESOLUTION_RANGE_MAX,
    PROMOTED_CASE_CONSISTENCY_MIN,
    PROMOTED_GOAL_ALIGNMENT_RANGE_MAX,
    PROMOTED_PROFILE_RUN_COUNT_MIN,
    PROMOTED_WORKFLOW_RESOLUTION_RANGE_MAX,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_8_1_handoff_integrity import build_v081_handoff_integrity
from .agent_modelica_v0_8_1_profile_replay_pack import build_v081_profile_replay_pack
from .agent_modelica_v0_8_1_workflow_profile_characterization import (
    build_v081_workflow_profile_characterization,
)


def build_v081_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    replay_pack_path: str = str(DEFAULT_PROFILE_REPLAY_PACK_OUT_DIR / "summary.json"),
    characterization_path: str = str(DEFAULT_PROFILE_CHARACTERIZATION_OUT_DIR / "summary.json"),
    v080_closeout_path: str = str(DEFAULT_V080_CLOSEOUT_PATH),
    v080_substrate_path: str = str(DEFAULT_V080_SUBSTRATE_PATH),
    v080_pilot_profile_path: str = str(DEFAULT_V080_PILOT_PROFILE_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
    profile_run_count: int = 3,
) -> dict:
    build_v081_handoff_integrity(
        v080_closeout_path=v080_closeout_path,
        v080_substrate_path=v080_substrate_path,
        v080_pilot_profile_path=v080_pilot_profile_path,
        out_dir=str(Path(handoff_integrity_path).parent),
    )
    integrity = load_json(handoff_integrity_path)
    if integrity.get("status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_8_1_HANDOFF_PROFILE_INVALID",
            "conclusion": {
                "version_decision": "v0_8_1_handoff_profile_invalid",
                "v0_8_2_handoff_mode": "repair_profile_execution_or_barrier_taxonomy_first",
                "why_this_is_interpretable_or_not": "Upstream v0.8.0 ready substrate handoff integrity did not pass.",
            },
            "handoff_integrity": integrity,
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.8.1 Closeout\n\n- version_decision: `v0_8_1_handoff_profile_invalid`\n")
        return payload

    build_v081_profile_replay_pack(
        substrate_path=v080_substrate_path,
        out_dir=str(Path(replay_pack_path).parent),
        profile_run_count=profile_run_count,
    )
    build_v081_workflow_profile_characterization(
        replay_pack_path=replay_pack_path,
        substrate_path=v080_substrate_path,
        out_dir=str(Path(characterization_path).parent),
    )

    replay_pack = load_json(replay_pack_path)
    characterization = load_json(characterization_path)

    promoted_repeatability = all(
        [
            int(replay_pack.get("profile_run_count") or 0) >= PROMOTED_PROFILE_RUN_COUNT_MIN,
            float(replay_pack.get("workflow_resolution_rate_range_pct") or 0.0)
            <= PROMOTED_WORKFLOW_RESOLUTION_RANGE_MAX,
            float(replay_pack.get("goal_alignment_rate_range_pct") or 0.0)
            <= PROMOTED_GOAL_ALIGNMENT_RANGE_MAX,
            float(replay_pack.get("per_case_outcome_consistency_rate_pct") or 0.0)
            >= PROMOTED_CASE_CONSISTENCY_MIN,
        ]
    )
    degraded_repeatability = all(
        [
            int(replay_pack.get("profile_run_count") or 0) >= DEGRADED_PROFILE_RUN_COUNT_MIN,
            float(replay_pack.get("workflow_resolution_rate_range_pct") or 0.0)
            <= DEGRADED_WORKFLOW_RESOLUTION_RANGE_MAX,
            float(replay_pack.get("goal_alignment_rate_range_pct") or 0.0)
            <= DEGRADED_GOAL_ALIGNMENT_RANGE_MAX,
            float(replay_pack.get("per_case_outcome_consistency_rate_pct") or 0.0)
            >= DEGRADED_CASE_CONSISTENCY_MIN,
        ]
    )
    promoted_explanation = all(
        [
            float(characterization.get("barrier_label_coverage_rate_pct") or 0.0) == 100.0,
            float(characterization.get("surface_fix_only_explained_rate_pct") or 0.0) == 100.0,
            float(characterization.get("unresolved_explained_rate_pct") or 0.0) == 100.0,
            int(characterization.get("profile_barrier_unclassified_count") or 0) == 0,
        ]
    )
    degraded_explanation = all(
        [
            float(characterization.get("barrier_label_coverage_rate_pct") or 0.0) == 100.0,
            float(characterization.get("surface_fix_only_explained_rate_pct") or 0.0) == 100.0,
            float(characterization.get("unresolved_explained_rate_pct") or 0.0) >= 75.0,
            int(characterization.get("profile_barrier_unclassified_count") or 0) <= 1,
        ]
    )
    if promoted_repeatability and promoted_explanation:
        status = "characterized"
        version_decision = "v0_8_1_workflow_readiness_profile_characterized"
        handoff = "freeze_workflow_readiness_thresholds_on_characterized_profile"
        why = "Frozen-substrate workflow profile is repeatable enough to characterize and every non-success case is explained without residual barrier ambiguity."
    elif degraded_repeatability and degraded_explanation:
        status = "partial"
        version_decision = "v0_8_1_workflow_readiness_profile_partial"
        handoff = "repair_profile_characterization_gaps_first"
        why = "Workflow profile exists and remains directionally interpretable, but repeatability or explanation coverage stays below the promoted characterization floor."
    else:
        status = "uninterpretable"
        version_decision = "v0_8_1_workflow_readiness_profile_uninterpretable"
        handoff = "repair_profile_execution_or_barrier_taxonomy_first"
        why = "Workflow profile could not maintain degraded repeatability or explanation coverage on the frozen substrate."

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": "PASS" if status in {"characterized", "partial"} else "FAIL",
        "closeout_status": {
            "characterized": "V0_8_1_WORKFLOW_READINESS_PROFILE_CHARACTERIZED",
            "partial": "V0_8_1_WORKFLOW_READINESS_PROFILE_PARTIAL",
            "uninterpretable": "V0_8_1_WORKFLOW_READINESS_PROFILE_UNINTERPRETABLE",
        }[status],
        "conclusion": {
            "version_decision": version_decision,
            "profile_run_count": replay_pack.get("profile_run_count"),
            "barrier_label_coverage_rate_pct": characterization.get("barrier_label_coverage_rate_pct"),
            "surface_fix_only_explained_rate_pct": characterization.get("surface_fix_only_explained_rate_pct"),
            "unresolved_explained_rate_pct": characterization.get("unresolved_explained_rate_pct"),
            "profile_barrier_unclassified_count": characterization.get("profile_barrier_unclassified_count"),
            "why_this_is_interpretable_or_not": why,
            "v0_8_2_handoff_mode": handoff,
        },
        "handoff_integrity": integrity,
        "profile_replay_pack": replay_pack,
        "workflow_profile_characterization": characterization,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.8.1 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- profile_run_count: `{replay_pack.get('profile_run_count')}`",
                f"- per_case_outcome_consistency_rate_pct: `{replay_pack.get('per_case_outcome_consistency_rate_pct')}`",
                f"- barrier_label_coverage_rate_pct: `{characterization.get('barrier_label_coverage_rate_pct')}`",
                f"- v0_8_2_handoff_mode: `{handoff}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.8.1 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--replay-pack", default=str(DEFAULT_PROFILE_REPLAY_PACK_OUT_DIR / "summary.json"))
    parser.add_argument(
        "--characterization-path",
        default=str(DEFAULT_PROFILE_CHARACTERIZATION_OUT_DIR / "summary.json"),
    )
    parser.add_argument("--v080-closeout", default=str(DEFAULT_V080_CLOSEOUT_PATH))
    parser.add_argument("--v080-substrate", default=str(DEFAULT_V080_SUBSTRATE_PATH))
    parser.add_argument("--v080-pilot-profile", default=str(DEFAULT_V080_PILOT_PROFILE_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    parser.add_argument("--profile-run-count", type=int, default=3)
    args = parser.parse_args()
    payload = build_v081_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        replay_pack_path=str(args.replay_pack),
        characterization_path=str(args.characterization_path),
        v080_closeout_path=str(args.v080_closeout),
        v080_substrate_path=str(args.v080_substrate),
        v080_pilot_profile_path=str(args.v080_pilot_profile),
        out_dir=str(args.out_dir),
        profile_run_count=int(args.profile_run_count),
    )
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "version_decision": (payload.get("conclusion") or {}).get("version_decision"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
