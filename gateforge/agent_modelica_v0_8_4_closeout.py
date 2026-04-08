from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_8_4_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_FROZEN_BASELINE_ADJUDICATION_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_ROUTE_INTERPRETATION_SUMMARY_OUT_DIR,
    DEFAULT_V081_CHARACTERIZATION_PATH,
    DEFAULT_V082_THRESHOLD_FREEZE_PATH,
    DEFAULT_V082_THRESHOLD_INPUT_TABLE_PATH,
    DEFAULT_V083_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_8_4_frozen_baseline_adjudication import (
    build_v084_frozen_baseline_adjudication,
)
from .agent_modelica_v0_8_4_handoff_integrity import build_v084_handoff_integrity
from .agent_modelica_v0_8_4_route_interpretation_summary import (
    build_v084_route_interpretation_summary,
)


def build_v084_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    frozen_baseline_adjudication_path: str = str(
        DEFAULT_FROZEN_BASELINE_ADJUDICATION_OUT_DIR / "summary.json"
    ),
    route_interpretation_summary_path: str = str(
        DEFAULT_ROUTE_INTERPRETATION_SUMMARY_OUT_DIR / "summary.json"
    ),
    v083_closeout_path: str = str(DEFAULT_V083_CLOSEOUT_PATH),
    v082_threshold_input_table_path: str = str(DEFAULT_V082_THRESHOLD_INPUT_TABLE_PATH),
    v082_threshold_freeze_path: str = str(DEFAULT_V082_THRESHOLD_FREEZE_PATH),
    v081_characterization_path: str = str(DEFAULT_V081_CHARACTERIZATION_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    build_v084_handoff_integrity(
        v083_closeout_path=v083_closeout_path,
        out_dir=str(Path(handoff_integrity_path).parent),
    )
    integrity = load_json(handoff_integrity_path)
    if integrity.get("status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_8_4_HANDOFF_ADJUDICATION_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_8_4_handoff_adjudication_inputs_invalid",
                "v0_8_5_handoff_mode": "rebuild_late_workflow_adjudication_inputs_first",
            },
            "handoff_integrity": integrity,
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.8.4 Closeout\n\n- version_decision: `v0_8_4_handoff_adjudication_inputs_invalid`\n")
        return payload

    build_v084_frozen_baseline_adjudication(
        v082_threshold_input_table_path=v082_threshold_input_table_path,
        v082_threshold_freeze_path=v082_threshold_freeze_path,
        out_dir=str(Path(frozen_baseline_adjudication_path).parent),
    )
    build_v084_route_interpretation_summary(
        frozen_baseline_adjudication_path=frozen_baseline_adjudication_path,
        v081_characterization_path=v081_characterization_path,
        v082_threshold_input_table_path=v082_threshold_input_table_path,
        v083_closeout_path=v083_closeout_path,
        out_dir=str(Path(route_interpretation_summary_path).parent),
    )

    adjudication = load_json(frozen_baseline_adjudication_path)
    summary = load_json(route_interpretation_summary_path)

    route_count = int(adjudication.get("adjudication_route_count") or 0)
    route = str(adjudication.get("adjudication_route") or "")
    sidecar_ok = bool(summary.get("legacy_bucket_sidecar_still_interpretable"))

    if route_count != 1 or not sidecar_ok:
        decision = "v0_8_4_handoff_adjudication_inputs_invalid"
        handoff = "rebuild_late_workflow_adjudication_inputs_first"
        status = "FAIL"
        closeout_status = "V0_8_4_HANDOFF_ADJUDICATION_INPUTS_INVALID"
    elif route == "workflow_readiness_supported":
        decision = "v0_8_4_workflow_readiness_supported"
        handoff = "prepare_workflow_phase_closeout_or_promotion"
        status = "PASS"
        closeout_status = "V0_8_4_WORKFLOW_READINESS_SUPPORTED"
    elif route == "workflow_readiness_partial_but_interpretable":
        decision = "v0_8_4_workflow_readiness_partial_but_interpretable"
        handoff = "decide_if_one_more_same_logic_refinement_is_worth_it"
        status = "PASS"
        closeout_status = "V0_8_4_WORKFLOW_READINESS_PARTIAL_BUT_INTERPRETABLE"
    elif route == "fallback_to_error_distribution_hardening_needed":
        decision = "v0_8_4_fallback_to_error_distribution_hardening_needed"
        handoff = "design_authenticity_constrained_barrier_aware_expansion"
        status = "PASS"
        closeout_status = "V0_8_4_FALLBACK_TO_ERROR_DISTRIBUTION_HARDENING_NEEDED"
    else:
        decision = "v0_8_4_handoff_adjudication_inputs_invalid"
        handoff = "rebuild_late_workflow_adjudication_inputs_first"
        status = "FAIL"
        closeout_status = "V0_8_4_HANDOFF_ADJUDICATION_INPUTS_INVALID"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": closeout_status,
        "conclusion": {
            "version_decision": decision,
            "adjudication_route": route,
            "adjudication_route_count": route_count,
            "legacy_bucket_sidecar_still_interpretable": sidecar_ok,
            "dominant_workflow_barrier_family": summary.get("dominant_workflow_barrier_family"),
            "why_supported_is_or_is_not_reached": summary.get("why_supported_is_or_is_not_reached"),
            "why_fallback_is_or_is_not_triggered": summary.get("why_fallback_is_or_is_not_triggered"),
            "v0_8_5_handoff_mode": handoff,
        },
        "handoff_integrity": integrity,
        "frozen_baseline_adjudication": adjudication,
        "route_interpretation_summary": summary,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.8.4 Closeout",
                "",
                f"- version_decision: `{decision}`",
                f"- adjudication_route: `{route}`",
                f"- dominant_workflow_barrier_family: `{summary.get('dominant_workflow_barrier_family')}`",
                f"- v0_8_5_handoff_mode: `{handoff}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.8.4 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument(
        "--frozen-baseline-adjudication",
        default=str(DEFAULT_FROZEN_BASELINE_ADJUDICATION_OUT_DIR / "summary.json"),
    )
    parser.add_argument(
        "--route-interpretation-summary",
        default=str(DEFAULT_ROUTE_INTERPRETATION_SUMMARY_OUT_DIR / "summary.json"),
    )
    parser.add_argument("--v083-closeout", default=str(DEFAULT_V083_CLOSEOUT_PATH))
    parser.add_argument("--v082-threshold-input-table", default=str(DEFAULT_V082_THRESHOLD_INPUT_TABLE_PATH))
    parser.add_argument("--v082-threshold-freeze", default=str(DEFAULT_V082_THRESHOLD_FREEZE_PATH))
    parser.add_argument("--v081-characterization", default=str(DEFAULT_V081_CHARACTERIZATION_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v084_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        frozen_baseline_adjudication_path=str(args.frozen_baseline_adjudication),
        route_interpretation_summary_path=str(args.route_interpretation_summary),
        v083_closeout_path=str(args.v083_closeout),
        v082_threshold_input_table_path=str(args.v082_threshold_input_table),
        v082_threshold_freeze_path=str(args.v082_threshold_freeze),
        v081_characterization_path=str(args.v081_characterization),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
