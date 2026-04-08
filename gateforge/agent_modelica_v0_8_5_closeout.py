from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_8_5_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_REFINEMENT_WORTH_IT_SUMMARY_OUT_DIR,
    DEFAULT_REMAINING_GAP_CHARACTERIZATION_OUT_DIR,
    DEFAULT_V081_CLOSEOUT_PATH,
    DEFAULT_V082_THRESHOLD_FREEZE_PATH,
    DEFAULT_V084_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_8_5_handoff_integrity import build_v085_handoff_integrity
from .agent_modelica_v0_8_5_refinement_worth_it_summary import (
    build_v085_refinement_worth_it_summary,
)
from .agent_modelica_v0_8_5_remaining_gap_characterization import (
    build_v085_remaining_gap_characterization,
)


def build_v085_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    remaining_gap_characterization_path: str = str(
        DEFAULT_REMAINING_GAP_CHARACTERIZATION_OUT_DIR / "summary.json"
    ),
    refinement_worth_it_summary_path: str = str(
        DEFAULT_REFINEMENT_WORTH_IT_SUMMARY_OUT_DIR / "summary.json"
    ),
    v084_closeout_path: str = str(DEFAULT_V084_CLOSEOUT_PATH),
    v081_closeout_path: str = str(DEFAULT_V081_CLOSEOUT_PATH),
    v082_threshold_freeze_path: str = str(DEFAULT_V082_THRESHOLD_FREEZE_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    build_v085_handoff_integrity(
        v084_closeout_path=v084_closeout_path,
        out_dir=str(Path(handoff_integrity_path).parent),
    )
    integrity = load_json(handoff_integrity_path)
    if integrity.get("status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_8_5_HANDOFF_DECISION_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_8_5_handoff_decision_inputs_invalid",
                "v0_8_6_handoff_mode": "rebuild_workflow_refinement_decision_inputs_first",
            },
            "handoff_integrity": integrity,
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.8.5 Closeout\n\n- version_decision: `v0_8_5_handoff_decision_inputs_invalid`\n")
        return payload

    build_v085_remaining_gap_characterization(
        v084_closeout_path=v084_closeout_path,
        v081_closeout_path=v081_closeout_path,
        v082_threshold_freeze_path=v082_threshold_freeze_path,
        out_dir=str(Path(remaining_gap_characterization_path).parent),
    )
    build_v085_refinement_worth_it_summary(
        remaining_gap_characterization_path=remaining_gap_characterization_path,
        out_dir=str(Path(refinement_worth_it_summary_path).parent),
    )

    gap = load_json(remaining_gap_characterization_path)
    summary = load_json(refinement_worth_it_summary_path)
    v084 = load_json(v084_closeout_path)
    route = ((v084.get("conclusion") or {}).get("adjudication_route"))

    justified = all(
        [
            route == "workflow_readiness_partial_but_interpretable",
            gap.get("remaining_gap_status") == "single_refinable_gap",
            bool(gap.get("remaining_gap_is_threshold_proximal")),
            bool(gap.get("remaining_gap_is_same_logic_addressable")),
            gap.get("expected_information_gain") == "non_trivial",
        ]
    )

    invalid = any(
        [
            route != "workflow_readiness_partial_but_interpretable",
            not str(gap.get("remaining_gap_status") or ""),
            not str(summary.get("why_one_more_same_logic_refinement_is_or_is_not_justified") or ""),
        ]
    )

    if invalid:
        decision = "v0_8_5_handoff_decision_inputs_invalid"
        handoff = "rebuild_workflow_refinement_decision_inputs_first"
        status = "FAIL"
        closeout_status = "V0_8_5_HANDOFF_DECISION_INPUTS_INVALID"
    elif justified:
        decision = "v0_8_5_one_more_same_logic_refinement_justified"
        handoff = "run_one_last_same_logic_workflow_refinement"
        status = "PASS"
        closeout_status = "V0_8_5_ONE_MORE_SAME_LOGIC_REFINEMENT_JUSTIFIED"
    else:
        decision = "v0_8_5_same_logic_refinement_not_worth_it"
        handoff = "prepare_v0_8_phase_closeout"
        status = "PASS"
        closeout_status = "V0_8_5_SAME_LOGIC_REFINEMENT_NOT_WORTH_IT"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": closeout_status,
        "conclusion": {
            "version_decision": decision,
            "remaining_gap_status": gap.get("remaining_gap_status"),
            "remaining_gap_label": gap.get("remaining_gap_label"),
            "remaining_gap_magnitude_pct": gap.get("remaining_gap_magnitude_pct"),
            "remaining_gap_is_threshold_proximal": gap.get("remaining_gap_is_threshold_proximal"),
            "remaining_gap_is_same_logic_addressable": gap.get("remaining_gap_is_same_logic_addressable"),
            "expected_information_gain": gap.get("expected_information_gain"),
            "why_one_more_same_logic_refinement_is_or_is_not_justified": summary.get(
                "why_one_more_same_logic_refinement_is_or_is_not_justified"
            ),
            "v0_8_6_handoff_mode": handoff,
        },
        "handoff_integrity": integrity,
        "remaining_gap_characterization": gap,
        "refinement_worth_it_summary": summary,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.8.5 Closeout",
                "",
                f"- version_decision: `{decision}`",
                f"- remaining_gap_status: `{gap.get('remaining_gap_status')}`",
                f"- expected_information_gain: `{gap.get('expected_information_gain')}`",
                f"- v0_8_6_handoff_mode: `{handoff}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.8.5 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument(
        "--remaining-gap-characterization",
        default=str(DEFAULT_REMAINING_GAP_CHARACTERIZATION_OUT_DIR / "summary.json"),
    )
    parser.add_argument(
        "--refinement-worth-it-summary",
        default=str(DEFAULT_REFINEMENT_WORTH_IT_SUMMARY_OUT_DIR / "summary.json"),
    )
    parser.add_argument("--v084-closeout", default=str(DEFAULT_V084_CLOSEOUT_PATH))
    parser.add_argument("--v081-closeout", default=str(DEFAULT_V081_CLOSEOUT_PATH))
    parser.add_argument("--v082-threshold-freeze", default=str(DEFAULT_V082_THRESHOLD_FREEZE_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v085_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        remaining_gap_characterization_path=str(args.remaining_gap_characterization),
        refinement_worth_it_summary_path=str(args.refinement_worth_it_summary),
        v084_closeout_path=str(args.v084_closeout),
        v081_closeout_path=str(args.v081_closeout),
        v082_threshold_freeze_path=str(args.v082_threshold_freeze),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
