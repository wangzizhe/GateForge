from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_11_4_common import (
    DEFAULT_PRODUCT_GAP_CASE_COUNT,
    DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR,
    DEFAULT_V113_CHARACTERIZATION_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v114_product_gap_threshold_input_table(
    *,
    v113_characterization_path: str = str(DEFAULT_V113_CHARACTERIZATION_PATH),
    out_dir: str = str(DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    characterization = load_json(v113_characterization_path)
    case_table = list(characterization.get("case_characterization_table") or [])

    total = len(case_table)
    workflow_resolution_count = sum(1 for row in case_table if row.get("product_gap_outcome") == "goal_level_resolved")
    surface_fix_only_count = sum(1 for row in case_table if row.get("product_gap_outcome") == "surface_fix_only")
    goal_alignment_count = workflow_resolution_count + surface_fix_only_count
    unresolved_count = sum(1 for row in case_table if row.get("product_gap_outcome") == "unresolved")

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_product_gap_threshold_input_table",
        "generated_at_utc": now_utc(),
        "status": "PASS" if total > 0 else "FAIL",
        "product_gap_case_count": total,
        "workflow_resolution_case_count": workflow_resolution_count,
        "goal_alignment_case_count": goal_alignment_count,
        "surface_fix_only_case_count": surface_fix_only_count,
        "unresolved_case_count": unresolved_count,
        "candidate_dominant_gap_family": characterization.get("candidate_dominant_gap_family"),
        "execution_posture_semantics_note": (
            "This threshold pack is frozen for product-gap interpretation on the carried 12-case substrate; "
            "it does not promote the result into product readiness."
        ),
        "workflow_resolution_rate_pct_display": characterization.get("workflow_resolution_rate_pct"),
        "goal_alignment_rate_pct_display": characterization.get("goal_alignment_rate_pct"),
        "surface_fix_only_rate_pct_display": characterization.get("surface_fix_only_rate_pct"),
        "unresolved_rate_pct_display": characterization.get("unresolved_rate_pct"),
        "derivation_source": "frozen_v0_11_3_product_gap_characterization_readout",
        "case_count_matches_expected_twelve": total == DEFAULT_PRODUCT_GAP_CASE_COUNT,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.11.4 Product-Gap Threshold Input Table",
                "",
                f"- product_gap_case_count: `{total}`",
                f"- workflow_resolution_case_count: `{workflow_resolution_count}`",
                f"- goal_alignment_case_count: `{goal_alignment_count}`",
                f"- surface_fix_only_case_count: `{surface_fix_only_count}`",
                f"- unresolved_case_count: `{unresolved_count}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.11.4 product-gap threshold input table.")
    parser.add_argument("--v113-characterization", default=str(DEFAULT_V113_CHARACTERIZATION_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR))
    args = parser.parse_args()
    payload = build_v114_product_gap_threshold_input_table(
        v113_characterization_path=str(args.v113_characterization),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "product_gap_case_count": payload.get("product_gap_case_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
