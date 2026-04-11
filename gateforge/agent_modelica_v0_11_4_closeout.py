from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_11_4_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR,
    DEFAULT_THRESHOLD_PACK_OUT_DIR,
    DEFAULT_V113_CHARACTERIZATION_PATH,
    DEFAULT_V113_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_11_4_handoff_integrity import build_v114_handoff_integrity
from .agent_modelica_v0_11_4_product_gap_threshold_input_table import build_v114_product_gap_threshold_input_table
from .agent_modelica_v0_11_4_product_gap_threshold_pack import build_v114_product_gap_threshold_pack


def build_v114_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    threshold_input_table_path: str = str(DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR / "summary.json"),
    threshold_pack_path: str = str(DEFAULT_THRESHOLD_PACK_OUT_DIR / "summary.json"),
    v113_closeout_path: str = str(DEFAULT_V113_CLOSEOUT_PATH),
    v113_characterization_path: str = str(DEFAULT_V113_CHARACTERIZATION_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    handoff_path_obj = Path(handoff_integrity_path)
    input_table_path_obj = Path(threshold_input_table_path)
    pack_path_obj = Path(threshold_pack_path)

    if not handoff_path_obj.exists():
        build_v114_handoff_integrity(
            v113_closeout_path=v113_closeout_path,
            out_dir=str(handoff_path_obj.parent),
        )
    integrity = load_json(handoff_integrity_path)

    if integrity.get("handoff_integrity_status") != "PASS":
        version_decision = "v0_11_4_product_gap_threshold_inputs_invalid"
        handoff_mode = "rebuild_v0_11_4_threshold_inputs_first"
        status = "FAIL"
        why = "Upstream v0.11.3 handoff integrity did not pass; product-gap threshold freeze cannot proceed."
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": status,
            "closeout_status": version_decision.upper(),
            "conclusion": {
                "version_decision": version_decision,
                "v0_11_5_handoff_mode": handoff_mode,
                "why_this_is_or_is_not_frozen": why,
            },
            "handoff_integrity": integrity,
        }
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", f"# v0.11.4 Closeout\n\n- version_decision: `{version_decision}`\n")
        return payload

    if not input_table_path_obj.exists():
        build_v114_product_gap_threshold_input_table(
            v113_characterization_path=v113_characterization_path,
            out_dir=str(input_table_path_obj.parent),
        )
    if not pack_path_obj.exists():
        build_v114_product_gap_threshold_pack(
            threshold_input_table_path=threshold_input_table_path,
            out_dir=str(pack_path_obj.parent),
        )

    input_table = load_json(threshold_input_table_path)
    pack = load_json(threshold_pack_path)

    anti_tautology_pass = bool(pack.get("anti_tautology_pass"))
    integer_safe_pass = bool(pack.get("integer_safe_pass"))
    execution_posture_ok = bool(pack.get("execution_posture_semantics_preserved"))
    baseline_classification = str(pack.get("baseline_classification_under_frozen_pack") or "")

    if (
        anti_tautology_pass
        and integer_safe_pass
        and execution_posture_ok
        and baseline_classification == "product_gap_partial_but_interpretable"
    ):
        version_decision = "v0_11_4_first_product_gap_thresholds_frozen"
        handoff_mode = "adjudicate_first_product_gap_profile_against_frozen_thresholds"
        status = "PASS"
        why = (
            "The first product-gap threshold pack is structurally frozen, anti-tautology and integer-safe checks pass, "
            "and the current baseline stays classified as product_gap_partial_but_interpretable."
        )
    elif integrity.get("handoff_integrity_status") == "PASS" and integer_safe_pass is False and anti_tautology_pass:
        version_decision = "v0_11_4_first_product_gap_thresholds_partial"
        handoff_mode = "finish_product_gap_threshold_freeze_first"
        status = "PASS"
        why = "The threshold-freeze direction is valid, but integer-safe threshold validation remains incomplete."
    else:
        version_decision = "v0_11_4_product_gap_threshold_inputs_invalid"
        handoff_mode = "rebuild_v0_11_4_threshold_inputs_first"
        status = "FAIL"
        why = (
            "Anti-tautology failed, the baseline no longer classifies as partial under the frozen pack, "
            "or the threshold pack no longer preserves the carried execution-posture semantics."
        )

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": version_decision.upper(),
        "conclusion": {
            "version_decision": version_decision,
            "product_gap_case_count": input_table.get("product_gap_case_count"),
            "workflow_resolution_case_count": input_table.get("workflow_resolution_case_count"),
            "goal_alignment_case_count": input_table.get("goal_alignment_case_count"),
            "surface_fix_only_case_count": input_table.get("surface_fix_only_case_count"),
            "unresolved_case_count": input_table.get("unresolved_case_count"),
            "baseline_classification_under_frozen_pack": baseline_classification,
            "anti_tautology_pass": anti_tautology_pass,
            "integer_safe_pass": integer_safe_pass,
            "execution_posture_semantics_preserved": execution_posture_ok,
            "v0_11_5_handoff_mode": handoff_mode,
            "why_this_is_or_is_not_frozen": why,
        },
        "handoff_integrity": integrity,
        "product_gap_threshold_input_table": input_table,
        "product_gap_threshold_pack": pack,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.11.4 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- baseline_classification_under_frozen_pack: `{baseline_classification}`",
                f"- anti_tautology_pass: `{anti_tautology_pass}`",
                f"- integer_safe_pass: `{integer_safe_pass}`",
                f"- v0_11_5_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.11.4 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--threshold-input-table", default=str(DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR / "summary.json"))
    parser.add_argument("--threshold-pack", default=str(DEFAULT_THRESHOLD_PACK_OUT_DIR / "summary.json"))
    parser.add_argument("--v113-closeout", default=str(DEFAULT_V113_CLOSEOUT_PATH))
    parser.add_argument("--v113-characterization", default=str(DEFAULT_V113_CHARACTERIZATION_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v114_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        threshold_input_table_path=str(args.threshold_input_table),
        threshold_pack_path=str(args.threshold_pack),
        v113_closeout_path=str(args.v113_closeout),
        v113_characterization_path=str(args.v113_characterization),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
