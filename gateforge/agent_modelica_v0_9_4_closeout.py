from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_9_4_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_EXPANDED_THRESHOLD_PACK_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR,
    DEFAULT_V093_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_9_4_expanded_threshold_pack import build_v094_expanded_threshold_pack
from .agent_modelica_v0_9_4_handoff_integrity import build_v094_handoff_integrity
from .agent_modelica_v0_9_4_threshold_input_table import build_v094_threshold_input_table


def build_v094_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    threshold_input_table_path: str = str(DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR / "summary.json"),
    expanded_threshold_pack_path: str = str(DEFAULT_EXPANDED_THRESHOLD_PACK_OUT_DIR / "summary.json"),
    v093_closeout_path: str = str(DEFAULT_V093_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    build_v094_handoff_integrity(v093_closeout_path=v093_closeout_path, out_dir=str(Path(handoff_integrity_path).parent))
    integrity = load_json(handoff_integrity_path)
    if integrity.get("handoff_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_9_4_HANDOFF_THRESHOLD_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_9_4_handoff_threshold_inputs_invalid",
                "v0_9_5_handoff_mode": "rebuild_v0_9_4_inputs_first",
                "why_threshold_pack_is_or_is_not_ready": "Upstream v0.9.3 characterized expanded profile integrity did not pass.",
            },
            "handoff_integrity": integrity,
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.9.4 Closeout\n\n- version_decision: `v0_9_4_handoff_threshold_inputs_invalid`\n")
        return payload

    if not Path(threshold_input_table_path).exists():
        build_v094_threshold_input_table(
            v093_closeout_path=v093_closeout_path,
            out_dir=str(Path(threshold_input_table_path).parent),
        )
    if not Path(expanded_threshold_pack_path).exists():
        build_v094_expanded_threshold_pack(
            threshold_input_table_path=threshold_input_table_path,
            out_dir=str(Path(expanded_threshold_pack_path).parent),
        )
    threshold_inputs = load_json(threshold_input_table_path)
    threshold_pack = load_json(expanded_threshold_pack_path)

    anti_tautology_pass = bool((threshold_pack.get("anti_tautology_check") or {}).get("pass"))
    integer_safe_pass = bool((threshold_pack.get("integer_safe_check") or {}).get("pass"))
    threshold_ordering_pass = bool((threshold_pack.get("threshold_ordering_check") or {}).get("pass"))
    execution_posture_pass = bool((threshold_pack.get("execution_posture_semantics_check") or {}).get("pass"))
    structural_explicit_pass = bool((threshold_pack.get("structural_explicit_check") or {}).get("pass"))
    baseline_classification = str(threshold_pack.get("baseline_classification_under_frozen_pack") or "")

    frozen_ready = all(
        [
            structural_explicit_pass,
            anti_tautology_pass,
            integer_safe_pass,
            threshold_ordering_pass,
            execution_posture_pass,
            baseline_classification == "expanded_workflow_readiness_partial_but_interpretable",
        ]
    )
    partial_ready = all(
        [
            structural_explicit_pass,
            threshold_ordering_pass,
            baseline_classification != "fallback_to_profile_clarification_or_expansion_needed",
            any(
                [
                    not anti_tautology_pass,
                    not integer_safe_pass,
                    not execution_posture_pass,
                    baseline_classification != "expanded_workflow_readiness_partial_but_interpretable",
                ]
            ),
        ]
    )

    if frozen_ready:
        state = "frozen"
        version_decision = "v0_9_4_expanded_workflow_thresholds_frozen"
        handoff = "adjudicate_expanded_workflow_readiness_against_frozen_thresholds"
        why = "The expanded workflow threshold pack is explicit, anti-tautological, integer-safe on the 19-task substrate, and keeps supported / partial / fallback meaningfully separated."
    elif partial_ready:
        state = "partial"
        version_decision = "v0_9_4_expanded_workflow_thresholds_partial"
        handoff = "clarify_threshold_pack_before_adjudication"
        why = "The threshold-freeze structure is usable, but at least one frozen validation layer remains incomplete before formal adjudication."
    else:
        state = "invalid"
        version_decision = "v0_9_4_expanded_workflow_thresholds_invalid"
        handoff = "repair_threshold_pack_design_first"
        why = "The threshold pack is structurally invalid, cannot preserve ordered class boundaries, or collapses the current baseline into fallback."

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": "PASS" if state in {"frozen", "partial"} else "FAIL",
        "closeout_status": {
            "frozen": "V0_9_4_EXPANDED_WORKFLOW_THRESHOLDS_FROZEN",
            "partial": "V0_9_4_EXPANDED_WORKFLOW_THRESHOLDS_PARTIAL",
            "invalid": "V0_9_4_EXPANDED_WORKFLOW_THRESHOLDS_INVALID",
        }[state],
        "conclusion": {
            "version_decision": version_decision,
            "baseline_classification_under_frozen_pack": baseline_classification,
            "supported_thresholds": threshold_pack.get("supported_threshold_pack"),
            "partial_but_interpretable_thresholds": threshold_pack.get("partial_threshold_pack"),
            "anti_tautology_pass": anti_tautology_pass,
            "integer_safe_pass": integer_safe_pass,
            "threshold_ordering_pass": threshold_ordering_pass,
            "execution_posture_pass": execution_posture_pass,
            "why_threshold_pack_is_or_is_not_ready": why,
            "v0_9_5_handoff_mode": handoff,
        },
        "handoff_integrity": integrity,
        "threshold_input_table": threshold_inputs,
        "expanded_threshold_pack": threshold_pack,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.4 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- baseline_classification_under_frozen_pack: `{baseline_classification}`",
                f"- anti_tautology_pass: `{anti_tautology_pass}`",
                f"- integer_safe_pass: `{integer_safe_pass}`",
                f"- v0_9_5_handoff_mode: `{handoff}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.4 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--threshold-input-table", default=str(DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR / "summary.json"))
    parser.add_argument("--expanded-threshold-pack", default=str(DEFAULT_EXPANDED_THRESHOLD_PACK_OUT_DIR / "summary.json"))
    parser.add_argument("--v093-closeout", default=str(DEFAULT_V093_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v094_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        threshold_input_table_path=str(args.threshold_input_table),
        expanded_threshold_pack_path=str(args.expanded_threshold_pack),
        v093_closeout_path=str(args.v093_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
