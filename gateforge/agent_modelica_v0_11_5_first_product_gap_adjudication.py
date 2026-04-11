from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_11_4_product_gap_threshold_pack import _classify_baseline
from .agent_modelica_v0_11_5_common import (
    DEFAULT_FIRST_PRODUCT_GAP_ADJUDICATION_OUT_DIR,
    DEFAULT_PRODUCT_GAP_ADJUDICATION_INPUT_TABLE_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v115_first_product_gap_adjudication(
    *,
    product_gap_adjudication_input_table_path: str = str(
        DEFAULT_PRODUCT_GAP_ADJUDICATION_INPUT_TABLE_OUT_DIR / "summary.json"
    ),
    out_dir: str = str(DEFAULT_FIRST_PRODUCT_GAP_ADJUDICATION_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    inputs = load_json(product_gap_adjudication_input_table_path)

    workflow_resolution_case_count = int(inputs.get("workflow_resolution_case_count") or 0)
    goal_alignment_case_count = int(inputs.get("goal_alignment_case_count") or 0)
    execution_posture_ok = bool(inputs.get("execution_posture_semantics_preserved"))
    dominant_gap_family_readout = inputs.get("dominant_gap_family_readout")

    classification = _classify_baseline(workflow_resolution_case_count, goal_alignment_case_count)
    if not execution_posture_ok:
        classification = "product_gap_fallback"

    supported = classification == "product_gap_supported"
    partial = classification == "product_gap_partial_but_interpretable"
    fallback = classification == "product_gap_fallback"
    route_count = int(sum([supported, partial, fallback]))

    if supported:
        why = (
            "Supported is reached because the current product-gap profile clears the frozen supported thresholds "
            "while preserving execution-posture semantics."
        )
    elif partial:
        why = (
            "Partial but interpretable is reached because the current product-gap profile clears the frozen "
            "partial floor, remains compatible with the carried execution-posture semantics, but stays below "
            "the frozen supported workflow-resolution and goal-alignment counts."
        )
    elif fallback:
        why = (
            "Fallback is triggered because the current product-gap profile no longer clears even the frozen "
            "partial band or no longer preserves the carried execution-posture semantics."
        )
    else:
        why = "The adjudication result is invalid because the frozen product-gap pack did not yield a unique route."

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_first_product_gap_adjudication",
        "generated_at_utc": now_utc(),
        "status": "PASS" if route_count == 1 else "FAIL",
        "final_adjudication_label": classification if route_count == 1 else "invalid_non_unique_route",
        "baseline_classification_under_frozen_pack": classification,
        "supported_check_pass": supported,
        "partial_check_pass": partial,
        "fallback_triggered": fallback,
        "execution_posture_semantics_preserved": execution_posture_ok,
        "adjudication_route_count": route_count,
        "dominant_gap_family_readout": dominant_gap_family_readout,
        "adjudication_explanation": why,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.11.5 First Product-Gap Adjudication",
                "",
                f"- final_adjudication_label: `{payload['final_adjudication_label']}`",
                f"- adjudication_route_count: `{route_count}`",
                f"- dominant_gap_family_readout: `{dominant_gap_family_readout}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.11.5 first product-gap adjudication artifact.")
    parser.add_argument(
        "--product-gap-adjudication-input-table",
        default=str(DEFAULT_PRODUCT_GAP_ADJUDICATION_INPUT_TABLE_OUT_DIR / "summary.json"),
    )
    parser.add_argument("--out-dir", default=str(DEFAULT_FIRST_PRODUCT_GAP_ADJUDICATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v115_first_product_gap_adjudication(
        product_gap_adjudication_input_table_path=str(args.product_gap_adjudication_input_table),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "final_adjudication_label": payload.get("final_adjudication_label")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
