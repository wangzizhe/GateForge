from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_14_1_broader_change_effect_characterization import (
    build_v141_broader_change_effect_characterization,
)
from .agent_modelica_v0_14_1_broader_change_execution_pack import build_v141_broader_change_execution_pack
from .agent_modelica_v0_14_1_common import (
    BROADER_CHANGE_EFFECT_INVALID,
    BROADER_CHANGE_EFFECT_MATERIAL,
    BROADER_CHANGE_EFFECT_NON_MATERIAL,
    BROADER_CHANGE_EFFECT_SIDE_EVIDENCE_ONLY,
    DEFAULT_BROADER_CHANGE_EFFECT_CHARACTERIZATION_OUT_DIR,
    DEFAULT_BROADER_CHANGE_EXECUTION_PACK_OUT_DIR,
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_BUILDER_PATH,
    DEFAULT_V140_CLOSEOUT_PATH,
    DEFAULT_V140_GOVERNANCE_PACK_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_14_1_handoff_integrity import build_v141_handoff_integrity


def build_v141_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    broader_change_execution_pack_path: str = str(DEFAULT_BROADER_CHANGE_EXECUTION_PACK_OUT_DIR / "summary.json"),
    broader_change_effect_characterization_path: str = str(
        DEFAULT_BROADER_CHANGE_EFFECT_CHARACTERIZATION_OUT_DIR / "summary.json"
    ),
    v140_closeout_path: str = str(DEFAULT_V140_CLOSEOUT_PATH),
    v140_governance_pack_path: str = str(DEFAULT_V140_GOVERNANCE_PACK_PATH),
    v112_product_gap_substrate_builder_path: str = str(DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_BUILDER_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    handoff_path_obj = Path(handoff_integrity_path)
    if not handoff_path_obj.exists():
        build_v141_handoff_integrity(
            v140_closeout_path=v140_closeout_path,
            out_dir=str(handoff_path_obj.parent),
        )
    handoff = load_json(handoff_integrity_path)
    if handoff.get("handoff_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_14_1_FIRST_BROADER_CHANGE_PACK_EXECUTION_INVALID",
            "conclusion": {
                "version_decision": "v0_14_1_first_broader_change_pack_execution_invalid",
                "v0_14_2_handoff_mode": "rebuild_v0_14_1_execution_inputs_first",
            },
            "handoff_integrity": handoff,
        }
        write_json(out_root / "summary.json", payload)
        write_text(
            out_root / "summary.md",
            "# v0.14.1 Closeout\n\n- version_decision: `v0_14_1_first_broader_change_pack_execution_invalid`\n",
        )
        return payload

    execution_pack_path_obj = Path(broader_change_execution_pack_path)
    if not execution_pack_path_obj.exists():
        build_v141_broader_change_execution_pack(
            v140_governance_pack_path=v140_governance_pack_path,
            v112_product_gap_substrate_builder_path=v112_product_gap_substrate_builder_path,
            out_dir=str(execution_pack_path_obj.parent),
        )
    effect_path_obj = Path(broader_change_effect_characterization_path)
    if not effect_path_obj.exists():
        build_v141_broader_change_effect_characterization(
            broader_change_execution_pack_path=broader_change_execution_pack_path,
            out_dir=str(effect_path_obj.parent),
        )

    execution_pack = load_json(broader_change_execution_pack_path)
    effect = load_json(broader_change_effect_characterization_path)
    broader_change_effect_class = str(
        ((effect.get("broader_change_effect_summary") or {}).get("broader_change_effect_class")) or ""
    )
    comparison = (
        execution_pack.get("pre_post_broader_change_comparison_record")
        if isinstance(execution_pack.get("pre_post_broader_change_comparison_record"), dict)
        else {}
    )
    pre_ref = comparison.get("pre_intervention_run_reference")
    post_ref = comparison.get("post_intervention_run_reference")
    same_execution_source = bool(comparison.get("same_execution_source"))

    runs_valid = bool(pre_ref) and bool(post_ref) and same_execution_source

    if any(
        [
            not pre_ref,
            not post_ref,
            not same_execution_source,
            broader_change_effect_class == BROADER_CHANGE_EFFECT_INVALID,
        ]
    ):
        version_decision = "v0_14_1_first_broader_change_pack_execution_invalid"
        handoff_mode = "rebuild_v0_14_1_execution_inputs_first"
        status = "FAIL"
    elif broader_change_effect_class == BROADER_CHANGE_EFFECT_MATERIAL and runs_valid:
        version_decision = "v0_14_1_first_broader_change_pack_mainline_material"
        handoff_mode = "characterize_first_broader_change_effect_profile"
        status = "PASS"
    elif broader_change_effect_class == BROADER_CHANGE_EFFECT_SIDE_EVIDENCE_ONLY and runs_valid:
        version_decision = "v0_14_1_first_broader_change_pack_side_evidence_only"
        handoff_mode = "determine_whether_stronger_broader_change_is_in_scope"
        status = "PASS"
    elif broader_change_effect_class == BROADER_CHANGE_EFFECT_NON_MATERIAL and runs_valid:
        version_decision = "v0_14_1_first_broader_change_pack_non_material"
        handoff_mode = "determine_whether_stronger_broader_change_is_in_scope"
        status = "PASS"
    else:
        version_decision = "v0_14_1_first_broader_change_pack_execution_invalid"
        handoff_mode = "rebuild_v0_14_1_execution_inputs_first"
        status = "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": version_decision.upper(),
        "conclusion": {
            "version_decision": version_decision,
            "broader_change_effect_class": broader_change_effect_class,
            "pre_intervention_run_reference": pre_ref,
            "post_intervention_run_reference": post_ref,
            "same_execution_source": same_execution_source,
            "same_case_requirement_met": comparison.get("same_case_requirement_met"),
            "workflow_resolution_delta": comparison.get("workflow_resolution_delta"),
            "goal_alignment_delta": comparison.get("goal_alignment_delta"),
            "surface_fix_only_delta": comparison.get("surface_fix_only_delta"),
            "unresolved_delta": comparison.get("unresolved_delta"),
            "token_count_delta": comparison.get("token_count_delta"),
            "product_gap_sidecar_comparison_status": comparison.get("product_gap_sidecar_comparison_status"),
            "v0_14_2_handoff_mode": handoff_mode,
        },
        "handoff_integrity": handoff,
        "broader_change_execution_pack": execution_pack,
        "broader_change_effect_characterization": effect,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.14.1 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- broader_change_effect_class: `{broader_change_effect_class}`",
                f"- same_execution_source: `{same_execution_source}`",
                f"- v0_14_2_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.14.1 broader change closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument(
        "--broader-change-execution-pack",
        default=str(DEFAULT_BROADER_CHANGE_EXECUTION_PACK_OUT_DIR / "summary.json"),
    )
    parser.add_argument(
        "--broader-change-effect-characterization",
        default=str(DEFAULT_BROADER_CHANGE_EFFECT_CHARACTERIZATION_OUT_DIR / "summary.json"),
    )
    parser.add_argument("--v140-closeout", default=str(DEFAULT_V140_CLOSEOUT_PATH))
    parser.add_argument("--v140-governance-pack", default=str(DEFAULT_V140_GOVERNANCE_PACK_PATH))
    parser.add_argument("--v112-product-gap-substrate-builder", default=str(DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_BUILDER_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v141_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        broader_change_execution_pack_path=str(args.broader_change_execution_pack),
        broader_change_effect_characterization_path=str(args.broader_change_effect_characterization),
        v140_closeout_path=str(args.v140_closeout),
        v140_governance_pack_path=str(args.v140_governance_pack),
        v112_product_gap_substrate_builder_path=str(args.v112_product_gap_substrate_builder),
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
