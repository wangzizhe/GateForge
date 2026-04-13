from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_13_1_common import (
    DEFAULT_CAPABILITY_EFFECT_CHARACTERIZATION_OUT_DIR,
    DEFAULT_CAPABILITY_INTERVENTION_EXECUTION_PACK_OUT_DIR,
    INTERVENTION_EFFECT_INVALID,
    INTERVENTION_EFFECT_MATERIAL,
    INTERVENTION_EFFECT_NON_MATERIAL,
    INTERVENTION_EFFECT_SIDE_EVIDENCE_ONLY,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v131_capability_effect_characterization(
    *,
    capability_intervention_execution_pack_path: str = str(
        DEFAULT_CAPABILITY_INTERVENTION_EXECUTION_PACK_OUT_DIR / "summary.json"
    ),
    out_dir: str = str(DEFAULT_CAPABILITY_EFFECT_CHARACTERIZATION_OUT_DIR),
) -> dict:
    execution_pack = load_json(capability_intervention_execution_pack_path)
    comparison = (
        execution_pack.get("pre_post_capability_comparison_record")
        if isinstance(execution_pack.get("pre_post_capability_comparison_record"), dict)
        else {}
    )

    invalid = any(
        [
            execution_pack.get("capability_intervention_execution_pack_status") != "ready",
            not comparison.get("pre_intervention_run_reference"),
            not comparison.get("post_intervention_run_reference"),
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
        intervention_effect_class = INTERVENTION_EFFECT_INVALID
    elif resolution_delta > 0 or goal_alignment_delta > 0:
        intervention_effect_class = INTERVENTION_EFFECT_MATERIAL
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
        intervention_effect_class = INTERVENTION_EFFECT_SIDE_EVIDENCE_ONLY
    else:
        intervention_effect_class = INTERVENTION_EFFECT_NON_MATERIAL

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_capability_effect_characterization",
        "generated_at_utc": now_utc(),
        "status": "PASS" if intervention_effect_class != INTERVENTION_EFFECT_INVALID else "FAIL",
        "intervention_effect_summary": {
            "intervention_effect_class": intervention_effect_class,
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
            "per_intervention_attribution_deferred": True,
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.13.1 Capability Effect Characterization",
                "",
                f"- intervention_effect_class: `{intervention_effect_class}`",
                f"- workflow_resolution_delta: `{resolution_delta}`",
                f"- goal_alignment_delta: `{goal_alignment_delta}`",
                f"- token_count_delta: `{token_count_delta}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.13.1 capability effect characterization artifact.")
    parser.add_argument(
        "--capability-intervention-execution-pack",
        default=str(DEFAULT_CAPABILITY_INTERVENTION_EXECUTION_PACK_OUT_DIR / "summary.json"),
    )
    parser.add_argument("--out-dir", default=str(DEFAULT_CAPABILITY_EFFECT_CHARACTERIZATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v131_capability_effect_characterization(
        capability_intervention_execution_pack_path=str(args.capability_intervention_execution_pack),
        out_dir=str(args.out_dir),
    )
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "intervention_effect_class": (
                    (payload.get("intervention_effect_summary") or {}).get("intervention_effect_class")
                ),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
