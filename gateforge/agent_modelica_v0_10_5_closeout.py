from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_10_5_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR,
    DEFAULT_THRESHOLD_PACK_OUT_DIR,
    DEFAULT_V104_CHARACTERIZATION_PATH,
    DEFAULT_V104_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_10_5_handoff_integrity import build_v105_handoff_integrity
from .agent_modelica_v0_10_5_real_origin_threshold_input_table import build_v105_real_origin_threshold_input_table
from .agent_modelica_v0_10_5_first_real_origin_threshold_pack import build_v105_first_real_origin_threshold_pack


def build_v105_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    threshold_input_table_path: str = str(DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR / "summary.json"),
    threshold_pack_path: str = str(DEFAULT_THRESHOLD_PACK_OUT_DIR / "summary.json"),
    v104_closeout_path: str = str(DEFAULT_V104_CLOSEOUT_PATH),
    v104_characterization_path: str = str(DEFAULT_V104_CHARACTERIZATION_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    handoff_path_obj = Path(handoff_integrity_path)
    input_table_path_obj = Path(threshold_input_table_path)
    pack_path_obj = Path(threshold_pack_path)

    # Build sub-artifacts if not already present
    if not handoff_path_obj.exists() or handoff_path_obj == DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json":
        build_v105_handoff_integrity(
            v104_closeout_path=v104_closeout_path,
            out_dir=str(handoff_path_obj.parent),
        )
    integrity = load_json(handoff_integrity_path)

    # Route table: Step 1 failure short-circuits everything
    if integrity.get("handoff_integrity_status") != "PASS":
        version_decision = "v0_10_5_real_origin_threshold_inputs_invalid"
        handoff_mode = "rebuild_v0_10_5_inputs_first"
        status = "FAIL"
        why = "Upstream v0.10.4 handoff integrity did not pass; threshold freeze cannot proceed."
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": status,
            "closeout_status": version_decision.upper(),
            "conclusion": {
                "version_decision": version_decision,
                "v0_10_6_handoff_mode": handoff_mode,
                "why_this_is_interpretable_or_not": why,
            },
            "handoff_integrity": integrity,
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", payload)
        write_text(
            out_root / "summary.md",
            f"# v0.10.5 Closeout\n\n- version_decision: `{version_decision}`\n",
        )
        return payload

    # Build threshold input table
    if not input_table_path_obj.exists() or input_table_path_obj == DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR / "summary.json":
        build_v105_real_origin_threshold_input_table(
            v104_characterization_path=v104_characterization_path,
            out_dir=str(input_table_path_obj.parent),
        )
    # Build threshold pack
    if not pack_path_obj.exists() or pack_path_obj == DEFAULT_THRESHOLD_PACK_OUT_DIR / "summary.json":
        build_v105_first_real_origin_threshold_pack(
            threshold_input_table_path=threshold_input_table_path,
            out_dir=str(pack_path_obj.parent),
        )

    input_table = load_json(threshold_input_table_path)
    pack = load_json(threshold_pack_path)

    anti_tautology_pass = bool(pack.get("anti_tautology_pass"))
    integer_safe_pass = bool(pack.get("integer_safe_pass"))
    execution_posture_ok = bool(pack.get("execution_posture_semantics_preserved"))
    baseline_classification = str(pack.get("baseline_classification_under_frozen_pack") or "")
    baseline_is_partial = baseline_classification == "real_origin_workflow_readiness_partial_but_interpretable"
    baseline_not_supported = baseline_classification != "real_origin_workflow_readiness_supported"

    # Route table (Step 4)
    if (
        anti_tautology_pass
        and integer_safe_pass
        and baseline_is_partial
        and execution_posture_ok
    ):
        version_decision = "v0_10_5_first_real_origin_workflow_thresholds_frozen"
        handoff_mode = "adjudicate_first_real_origin_workflow_readiness_against_frozen_thresholds"
        status = "PASS"
        why = (
            "The first real-origin workflow threshold pack is structurally frozen, "
            "anti-tautology and integer-safe checks pass, the v0.10.4 baseline classifies "
            "as partial_but_interpretable, and execution-posture semantics are preserved."
        )
    elif anti_tautology_pass and integer_safe_pass and baseline_not_supported:
        version_decision = "v0_10_5_first_real_origin_workflow_thresholds_partial"
        handoff_mode = "repair_threshold_pack_before_adjudication"
        status = "PASS"
        why = (
            "Threshold-freeze intent is valid and the baseline does not classify as supported, "
            "but at least one full-route condition (baseline=partial or execution-posture) "
            "remains under-specified."
        )
    else:
        version_decision = "v0_10_5_real_origin_threshold_inputs_invalid"
        handoff_mode = "rebuild_v0_10_5_inputs_first"
        status = "FAIL"
        why = (
            "Anti-tautology or integer-safe check failed, or the baseline classified as supported; "
            "the threshold pack cannot be frozen."
        )

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": version_decision.upper(),
        "conclusion": {
            "version_decision": version_decision,
            "workflow_resolution_case_count": input_table.get("workflow_resolution_case_count"),
            "goal_alignment_case_count": input_table.get("goal_alignment_case_count"),
            "surface_fix_only_case_count": input_table.get("surface_fix_only_case_count"),
            "unresolved_case_count": input_table.get("unresolved_case_count"),
            "baseline_classification_under_frozen_pack": baseline_classification,
            "anti_tautology_pass": anti_tautology_pass,
            "integer_safe_pass": integer_safe_pass,
            "v0_10_6_handoff_mode": handoff_mode,
            "why_this_is_interpretable_or_not": why,
        },
        "handoff_integrity": integrity,
        "real_origin_threshold_input_table": input_table,
        "first_real_origin_threshold_pack": pack,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.10.5 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- baseline_classification_under_frozen_pack: `{baseline_classification}`",
                f"- anti_tautology_pass: `{anti_tautology_pass}`",
                f"- integer_safe_pass: `{integer_safe_pass}`",
                f"- v0_10_6_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.10.5 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument(
        "--threshold-input-table", default=str(DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR / "summary.json")
    )
    parser.add_argument("--threshold-pack", default=str(DEFAULT_THRESHOLD_PACK_OUT_DIR / "summary.json"))
    parser.add_argument("--v104-closeout", default=str(DEFAULT_V104_CLOSEOUT_PATH))
    parser.add_argument("--v104-characterization", default=str(DEFAULT_V104_CHARACTERIZATION_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v105_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        threshold_input_table_path=str(args.threshold_input_table),
        threshold_pack_path=str(args.threshold_pack),
        v104_closeout_path=str(args.v104_closeout),
        v104_characterization_path=str(args.v104_characterization),
        out_dir=str(args.out_dir),
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
