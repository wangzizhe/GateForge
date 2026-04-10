from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_10_8_common import (
    DEFAULT_STOP_CONDITION_OUT_DIR,
    DEFAULT_V100_CLOSEOUT_PATH,
    DEFAULT_V101_CLOSEOUT_PATH,
    DEFAULT_V102_CLOSEOUT_PATH,
    DEFAULT_V103_CLOSEOUT_PATH,
    DEFAULT_V104_CLOSEOUT_PATH,
    DEFAULT_V105_CLOSEOUT_PATH,
    DEFAULT_V106_CLOSEOUT_PATH,
    DEFAULT_V107_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v108_stop_condition(
    *,
    v100_closeout_path: str = str(DEFAULT_V100_CLOSEOUT_PATH),
    v101_closeout_path: str = str(DEFAULT_V101_CLOSEOUT_PATH),
    v102_closeout_path: str = str(DEFAULT_V102_CLOSEOUT_PATH),
    v103_closeout_path: str = str(DEFAULT_V103_CLOSEOUT_PATH),
    v104_closeout_path: str = str(DEFAULT_V104_CLOSEOUT_PATH),
    v105_closeout_path: str = str(DEFAULT_V105_CLOSEOUT_PATH),
    v106_closeout_path: str = str(DEFAULT_V106_CLOSEOUT_PATH),
    v107_closeout_path: str = str(DEFAULT_V107_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_STOP_CONDITION_OUT_DIR),
) -> dict:
    v100 = load_json(v100_closeout_path)
    v101 = load_json(v101_closeout_path)
    v102 = load_json(v102_closeout_path)
    v103 = load_json(v103_closeout_path)
    v104 = load_json(v104_closeout_path)
    v105 = load_json(v105_closeout_path)
    v106 = load_json(v106_closeout_path)
    v107 = load_json(v107_closeout_path)

    c100 = v100.get("conclusion") or {}
    c101 = v101.get("conclusion") or {}
    c102 = v102.get("conclusion") or {}
    c103 = v103.get("conclusion") or {}
    c104 = v104.get("conclusion") or {}
    c105 = v105.get("conclusion") or {}
    c106 = v106.get("conclusion") or {}
    c107 = v107.get("conclusion") or {}

    real_origin_governance_frozen_and_preserved = (
        c100.get("version_decision") == "v0_10_0_real_origin_candidate_governance_partial"
        and str(c100.get("v0_10_1_handoff_mode") or "") == "expand_real_origin_candidate_pool_before_substrate_freeze"
    )
    real_origin_candidate_pool_established = (
        c102.get("version_decision") == "v0_10_2_real_origin_source_expansion_ready"
        and int(c102.get("post_expansion_mainline_real_origin_candidate_count") or 0) >= 12
        and float(c102.get("max_single_source_share_pct") or 0.0) <= 50.0
    )
    real_origin_substrate_frozen = (
        c103.get("version_decision") == "v0_10_3_first_real_origin_workflow_substrate_ready"
        and int(c103.get("real_origin_substrate_size") or 0) >= 12
        and float(c103.get("max_single_source_share_pct") or 0.0) <= 50.0
        and str(c103.get("real_origin_substrate_admission_status") or "") == "ready"
    )
    real_origin_profile_characterized_and_explainable = (
        c104.get("version_decision") == "v0_10_4_first_real_origin_workflow_profile_characterized"
        and int(c104.get("profile_non_success_unclassified_count") or 0) == 0
    )
    thresholds_frozen_and_formal_adjudication_recorded = (
        c105.get("version_decision") == "v0_10_5_first_real_origin_workflow_thresholds_frozen"
        and bool(c105.get("anti_tautology_pass"))
        and bool(c105.get("integer_safe_pass"))
        and str(c106.get("version_decision") or "").startswith("v0_10_6_first_real_origin_workflow_readiness_")
        and str(c106.get("final_adjudication_label") or "")
        in {
            "real_origin_workflow_readiness_partial_but_interpretable",
            "real_origin_workflow_readiness_supported",
        }
    )
    more_bounded_real_origin_step_explicitly_not_worth_it = (
        c107.get("version_decision") == "v0_10_7_more_bounded_real_origin_step_not_worth_it"
        and str(c107.get("remaining_uncertainty_status") or "") == "no_phase_relevant_uncertainty_remaining"
        and str(c107.get("expected_information_gain") or "") == "marginal"
        and str(c107.get("proposed_next_step_kind") or "") == "none"
    )
    phase_primary_question_answered_enough_for_handoff = all(
        [
            real_origin_profile_characterized_and_explainable,
            thresholds_frozen_and_formal_adjudication_recorded,
            more_bounded_real_origin_step_explicitly_not_worth_it,
            str(c106.get("final_adjudication_label") or "")
            in {
                "real_origin_workflow_readiness_partial_but_interpretable",
                "real_origin_workflow_readiness_supported",
            },
        ]
    )

    base_six = [
        real_origin_governance_frozen_and_preserved,
        real_origin_candidate_pool_established,
        real_origin_substrate_frozen,
        real_origin_profile_characterized_and_explainable,
        thresholds_frozen_and_formal_adjudication_recorded,
        more_bounded_real_origin_step_explicitly_not_worth_it,
    ]
    final_is_supported = str(c106.get("final_adjudication_label") or "") == "real_origin_workflow_readiness_supported"
    final_is_partial = str(c106.get("final_adjudication_label") or "") == "real_origin_workflow_readiness_partial_but_interpretable"

    if all(base_six) and phase_primary_question_answered_enough_for_handoff and final_is_supported:
        phase_stop_condition_status = "met"
    elif all(base_six) and phase_primary_question_answered_enough_for_handoff and final_is_partial:
        phase_stop_condition_status = "nearly_complete_with_caveat"
    else:
        phase_stop_condition_status = "not_ready_for_closeout"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_stop_condition",
        "generated_at_utc": now_utc(),
        "status": "PASS" if phase_stop_condition_status in {"met", "nearly_complete_with_caveat"} else "FAIL",
        "real_origin_governance_frozen_and_preserved": real_origin_governance_frozen_and_preserved,
        "real_origin_candidate_pool_established": real_origin_candidate_pool_established,
        "real_origin_substrate_frozen": real_origin_substrate_frozen,
        "real_origin_profile_characterized_and_explainable": real_origin_profile_characterized_and_explainable,
        "thresholds_frozen_and_formal_adjudication_recorded": thresholds_frozen_and_formal_adjudication_recorded,
        "more_bounded_real_origin_step_explicitly_not_worth_it": more_bounded_real_origin_step_explicitly_not_worth_it,
        "phase_primary_question_answered_enough_for_handoff": phase_primary_question_answered_enough_for_handoff,
        "phase_stop_condition_status": phase_stop_condition_status,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.10.8 Stop Condition",
                "",
                f"- phase_stop_condition_status: `{phase_stop_condition_status}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.10.8 stop condition artifact.")
    parser.add_argument("--v100-closeout", default=str(DEFAULT_V100_CLOSEOUT_PATH))
    parser.add_argument("--v101-closeout", default=str(DEFAULT_V101_CLOSEOUT_PATH))
    parser.add_argument("--v102-closeout", default=str(DEFAULT_V102_CLOSEOUT_PATH))
    parser.add_argument("--v103-closeout", default=str(DEFAULT_V103_CLOSEOUT_PATH))
    parser.add_argument("--v104-closeout", default=str(DEFAULT_V104_CLOSEOUT_PATH))
    parser.add_argument("--v105-closeout", default=str(DEFAULT_V105_CLOSEOUT_PATH))
    parser.add_argument("--v106-closeout", default=str(DEFAULT_V106_CLOSEOUT_PATH))
    parser.add_argument("--v107-closeout", default=str(DEFAULT_V107_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_STOP_CONDITION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v108_stop_condition(
        v100_closeout_path=str(args.v100_closeout),
        v101_closeout_path=str(args.v101_closeout),
        v102_closeout_path=str(args.v102_closeout),
        v103_closeout_path=str(args.v103_closeout),
        v104_closeout_path=str(args.v104_closeout),
        v105_closeout_path=str(args.v105_closeout),
        v106_closeout_path=str(args.v106_closeout),
        v107_closeout_path=str(args.v107_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "phase_stop_condition_status": payload.get("phase_stop_condition_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
