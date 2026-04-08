from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_8_2_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_THRESHOLD_FREEZE_OUT_DIR,
    DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR,
    DEFAULT_V081_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_8_2_handoff_integrity import build_v082_handoff_integrity
from .agent_modelica_v0_8_2_threshold_freeze import build_v082_threshold_freeze
from .agent_modelica_v0_8_2_threshold_input_table import build_v082_threshold_input_table


def build_v082_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    threshold_input_table_path: str = str(DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR / "summary.json"),
    threshold_freeze_path: str = str(DEFAULT_THRESHOLD_FREEZE_OUT_DIR / "summary.json"),
    v081_closeout_path: str = str(DEFAULT_V081_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    build_v082_handoff_integrity(
        v081_closeout_path=v081_closeout_path,
        out_dir=str(Path(handoff_integrity_path).parent),
    )
    integrity = load_json(handoff_integrity_path)
    if integrity.get("status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_8_2_HANDOFF_THRESHOLD_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_8_2_handoff_threshold_inputs_invalid",
                "v0_8_3_handoff_mode": "rebuild_threshold_inputs_first",
                "why_threshold_pack_is_or_is_not_ready": "Upstream v0.8.1 characterized profile integrity did not pass.",
            },
            "handoff_integrity": integrity,
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", payload)
        write_text(
            out_root / "summary.md",
            "# v0.8.2 Closeout\n\n- version_decision: `v0_8_2_handoff_threshold_inputs_invalid`\n",
        )
        return payload

    build_v082_threshold_input_table(
        v081_closeout_path=v081_closeout_path,
        out_dir=str(Path(threshold_input_table_path).parent),
    )
    build_v082_threshold_freeze(
        threshold_input_table_path=threshold_input_table_path,
        out_dir=str(Path(threshold_freeze_path).parent),
    )
    threshold_inputs = load_json(threshold_input_table_path)
    threshold_freeze = load_json(threshold_freeze_path)

    anti_tautology_pass = bool((threshold_freeze.get("anti_tautology_check") or {}).get("pass"))
    integer_safe_pass = bool((threshold_freeze.get("integer_safe_check") or {}).get("pass"))
    class_distinction_pass = bool((threshold_freeze.get("class_distinction_check") or {}).get("pass"))
    all_three_classes_frozen = all(
        [
            bool(threshold_freeze.get("supported_threshold_pack")),
            bool(threshold_freeze.get("partial_threshold_pack")),
            bool(threshold_freeze.get("fallback_rule_summary")),
        ]
    )

    if anti_tautology_pass and integer_safe_pass and class_distinction_pass and all_three_classes_frozen:
        state = "frozen"
        version_decision = "v0_8_2_workflow_readiness_thresholds_frozen"
        handoff = "validate_frozen_workflow_readiness_threshold_pack"
        why = "The workflow threshold pack is explicitly frozen, anti-tautological, integer-safe on the 10-task substrate, and keeps supported / partial / fallback meaningfully separated."
    elif all_three_classes_frozen and (anti_tautology_pass or integer_safe_pass or class_distinction_pass):
        state = "partial"
        version_decision = "v0_8_2_workflow_readiness_thresholds_partial"
        handoff = "repair_threshold_pack_justification_first"
        why = "The threshold logic is directionally usable, but at least one required validation layer remains too weak to treat the pack as frozen."
    else:
        state = "invalid"
        version_decision = "v0_8_2_workflow_readiness_thresholds_invalid"
        handoff = "rebuild_threshold_inputs_first"
        why = "The threshold pack does not yet preserve a clean supported / partial / fallback distinction under executable checks."

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": "PASS" if state in {"frozen", "partial"} else "FAIL",
        "closeout_status": {
            "frozen": "V0_8_2_WORKFLOW_READINESS_THRESHOLDS_FROZEN",
            "partial": "V0_8_2_WORKFLOW_READINESS_THRESHOLDS_PARTIAL",
            "invalid": "V0_8_2_WORKFLOW_READINESS_THRESHOLDS_INVALID",
        }[state],
        "conclusion": {
            "version_decision": version_decision,
            "why_threshold_pack_is_or_is_not_ready": why,
            "anti_tautology_pass": anti_tautology_pass,
            "integer_safe_pass": integer_safe_pass,
            "class_distinction_pass": class_distinction_pass,
            "why_current_v081_baseline_is_or_is_not_partial_by_default": threshold_freeze.get(
                "why_current_v081_baseline_is_or_is_not_partial_by_default"
            ),
            "v0_8_3_handoff_mode": handoff,
        },
        "handoff_integrity": integrity,
        "threshold_input_table": threshold_inputs,
        "threshold_freeze": threshold_freeze,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.8.2 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- anti_tautology_pass: `{anti_tautology_pass}`",
                f"- integer_safe_pass: `{integer_safe_pass}`",
                f"- v0_8_3_handoff_mode: `{handoff}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.8.2 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument(
        "--threshold-input-table",
        default=str(DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR / "summary.json"),
    )
    parser.add_argument(
        "--threshold-freeze",
        default=str(DEFAULT_THRESHOLD_FREEZE_OUT_DIR / "summary.json"),
    )
    parser.add_argument("--v081-closeout", default=str(DEFAULT_V081_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v082_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        threshold_input_table_path=str(args.threshold_input_table),
        threshold_freeze_path=str(args.threshold_freeze),
        v081_closeout_path=str(args.v081_closeout),
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
