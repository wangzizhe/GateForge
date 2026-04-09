from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_9_3_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_EXPANDED_PROFILE_CHARACTERIZATION_OUT_DIR,
    DEFAULT_EXPANDED_PROFILE_REPLAY_PACK_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V092_CLOSEOUT_PATH,
    DEFAULT_V092_EXPANDED_SUBSTRATE_BUILDER_PATH,
    MAX_UNEXPLAINED_CASE_FLIPS,
    PROFILE_RUN_COUNT,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_9_3_expanded_profile_replay_pack import build_v093_expanded_profile_replay_pack
from .agent_modelica_v0_9_3_expanded_workflow_profile_characterization import (
    build_v093_expanded_workflow_profile_characterization,
)
from .agent_modelica_v0_9_3_handoff_integrity import build_v093_handoff_integrity


def build_v093_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    replay_pack_path: str = str(DEFAULT_EXPANDED_PROFILE_REPLAY_PACK_OUT_DIR / "summary.json"),
    characterization_path: str = str(DEFAULT_EXPANDED_PROFILE_CHARACTERIZATION_OUT_DIR / "summary.json"),
    v092_closeout_path: str = str(DEFAULT_V092_CLOSEOUT_PATH),
    v092_expanded_substrate_builder_path: str = str(DEFAULT_V092_EXPANDED_SUBSTRATE_BUILDER_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
    profile_run_count: int = PROFILE_RUN_COUNT,
) -> dict:
    build_v093_handoff_integrity(
        v092_closeout_path=v092_closeout_path,
        v092_expanded_substrate_builder_path=v092_expanded_substrate_builder_path,
        out_dir=str(Path(handoff_integrity_path).parent),
    )
    integrity = load_json(handoff_integrity_path)
    if integrity.get("handoff_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_9_3_PROFILE_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_9_3_profile_inputs_invalid",
                "v0_9_4_handoff_mode": "rebuild_v0_9_3_inputs_first",
                "why_this_is_interpretable_or_not": "Upstream v0.9.2 expanded-substrate-ready handoff integrity did not pass.",
            },
            "handoff_integrity": integrity,
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.9.3 Closeout\n\n- version_decision: `v0_9_3_profile_inputs_invalid`\n")
        return payload

    build_v093_expanded_profile_replay_pack(
        v092_expanded_substrate_builder_path=v092_expanded_substrate_builder_path,
        out_dir=str(Path(replay_pack_path).parent),
        profile_run_count=profile_run_count,
    )
    build_v093_expanded_workflow_profile_characterization(
        replay_pack_path=replay_pack_path,
        v092_expanded_substrate_builder_path=v092_expanded_substrate_builder_path,
        out_dir=str(Path(characterization_path).parent),
    )

    replay_pack = load_json(replay_pack_path)
    characterization = load_json(characterization_path)

    runtime_valid = not bool(replay_pack.get("runtime_invalid_due_to_all_failed_executor"))
    repeatability_floor_met = all(
        [
            replay_pack.get("status") == "PASS",
            int(replay_pack.get("profile_run_count") or 0) >= PROFILE_RUN_COUNT,
            int(replay_pack.get("unexplained_case_flip_count") or 0) <= MAX_UNEXPLAINED_CASE_FLIPS,
            bool(replay_pack.get("primary_workflow_route_picture_interpretable")),
            runtime_valid,
        ]
    )
    explainability_floor_met = all(
        [
            float(characterization.get("barrier_label_coverage_rate_pct") or 0.0) == 100.0,
            float(characterization.get("surface_fix_only_explained_rate_pct") or 0.0) == 100.0,
            float(characterization.get("unresolved_explained_rate_pct") or 0.0) == 100.0,
            int(characterization.get("profile_barrier_unclassified_count") or 0) == 0,
        ]
    )
    profile_interpretable = bool(characterization.get("workflow_level_interpretable"))

    if repeatability_floor_met and explainability_floor_met and profile_interpretable:
        status = "PASS"
        version_decision = "v0_9_3_expanded_workflow_profile_characterized"
        handoff_mode = "freeze_expanded_workflow_thresholds"
        why = "The first expanded workflow profile is stable enough to characterize, and every non-success case is explained without residual barrier ambiguity."
    elif runtime_valid and bool(replay_pack.get("primary_workflow_route_picture_interpretable")):
        status = "PASS"
        version_decision = "v0_9_3_expanded_workflow_profile_partial"
        handoff_mode = "clarify_expanded_profile_before_threshold_freeze"
        why = "The expanded profile is inspectable, but repeatability or barrier explainability still stays below the frozen characterization floor."
    else:
        status = "FAIL"
        version_decision = "v0_9_3_profile_inputs_invalid"
        handoff_mode = "rebuild_v0_9_3_inputs_first"
        why = "The replay pack stayed runtime-invalid or non-interpretable, so the expanded profile cannot yet support threshold freezing."

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": version_decision.upper(),
        "conclusion": {
            "version_decision": version_decision,
            "profile_run_count": replay_pack.get("profile_run_count"),
            "workflow_resolution_rate_pct": characterization.get("workflow_resolution_rate_pct"),
            "goal_alignment_rate_pct": characterization.get("goal_alignment_rate_pct"),
            "surface_fix_only_rate_pct": characterization.get("surface_fix_only_rate_pct"),
            "unresolved_rate_pct": characterization.get("unresolved_rate_pct"),
            "barrier_label_distribution": characterization.get("barrier_label_distribution"),
            "profile_barrier_unclassified_count": characterization.get("profile_barrier_unclassified_count"),
            "v0_9_4_handoff_mode": handoff_mode,
            "why_this_is_interpretable_or_not": why,
        },
        "handoff_integrity": integrity,
        "expanded_profile_replay_pack": replay_pack,
        "expanded_workflow_profile_characterization": characterization,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.3 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- profile_run_count: `{replay_pack.get('profile_run_count')}`",
                f"- workflow_resolution_rate_pct: `{characterization.get('workflow_resolution_rate_pct')}`",
                f"- goal_alignment_rate_pct: `{characterization.get('goal_alignment_rate_pct')}`",
                f"- v0_9_4_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.3 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--replay-pack", default=str(DEFAULT_EXPANDED_PROFILE_REPLAY_PACK_OUT_DIR / "summary.json"))
    parser.add_argument("--characterization-path", default=str(DEFAULT_EXPANDED_PROFILE_CHARACTERIZATION_OUT_DIR / "summary.json"))
    parser.add_argument("--v092-closeout", default=str(DEFAULT_V092_CLOSEOUT_PATH))
    parser.add_argument("--v092-expanded-substrate-builder", default=str(DEFAULT_V092_EXPANDED_SUBSTRATE_BUILDER_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    parser.add_argument("--profile-run-count", type=int, default=PROFILE_RUN_COUNT)
    args = parser.parse_args()
    payload = build_v093_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        replay_pack_path=str(args.replay_pack),
        characterization_path=str(args.characterization_path),
        v092_closeout_path=str(args.v092_closeout),
        v092_expanded_substrate_builder_path=str(args.v092_expanded_substrate_builder),
        out_dir=str(args.out_dir),
        profile_run_count=int(args.profile_run_count),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
