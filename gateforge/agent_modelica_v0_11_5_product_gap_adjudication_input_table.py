from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_11_5_common import (
    DEFAULT_PRODUCT_GAP_ADJUDICATION_INPUT_TABLE_OUT_DIR,
    DEFAULT_V113_CLOSEOUT_PATH,
    DEFAULT_V114_CLOSEOUT_PATH,
    DEFAULT_V114_THRESHOLD_PACK_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v115_product_gap_adjudication_input_table(
    *,
    v114_closeout_path: str = str(DEFAULT_V114_CLOSEOUT_PATH),
    v114_threshold_pack_path: str = str(DEFAULT_V114_THRESHOLD_PACK_PATH),
    v113_closeout_path: str = str(DEFAULT_V113_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_PRODUCT_GAP_ADJUDICATION_INPUT_TABLE_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    v114_closeout = load_json(v114_closeout_path)
    v114_pack = load_json(v114_threshold_pack_path)
    v113_closeout = load_json(v113_closeout_path)

    v114_conclusion = v114_closeout.get("conclusion") if isinstance(v114_closeout.get("conclusion"), dict) else {}
    v113_conclusion = v113_closeout.get("conclusion") if isinstance(v113_closeout.get("conclusion"), dict) else {}

    supported = dict(v114_pack.get("supported_thresholds") or {})
    partial = dict(v114_pack.get("partial_but_interpretable_thresholds") or {})

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_product_gap_adjudication_input_table",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "product_gap_case_count": int(v114_conclusion.get("product_gap_case_count") or 0),
        "workflow_resolution_case_count": int(v114_conclusion.get("workflow_resolution_case_count") or 0),
        "goal_alignment_case_count": int(v114_conclusion.get("goal_alignment_case_count") or 0),
        "surface_fix_only_case_count": int(v114_conclusion.get("surface_fix_only_case_count") or 0),
        "unresolved_case_count": int(v114_conclusion.get("unresolved_case_count") or 0),
        "supported_workflow_resolution_case_count": int(supported.get("workflow_resolution_case_count") or 0),
        "supported_goal_alignment_case_count": int(supported.get("goal_alignment_case_count") or 0),
        "partial_workflow_resolution_case_count": int(partial.get("workflow_resolution_case_count") or 0),
        "partial_goal_alignment_case_count": int(partial.get("goal_alignment_case_count") or 0),
        "execution_posture_semantics_preserved": bool(v114_conclusion.get("execution_posture_semantics_preserved")),
        "dominant_gap_family_readout": v113_conclusion.get("candidate_dominant_gap_family"),
        "baseline_classification_under_frozen_pack": v114_conclusion.get("baseline_classification_under_frozen_pack"),
        "frozen_baseline_metrics": {
            "product_gap_case_count": int(v114_conclusion.get("product_gap_case_count") or 0),
            "workflow_resolution_case_count": int(v114_conclusion.get("workflow_resolution_case_count") or 0),
            "goal_alignment_case_count": int(v114_conclusion.get("goal_alignment_case_count") or 0),
            "surface_fix_only_case_count": int(v114_conclusion.get("surface_fix_only_case_count") or 0),
            "unresolved_case_count": int(v114_conclusion.get("unresolved_case_count") or 0),
        },
        "frozen_thresholds": {
            "supported": {
                "workflow_resolution_case_count": int(supported.get("workflow_resolution_case_count") or 0),
                "goal_alignment_case_count": int(supported.get("goal_alignment_case_count") or 0),
            },
            "partial_but_interpretable": {
                "workflow_resolution_case_count": int(partial.get("workflow_resolution_case_count") or 0),
                "goal_alignment_case_count": int(partial.get("goal_alignment_case_count") or 0),
            },
        },
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.11.5 Product-Gap Adjudication Input Table",
                "",
                f"- product_gap_case_count: `{payload['product_gap_case_count']}`",
                f"- workflow_resolution_case_count: `{payload['workflow_resolution_case_count']}`",
                f"- goal_alignment_case_count: `{payload['goal_alignment_case_count']}`",
                f"- dominant_gap_family_readout: `{payload['dominant_gap_family_readout']}`",
                f"- baseline_classification_under_frozen_pack: `{payload['baseline_classification_under_frozen_pack']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.11.5 product-gap adjudication input table.")
    parser.add_argument("--v114-closeout", default=str(DEFAULT_V114_CLOSEOUT_PATH))
    parser.add_argument("--v114-threshold-pack", default=str(DEFAULT_V114_THRESHOLD_PACK_PATH))
    parser.add_argument("--v113-closeout", default=str(DEFAULT_V113_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_PRODUCT_GAP_ADJUDICATION_INPUT_TABLE_OUT_DIR))
    args = parser.parse_args()
    payload = build_v115_product_gap_adjudication_input_table(
        v114_closeout_path=str(args.v114_closeout),
        v114_threshold_pack_path=str(args.v114_threshold_pack),
        v113_closeout_path=str(args.v113_closeout),
        out_dir=str(args.out_dir),
    )
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "product_gap_case_count": payload.get("product_gap_case_count"),
                "dominant_gap_family_readout": payload.get("dominant_gap_family_readout"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
