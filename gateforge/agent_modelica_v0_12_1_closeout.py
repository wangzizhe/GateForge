from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_12_1_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_PACK_EFFECT_CHARACTERIZATION_OUT_DIR,
    DEFAULT_REMEDY_EXECUTION_PACK_OUT_DIR,
    DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_BUILDER_PATH,
    DEFAULT_V120_CLOSEOUT_PATH,
    PACK_EFFECT_INVALID,
    PACK_EFFECT_MAINLINE_IMPROVING,
    PACK_EFFECT_NON_MATERIAL,
    PACK_EFFECT_SIDE_EVIDENCE_ONLY,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_12_1_handoff_integrity import build_v121_handoff_integrity
from .agent_modelica_v0_12_1_pack_effect_characterization import build_v121_pack_effect_characterization
from .agent_modelica_v0_12_1_remedy_execution_pack import build_v121_remedy_execution_pack


def build_v121_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    remedy_execution_pack_path: str = str(DEFAULT_REMEDY_EXECUTION_PACK_OUT_DIR / "summary.json"),
    pack_effect_characterization_path: str = str(DEFAULT_PACK_EFFECT_CHARACTERIZATION_OUT_DIR / "summary.json"),
    v120_closeout_path: str = str(DEFAULT_V120_CLOSEOUT_PATH),
    v112_product_gap_substrate_builder_path: str = str(DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_BUILDER_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    handoff_path_obj = Path(handoff_integrity_path)
    if not handoff_path_obj.exists():
        build_v121_handoff_integrity(
            v120_closeout_path=v120_closeout_path,
            out_dir=str(handoff_path_obj.parent),
        )
    handoff = load_json(handoff_integrity_path)
    if handoff.get("handoff_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_12_1_FIRST_REMEDY_PACK_EXECUTION_INVALID",
            "conclusion": {
                "version_decision": "v0_12_1_first_remedy_pack_execution_invalid",
                "v0_12_2_handoff_mode": "rebuild_remedy_execution_first",
            },
            "handoff_integrity": handoff,
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.12.1 Closeout\n\n- version_decision: `v0_12_1_first_remedy_pack_execution_invalid`\n")
        return payload

    execution_pack_path_obj = Path(remedy_execution_pack_path)
    if not execution_pack_path_obj.exists():
        build_v121_remedy_execution_pack(
            v112_product_gap_substrate_builder_path=v112_product_gap_substrate_builder_path,
            out_dir=str(execution_pack_path_obj.parent),
        )
    effect_path_obj = Path(pack_effect_characterization_path)
    if not effect_path_obj.exists():
        build_v121_pack_effect_characterization(
            remedy_execution_pack_path=remedy_execution_pack_path,
            out_dir=str(effect_path_obj.parent),
        )

    execution_pack = load_json(remedy_execution_pack_path)
    effect = load_json(pack_effect_characterization_path)
    pack_level_effect = str(((effect.get("pack_level_effect_summary") or {}).get("pack_level_effect")) or "")
    comparison = (
        execution_pack.get("pre_post_comparison_record")
        if isinstance(execution_pack.get("pre_post_comparison_record"), dict)
        else {}
    )

    if any(
        [
            not comparison.get("pre_remedy_run_reference"),
            not comparison.get("post_remedy_run_reference"),
            not bool(comparison.get("same_execution_source")),
            pack_level_effect == PACK_EFFECT_INVALID,
        ]
    ):
        version_decision = "v0_12_1_first_remedy_pack_execution_invalid"
        handoff_mode = "rebuild_remedy_execution_first"
        status = "FAIL"
    elif pack_level_effect == PACK_EFFECT_MAINLINE_IMPROVING:
        version_decision = "v0_12_1_first_remedy_pack_mainline_improving"
        handoff_mode = "characterize_pack_level_product_gap_effect"
        status = "PASS"
    elif pack_level_effect == PACK_EFFECT_SIDE_EVIDENCE_ONLY:
        version_decision = "v0_12_1_first_remedy_pack_side_evidence_only"
        handoff_mode = "determine_whether_stronger_remedy_is_in_scope"
        status = "PASS"
    elif pack_level_effect == PACK_EFFECT_NON_MATERIAL:
        version_decision = "v0_12_1_first_remedy_pack_non_material"
        handoff_mode = "determine_whether_stronger_remedy_is_in_scope"
        status = "PASS"
    else:
        version_decision = "v0_12_1_first_remedy_pack_execution_invalid"
        handoff_mode = "rebuild_remedy_execution_first"
        status = "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": version_decision.upper(),
        "conclusion": {
            "version_decision": version_decision,
            "pack_level_effect": pack_level_effect,
            "pre_remedy_run_reference": comparison.get("pre_remedy_run_reference"),
            "post_remedy_run_reference": comparison.get("post_remedy_run_reference"),
            "same_execution_source": comparison.get("same_execution_source"),
            "same_case_requirement_met": comparison.get("same_case_requirement_met"),
            "workflow_resolution_delta": comparison.get("workflow_resolution_delta"),
            "goal_alignment_delta": comparison.get("goal_alignment_delta"),
            "surface_fix_only_delta": comparison.get("surface_fix_only_delta"),
            "unresolved_delta": comparison.get("unresolved_delta"),
            "token_count_delta": comparison.get("token_count_delta"),
            "product_gap_sidecar_comparison_status": comparison.get("product_gap_sidecar_comparison_status"),
            "v0_12_2_handoff_mode": handoff_mode,
        },
        "handoff_integrity": handoff,
        "remedy_execution_pack": execution_pack,
        "pack_effect_characterization": effect,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.12.1 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- pack_level_effect: `{pack_level_effect}`",
                f"- same_execution_source: `{comparison.get('same_execution_source')}`",
                f"- v0_12_2_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.12.1 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--remedy-execution-pack", default=str(DEFAULT_REMEDY_EXECUTION_PACK_OUT_DIR / "summary.json"))
    parser.add_argument("--pack-effect-characterization", default=str(DEFAULT_PACK_EFFECT_CHARACTERIZATION_OUT_DIR / "summary.json"))
    parser.add_argument("--v120-closeout", default=str(DEFAULT_V120_CLOSEOUT_PATH))
    parser.add_argument("--v112-product-gap-substrate-builder", default=str(DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_BUILDER_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v121_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        remedy_execution_pack_path=str(args.remedy_execution_pack),
        pack_effect_characterization_path=str(args.pack_effect_characterization),
        v120_closeout_path=str(args.v120_closeout),
        v112_product_gap_substrate_builder_path=str(args.v112_product_gap_substrate_builder),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": ((payload.get("conclusion") or {}).get("version_decision"))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
