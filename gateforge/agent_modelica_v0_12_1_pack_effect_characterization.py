from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_12_1_common import (
    DEFAULT_PACK_EFFECT_CHARACTERIZATION_OUT_DIR,
    DEFAULT_REMEDY_EXECUTION_PACK_OUT_DIR,
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


def build_v121_pack_effect_characterization(
    *,
    remedy_execution_pack_path: str = str(DEFAULT_REMEDY_EXECUTION_PACK_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_PACK_EFFECT_CHARACTERIZATION_OUT_DIR),
) -> dict:
    execution_pack = load_json(remedy_execution_pack_path)
    comparison = (
        execution_pack.get("pre_post_comparison_record")
        if isinstance(execution_pack.get("pre_post_comparison_record"), dict)
        else {}
    )

    invalid = any(
        [
            execution_pack.get("remedy_execution_pack_status") != "ready",
            not comparison.get("pre_remedy_run_reference"),
            not comparison.get("post_remedy_run_reference"),
            not bool(comparison.get("same_execution_source")),
            not bool(comparison.get("same_case_requirement_met")),
        ]
    )
    resolution_delta = int(comparison.get("workflow_resolution_delta") or 0)
    goal_alignment_delta = int(comparison.get("goal_alignment_delta") or 0)
    surface_fix_only_delta = int(comparison.get("surface_fix_only_delta") or 0)
    unresolved_delta = int(comparison.get("unresolved_delta") or 0)
    token_count_delta = int(comparison.get("token_count_delta") or 0)
    sidecar_status = str(comparison.get("product_gap_sidecar_comparison_status") or "")
    ambiguous_side = bool(comparison.get("ambiguous_side_evidence_movement"))
    measurable_side_fields = list(comparison.get("measurable_side_evidence_fields") or [])

    if invalid:
        pack_level_effect = PACK_EFFECT_INVALID
    elif resolution_delta > 0 or goal_alignment_delta > 0 or surface_fix_only_delta < 0:
        pack_level_effect = PACK_EFFECT_MAINLINE_IMPROVING
    elif (
        resolution_delta == 0
        and goal_alignment_delta == 0
        and surface_fix_only_delta == 0
        and unresolved_delta == 0
        and not ambiguous_side
        and (
            token_count_delta != 0
            or sidecar_status == "measurable_runtime_side_evidence_movement"
            or bool(measurable_side_fields)
        )
    ):
        pack_level_effect = PACK_EFFECT_SIDE_EVIDENCE_ONLY
    else:
        pack_level_effect = PACK_EFFECT_NON_MATERIAL

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_pack_effect_characterization",
        "generated_at_utc": now_utc(),
        "status": "PASS" if pack_level_effect != PACK_EFFECT_INVALID else "FAIL",
        "pack_level_effect_summary": {
            "pack_level_effect": pack_level_effect,
            "observed_mainline_delta": {
                "workflow_resolution_delta": resolution_delta,
                "goal_alignment_delta": goal_alignment_delta,
                "surface_fix_only_delta": surface_fix_only_delta,
                "unresolved_delta": unresolved_delta,
            },
            "observed_side_delta": {
                "token_count_delta": token_count_delta,
                "product_gap_sidecar_comparison_status": sidecar_status,
                "measurable_side_evidence_fields": measurable_side_fields,
                "ambiguous_side_evidence_movement": ambiguous_side,
            },
            "product_gap_sidecar_comparison_status": sidecar_status,
            "per_remedy_attribution_deferred": True,
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.12.1 Pack Effect Characterization",
                "",
                f"- pack_level_effect: `{pack_level_effect}`",
                f"- workflow_resolution_delta: `{resolution_delta}`",
                f"- goal_alignment_delta: `{goal_alignment_delta}`",
                f"- token_count_delta: `{token_count_delta}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.12.1 pack-effect characterization artifact.")
    parser.add_argument("--remedy-execution-pack", default=str(DEFAULT_REMEDY_EXECUTION_PACK_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_PACK_EFFECT_CHARACTERIZATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v121_pack_effect_characterization(
        remedy_execution_pack_path=str(args.remedy_execution_pack),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "pack_level_effect": ((payload.get("pack_level_effect_summary") or {}).get("pack_level_effect"))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
