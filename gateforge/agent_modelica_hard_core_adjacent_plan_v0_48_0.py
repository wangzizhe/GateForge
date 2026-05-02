from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hard_core_adjacent_plan_v0_48_0"

ANCHOR_CASE_IDS = (
    "sem_13_arrayed_connector_bus_refactor",
    "sem_26_three_segment_adapter_cross_node",
    "singleroot2_02_replaceable_probe_array",
)

ANCHOR_RATIONALE = {
    "sem_13_arrayed_connector_bus_refactor": "arrayed connector bus and flow ownership remain a stable hard boundary",
    "sem_26_three_segment_adapter_cross_node": "multi-node adapter contract exposes cross-node flow ownership errors",
    "singleroot2_02_replaceable_probe_array": "replaceable probe array has historical success evidence and hard negative repeats",
}


def build_hard_core_adjacent_plan(*, version: str = "v0.48.0") -> dict[str, Any]:
    anchors = [
        {
            "case_id": case_id,
            "rationale": ANCHOR_RATIONALE[case_id],
            "planned_variant_count": 4,
        }
        for case_id in ANCHOR_CASE_IDS
    ]
    return {
        "version": version,
        "analysis_scope": "hard_core_adjacent_expansion_plan",
        "status": "PASS",
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "anchor_count": len(anchors),
        "planned_variant_count": sum(int(row["planned_variant_count"]) for row in anchors),
        "anchors": anchors,
        "construction_contract": {
            "source_backed": True,
            "workflow_proximal": True,
            "model_check_first": True,
            "no_answer_leakage": True,
            "no_wrapper_repair": True,
            "provider_model_source": "environment",
        },
        "decision": "construct_adjacent_variants_before_live_baseline",
    }


def write_hard_core_adjacent_plan_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_hard_core_adjacent_plan(*, out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    summary = build_hard_core_adjacent_plan()
    write_hard_core_adjacent_plan_outputs(out_dir=out_dir, summary=summary)
    return summary
