from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_9_6_common import (
    DEFAULT_REMAINING_UNCERTAINTY_CHARACTERIZATION_OUT_DIR,
    DEFAULT_V091_CLOSEOUT_PATH,
    DEFAULT_V092_CLOSEOUT_PATH,
    DEFAULT_V093_CLOSEOUT_PATH,
    DEFAULT_V094_CLOSEOUT_PATH,
    DEFAULT_V095_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v096_remaining_uncertainty_characterization(
    *,
    v095_closeout_path: str = str(DEFAULT_V095_CLOSEOUT_PATH),
    v094_closeout_path: str = str(DEFAULT_V094_CLOSEOUT_PATH),
    v093_closeout_path: str = str(DEFAULT_V093_CLOSEOUT_PATH),
    v092_closeout_path: str = str(DEFAULT_V092_CLOSEOUT_PATH),
    v091_closeout_path: str = str(DEFAULT_V091_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_REMAINING_UNCERTAINTY_CHARACTERIZATION_OUT_DIR),
) -> dict:
    v095 = load_json(v095_closeout_path)
    v094 = load_json(v094_closeout_path)
    v093 = load_json(v093_closeout_path)
    v092 = load_json(v092_closeout_path)
    v091 = load_json(v091_closeout_path)

    c095 = v095.get("conclusion") if isinstance(v095.get("conclusion"), dict) else {}
    c094 = v094.get("conclusion") if isinstance(v094.get("conclusion"), dict) else {}
    c093 = v093.get("conclusion") if isinstance(v093.get("conclusion"), dict) else {}
    c092 = v092.get("conclusion") if isinstance(v092.get("conclusion"), dict) else {}
    c091 = v091.get("conclusion") if isinstance(v091.get("conclusion"), dict) else {}

    candidate_depth = c091.get("candidate_depth_by_priority_barrier") if isinstance(c091.get("candidate_depth_by_priority_barrier"), dict) else {}
    substrate_depth = c092.get("priority_barrier_coverage_table") if isinstance(c092.get("priority_barrier_coverage_table"), dict) else {}
    priority_barriers = (
        "goal_artifact_missing_after_surface_fix",
        "dispatch_or_policy_limited_unresolved",
        "workflow_spillover_unresolved",
    )
    candidate_depth_all_gt_floor = all(int(candidate_depth.get(barrier) or 0) > 5 for barrier in priority_barriers)
    substrate_depth_all_ready = all(int(substrate_depth.get(barrier) or 0) >= 5 for barrier in priority_barriers)
    profile_unclassified_zero = int(c093.get("profile_barrier_unclassified_count") or 0) == 0
    adjudication_partial = c095.get("final_adjudication_label") == "expanded_workflow_readiness_partial_but_interpretable"
    execution_posture_preserved = bool(c095.get("execution_posture_semantics_preserved"))

    remaining_uncertainty_is_depth_limited = not (
        candidate_depth_all_gt_floor and substrate_depth_all_ready and profile_unclassified_zero and adjudication_partial
    )
    remaining_uncertainty_is_authentic_expansion_addressable = not (
        adjudication_partial
        and execution_posture_preserved
        and profile_unclassified_zero
        and substrate_depth_all_ready
        and candidate_depth_all_gt_floor
    )

    if remaining_uncertainty_is_depth_limited and remaining_uncertainty_is_authentic_expansion_addressable:
        remaining_uncertainty_status = "single_expansion_addressable_uncertainty"
        remaining_uncertainty_label = "priority_barrier_depth_still_may_be_limiting_phase_answer"
        remaining_uncertainty_scope = "bounded_authentic_barrier_depth_extension"
        expected_information_gain = "non_trivial"
    else:
        remaining_uncertainty_status = "no_expansion_addressable_uncertainty_with_meaningful_expected_gain"
        remaining_uncertainty_label = "current_authentic_expansion_chain_already_answers_phase_question"
        remaining_uncertainty_scope = "phase_governance_and_stop_condition"
        expected_information_gain = "marginal"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_remaining_uncertainty_characterization",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "remaining_uncertainty_status": remaining_uncertainty_status,
        "remaining_uncertainty_label": remaining_uncertainty_label,
        "remaining_uncertainty_scope": remaining_uncertainty_scope,
        "remaining_uncertainty_is_depth_limited": remaining_uncertainty_is_depth_limited,
        "remaining_uncertainty_is_authentic_expansion_addressable": remaining_uncertainty_is_authentic_expansion_addressable,
        "expected_information_gain": expected_information_gain,
        "candidate_depth_by_priority_barrier": candidate_depth,
        "expanded_substrate_depth_by_priority_barrier": substrate_depth,
        "baseline_classification_under_frozen_pack": c094.get("baseline_classification_under_frozen_pack"),
        "final_adjudication_label": c095.get("final_adjudication_label"),
        "execution_posture_semantics_preserved": execution_posture_preserved,
        "profile_barrier_unclassified_count": c093.get("profile_barrier_unclassified_count"),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.6 Remaining Uncertainty Characterization",
                "",
                f"- remaining_uncertainty_status: `{remaining_uncertainty_status}`",
                f"- remaining_uncertainty_label: `{remaining_uncertainty_label}`",
                f"- expected_information_gain: `{expected_information_gain}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.6 remaining uncertainty characterization.")
    parser.add_argument("--v095-closeout", default=str(DEFAULT_V095_CLOSEOUT_PATH))
    parser.add_argument("--v094-closeout", default=str(DEFAULT_V094_CLOSEOUT_PATH))
    parser.add_argument("--v093-closeout", default=str(DEFAULT_V093_CLOSEOUT_PATH))
    parser.add_argument("--v092-closeout", default=str(DEFAULT_V092_CLOSEOUT_PATH))
    parser.add_argument("--v091-closeout", default=str(DEFAULT_V091_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_REMAINING_UNCERTAINTY_CHARACTERIZATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v096_remaining_uncertainty_characterization(
        v095_closeout_path=str(args.v095_closeout),
        v094_closeout_path=str(args.v094_closeout),
        v093_closeout_path=str(args.v093_closeout),
        v092_closeout_path=str(args.v092_closeout),
        v091_closeout_path=str(args.v091_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "remaining_uncertainty_status": payload.get("remaining_uncertainty_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
