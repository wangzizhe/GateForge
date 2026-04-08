from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_8_6_common import (
    DEFAULT_STOP_CONDITION_OUT_DIR,
    DEFAULT_V080_CLOSEOUT_PATH,
    DEFAULT_V081_CLOSEOUT_PATH,
    DEFAULT_V082_CLOSEOUT_PATH,
    DEFAULT_V083_CLOSEOUT_PATH,
    DEFAULT_V084_CLOSEOUT_PATH,
    DEFAULT_V085_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v086_stop_condition(
    *,
    v080_closeout_path: str = str(DEFAULT_V080_CLOSEOUT_PATH),
    v081_closeout_path: str = str(DEFAULT_V081_CLOSEOUT_PATH),
    v082_closeout_path: str = str(DEFAULT_V082_CLOSEOUT_PATH),
    v083_closeout_path: str = str(DEFAULT_V083_CLOSEOUT_PATH),
    v084_closeout_path: str = str(DEFAULT_V084_CLOSEOUT_PATH),
    v085_closeout_path: str = str(DEFAULT_V085_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_STOP_CONDITION_OUT_DIR),
) -> dict:
    v080 = load_json(v080_closeout_path)
    v081 = load_json(v081_closeout_path)
    v082 = load_json(v082_closeout_path)
    v083 = load_json(v083_closeout_path)
    v084 = load_json(v084_closeout_path)
    v085 = load_json(v085_closeout_path)

    c080 = v080.get("conclusion") or {}
    c081 = v081.get("conclusion") or {}
    c082 = v082.get("conclusion") or {}
    c083 = v083.get("conclusion") or {}
    c084 = v084.get("conclusion") or {}
    c085 = v085.get("conclusion") or {}

    workflow_proximal_substrate_supported = c080.get("version_decision") == "v0_8_0_workflow_proximal_substrate_ready"
    workflow_profile_characterized_and_stable = c081.get("version_decision") == "v0_8_1_workflow_readiness_profile_characterized"
    thresholds_frozen_and_validated = (
        c082.get("version_decision") == "v0_8_2_workflow_readiness_thresholds_frozen"
        and c083.get("version_decision") == "v0_8_3_threshold_pack_validated"
    )
    late_adjudication_route_recorded = (
        c084.get("version_decision") == "v0_8_4_workflow_readiness_partial_but_interpretable"
        and c084.get("adjudication_route") == "workflow_readiness_partial_but_interpretable"
        and int(c084.get("adjudication_route_count") or 0) == 1
    )
    same_logic_refinement_explicitly_not_worth_it = (
        c085.get("version_decision") == "v0_8_5_same_logic_refinement_not_worth_it"
    )
    legacy_sidecar_remains_interpretable = bool(c084.get("legacy_bucket_sidecar_still_interpretable"))
    phase_primary_question_answered_enough_for_handoff = all(
        [
            late_adjudication_route_recorded,
            same_logic_refinement_explicitly_not_worth_it,
            legacy_sidecar_remains_interpretable,
        ]
    )

    base_six = [
        workflow_proximal_substrate_supported,
        workflow_profile_characterized_and_stable,
        thresholds_frozen_and_validated,
        late_adjudication_route_recorded,
        same_logic_refinement_explicitly_not_worth_it,
        legacy_sidecar_remains_interpretable,
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
        "workflow_proximal_substrate_supported": workflow_proximal_substrate_supported,
        "workflow_profile_characterized_and_stable": workflow_profile_characterized_and_stable,
        "thresholds_frozen_and_validated": thresholds_frozen_and_validated,
        "late_adjudication_route_recorded": late_adjudication_route_recorded,
        "same_logic_refinement_explicitly_not_worth_it": same_logic_refinement_explicitly_not_worth_it,
        "legacy_sidecar_remains_interpretable": legacy_sidecar_remains_interpretable,
        "phase_primary_question_answered_enough_for_handoff": phase_primary_question_answered_enough_for_handoff,
        "phase_stop_condition_status": phase_stop_condition_status,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.8.6 Stop Condition",
                "",
                f"- phase_stop_condition_status: `{phase_stop_condition_status}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.8.6 stop condition artifact.")
    parser.add_argument("--v080-closeout", default=str(DEFAULT_V080_CLOSEOUT_PATH))
    parser.add_argument("--v081-closeout", default=str(DEFAULT_V081_CLOSEOUT_PATH))
    parser.add_argument("--v082-closeout", default=str(DEFAULT_V082_CLOSEOUT_PATH))
    parser.add_argument("--v083-closeout", default=str(DEFAULT_V083_CLOSEOUT_PATH))
    parser.add_argument("--v084-closeout", default=str(DEFAULT_V084_CLOSEOUT_PATH))
    parser.add_argument("--v085-closeout", default=str(DEFAULT_V085_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_STOP_CONDITION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v086_stop_condition(
        v080_closeout_path=str(args.v080_closeout),
        v081_closeout_path=str(args.v081_closeout),
        v082_closeout_path=str(args.v082_closeout),
        v083_closeout_path=str(args.v083_closeout),
        v084_closeout_path=str(args.v084_closeout),
        v085_closeout_path=str(args.v085_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "phase_stop_condition_status": payload.get("phase_stop_condition_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
