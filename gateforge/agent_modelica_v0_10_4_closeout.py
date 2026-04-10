from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_10_4_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_REAL_ORIGIN_PROFILE_CHARACTERIZATION_OUT_DIR,
    DEFAULT_REAL_ORIGIN_PROFILE_REPLAY_PACK_OUT_DIR,
    DEFAULT_V103_CLOSEOUT_PATH,
    DEFAULT_V103_REAL_ORIGIN_SUBSTRATE_BUILDER_PATH,
    MAX_UNEXPLAINED_CASE_FLIPS,
    PROFILE_RUN_COUNT,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_10_4_handoff_integrity import build_v104_handoff_integrity
from .agent_modelica_v0_10_4_real_origin_profile_replay_pack import build_v104_real_origin_profile_replay_pack
from .agent_modelica_v0_10_4_real_origin_workflow_profile_characterization import (
    build_v104_real_origin_workflow_profile_characterization,
)


def build_v104_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    replay_pack_path: str = str(DEFAULT_REAL_ORIGIN_PROFILE_REPLAY_PACK_OUT_DIR / "summary.json"),
    characterization_path: str = str(DEFAULT_REAL_ORIGIN_PROFILE_CHARACTERIZATION_OUT_DIR / "summary.json"),
    v103_closeout_path: str = str(DEFAULT_V103_CLOSEOUT_PATH),
    v103_real_origin_substrate_builder_path: str = str(DEFAULT_V103_REAL_ORIGIN_SUBSTRATE_BUILDER_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
    profile_run_count: int = PROFILE_RUN_COUNT,
) -> dict:
    handoff_path_obj = Path(handoff_integrity_path)
    replay_path_obj = Path(replay_pack_path)
    characterization_path_obj = Path(characterization_path)
    default_handoff_path = DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"
    default_replay_path = DEFAULT_REAL_ORIGIN_PROFILE_REPLAY_PACK_OUT_DIR / "summary.json"
    default_characterization_path = DEFAULT_REAL_ORIGIN_PROFILE_CHARACTERIZATION_OUT_DIR / "summary.json"

    if not handoff_path_obj.exists() or handoff_path_obj == default_handoff_path:
        build_v104_handoff_integrity(
            v103_closeout_path=v103_closeout_path,
            v103_real_origin_substrate_builder_path=v103_real_origin_substrate_builder_path,
            out_dir=str(handoff_path_obj.parent),
        )
    integrity = load_json(handoff_integrity_path)
    if integrity.get("handoff_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_10_4_REAL_ORIGIN_PROFILE_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_10_4_real_origin_profile_inputs_invalid",
                "v0_10_5_handoff_mode": "rebuild_v0_10_4_inputs_first",
                "why_this_is_interpretable_or_not": "Upstream v0.10.3 real-origin-substrate-ready handoff integrity did not pass.",
            },
            "handoff_integrity": integrity,
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.10.4 Closeout\n\n- version_decision: `v0_10_4_real_origin_profile_inputs_invalid`\n")
        return payload

    if not replay_path_obj.exists() or replay_path_obj == default_replay_path:
        build_v104_real_origin_profile_replay_pack(
            v103_real_origin_substrate_builder_path=v103_real_origin_substrate_builder_path,
            out_dir=str(replay_path_obj.parent),
            profile_run_count=profile_run_count,
        )
    if not characterization_path_obj.exists() or characterization_path_obj == default_characterization_path:
        build_v104_real_origin_workflow_profile_characterization(
            replay_pack_path=replay_pack_path,
            v103_real_origin_substrate_builder_path=v103_real_origin_substrate_builder_path,
            out_dir=str(characterization_path_obj.parent),
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
            float(characterization.get("surface_fix_only_explained_rate_pct") or 0.0) == 100.0,
            float(characterization.get("unresolved_explained_rate_pct") or 0.0) == 100.0,
            int(characterization.get("profile_non_success_unclassified_count") or 0) == 0,
        ]
    )
    profile_interpretable = bool(characterization.get("workflow_level_interpretable"))

    if repeatability_floor_met and explainability_floor_met and profile_interpretable:
        status = "PASS"
        version_decision = "v0_10_4_first_real_origin_workflow_profile_characterized"
        handoff_mode = "freeze_first_real_origin_workflow_thresholds"
        why = "The first real-origin workflow profile is stable enough to characterize, and every non-success case is explained without residual label ambiguity."
    elif runtime_valid and bool(replay_pack.get("primary_workflow_route_picture_interpretable")):
        status = "PASS"
        version_decision = "v0_10_4_first_real_origin_workflow_profile_partial"
        handoff_mode = "clarify_real_origin_profile_before_threshold_freeze"
        why = "The real-origin profile is inspectable, but repeatability or non-success explainability still stays below the frozen characterization floor."
    else:
        status = "FAIL"
        version_decision = "v0_10_4_real_origin_profile_inputs_invalid"
        handoff_mode = "rebuild_v0_10_4_inputs_first"
        why = "The replay pack stayed runtime-invalid or non-interpretable, so the real-origin profile cannot yet support threshold freezing."

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
            "non_success_label_distribution": characterization.get("non_success_label_distribution"),
            "profile_non_success_unclassified_count": characterization.get("profile_non_success_unclassified_count"),
            "v0_10_5_handoff_mode": handoff_mode,
            "why_this_is_interpretable_or_not": why,
        },
        "handoff_integrity": integrity,
        "real_origin_profile_replay_pack": replay_pack,
        "real_origin_workflow_profile_characterization": characterization,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.10.4 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- profile_run_count: `{replay_pack.get('profile_run_count')}`",
                f"- workflow_resolution_rate_pct: `{characterization.get('workflow_resolution_rate_pct')}`",
                f"- goal_alignment_rate_pct: `{characterization.get('goal_alignment_rate_pct')}`",
                f"- v0_10_5_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.10.4 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--replay-pack", default=str(DEFAULT_REAL_ORIGIN_PROFILE_REPLAY_PACK_OUT_DIR / "summary.json"))
    parser.add_argument("--characterization-path", default=str(DEFAULT_REAL_ORIGIN_PROFILE_CHARACTERIZATION_OUT_DIR / "summary.json"))
    parser.add_argument("--v103-closeout", default=str(DEFAULT_V103_CLOSEOUT_PATH))
    parser.add_argument("--v103-real-origin-substrate-builder", default=str(DEFAULT_V103_REAL_ORIGIN_SUBSTRATE_BUILDER_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    parser.add_argument("--profile-run-count", type=int, default=PROFILE_RUN_COUNT)
    args = parser.parse_args()
    payload = build_v104_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        replay_pack_path=str(args.replay_pack),
        characterization_path=str(args.characterization_path),
        v103_closeout_path=str(args.v103_closeout),
        v103_real_origin_substrate_builder_path=str(args.v103_real_origin_substrate_builder),
        out_dir=str(args.out_dir),
        profile_run_count=int(args.profile_run_count),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
