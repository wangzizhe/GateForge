from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_9_7_common import (
    DEFAULT_STOP_CONDITION_OUT_DIR,
    DEFAULT_V090_CLOSEOUT_PATH,
    DEFAULT_V091_CLOSEOUT_PATH,
    DEFAULT_V092_CLOSEOUT_PATH,
    DEFAULT_V093_CLOSEOUT_PATH,
    DEFAULT_V094_CLOSEOUT_PATH,
    DEFAULT_V095_CLOSEOUT_PATH,
    DEFAULT_V096_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v097_stop_condition(
    *,
    v090_closeout_path: str = str(DEFAULT_V090_CLOSEOUT_PATH),
    v091_closeout_path: str = str(DEFAULT_V091_CLOSEOUT_PATH),
    v092_closeout_path: str = str(DEFAULT_V092_CLOSEOUT_PATH),
    v093_closeout_path: str = str(DEFAULT_V093_CLOSEOUT_PATH),
    v094_closeout_path: str = str(DEFAULT_V094_CLOSEOUT_PATH),
    v095_closeout_path: str = str(DEFAULT_V095_CLOSEOUT_PATH),
    v096_closeout_path: str = str(DEFAULT_V096_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_STOP_CONDITION_OUT_DIR),
) -> dict:
    v090 = load_json(v090_closeout_path)
    v091 = load_json(v091_closeout_path)
    v092 = load_json(v092_closeout_path)
    v093 = load_json(v093_closeout_path)
    v094 = load_json(v094_closeout_path)
    v095 = load_json(v095_closeout_path)
    v096 = load_json(v096_closeout_path)

    c090 = v090.get("conclusion") or {}
    c091 = v091.get("conclusion") or {}
    c092 = v092.get("conclusion") or {}
    c093 = v093.get("conclusion") or {}
    c094 = v094.get("conclusion") or {}
    c095 = v095.get("conclusion") or {}
    c096 = v096.get("conclusion") or {}

    authenticity_governance_frozen_and_preserved = (
        c090.get("version_decision") == "v0_9_0_candidate_pool_governance_partial"
        and bool(c090.get("needs_additional_real_sources"))
        and str(c090.get("v0_9_1_handoff_mode") or "") == "expand_real_candidate_pool_before_substrate_freeze"
    )
    expanded_real_candidate_pool_established = (
        c091.get("version_decision") == "v0_9_1_real_candidate_source_expansion_ready"
        and int(c091.get("post_expansion_candidate_pool_count") or 0) >= 20
        and all(int(v) >= 5 for v in (c091.get("candidate_depth_by_priority_barrier") or {}).values())
    )
    expanded_authentic_substrate_frozen = (
        c092.get("version_decision") == "v0_9_2_first_expanded_authentic_workflow_substrate_ready"
        and int(c092.get("expanded_substrate_size") or 0) >= 19
        and all(int(v) >= 5 for v in (c092.get("priority_barrier_coverage_table") or {}).values())
    )
    expanded_profile_characterized_and_explainable = (
        c093.get("version_decision") == "v0_9_3_expanded_workflow_profile_characterized"
        and int(c093.get("profile_barrier_unclassified_count") or 0) == 0
    )
    thresholds_frozen_and_formal_adjudication_recorded = (
        c094.get("version_decision") == "v0_9_4_expanded_workflow_thresholds_frozen"
        and bool(c094.get("anti_tautology_pass"))
        and bool(c094.get("integer_safe_pass"))
        and c095.get("version_decision") == "v0_9_5_expanded_workflow_readiness_partial_but_interpretable"
        and int(c095.get("adjudication_route_count") or 0) == 1
    )
    more_authentic_expansion_explicitly_not_worth_it = (
        c096.get("version_decision") == "v0_9_6_more_authentic_expansion_not_worth_it"
        and str(c096.get("remaining_uncertainty_status") or "")
        == "no_expansion_addressable_uncertainty_with_meaningful_expected_gain"
        and str(c096.get("expected_information_gain") or "") == "marginal"
    )
    phase_primary_question_answered_enough_for_handoff = all(
        [
            expanded_profile_characterized_and_explainable,
            thresholds_frozen_and_formal_adjudication_recorded,
            more_authentic_expansion_explicitly_not_worth_it,
            str(c095.get("final_adjudication_label") or "") == "expanded_workflow_readiness_partial_but_interpretable",
        ]
    )

    base_six = [
        authenticity_governance_frozen_and_preserved,
        expanded_real_candidate_pool_established,
        expanded_authentic_substrate_frozen,
        expanded_profile_characterized_and_explainable,
        thresholds_frozen_and_formal_adjudication_recorded,
        more_authentic_expansion_explicitly_not_worth_it,
    ]
    if all(base_six) and phase_primary_question_answered_enough_for_handoff:
        phase_stop_condition_status = "met"
    elif all(base_six) and not phase_primary_question_answered_enough_for_handoff:
        phase_stop_condition_status = "nearly_complete_with_caveat"
    else:
        phase_stop_condition_status = "not_ready_for_closeout"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_stop_condition",
        "generated_at_utc": now_utc(),
        "status": "PASS" if phase_stop_condition_status in {"met", "nearly_complete_with_caveat"} else "FAIL",
        "authenticity_governance_frozen_and_preserved": authenticity_governance_frozen_and_preserved,
        "expanded_real_candidate_pool_established": expanded_real_candidate_pool_established,
        "expanded_authentic_substrate_frozen": expanded_authentic_substrate_frozen,
        "expanded_profile_characterized_and_explainable": expanded_profile_characterized_and_explainable,
        "thresholds_frozen_and_formal_adjudication_recorded": thresholds_frozen_and_formal_adjudication_recorded,
        "more_authentic_expansion_explicitly_not_worth_it": more_authentic_expansion_explicitly_not_worth_it,
        "phase_primary_question_answered_enough_for_handoff": phase_primary_question_answered_enough_for_handoff,
        "phase_stop_condition_status": phase_stop_condition_status,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.7 Stop Condition",
                "",
                f"- phase_stop_condition_status: `{phase_stop_condition_status}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.7 stop condition artifact.")
    parser.add_argument("--v090-closeout", default=str(DEFAULT_V090_CLOSEOUT_PATH))
    parser.add_argument("--v091-closeout", default=str(DEFAULT_V091_CLOSEOUT_PATH))
    parser.add_argument("--v092-closeout", default=str(DEFAULT_V092_CLOSEOUT_PATH))
    parser.add_argument("--v093-closeout", default=str(DEFAULT_V093_CLOSEOUT_PATH))
    parser.add_argument("--v094-closeout", default=str(DEFAULT_V094_CLOSEOUT_PATH))
    parser.add_argument("--v095-closeout", default=str(DEFAULT_V095_CLOSEOUT_PATH))
    parser.add_argument("--v096-closeout", default=str(DEFAULT_V096_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_STOP_CONDITION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v097_stop_condition(
        v090_closeout_path=str(args.v090_closeout),
        v091_closeout_path=str(args.v091_closeout),
        v092_closeout_path=str(args.v092_closeout),
        v093_closeout_path=str(args.v093_closeout),
        v094_closeout_path=str(args.v094_closeout),
        v095_closeout_path=str(args.v095_closeout),
        v096_closeout_path=str(args.v096_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "phase_stop_condition_status": payload.get("phase_stop_condition_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
