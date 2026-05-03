from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_benchmark_v1_spec_v0_51_0 import layer_names
from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_json


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HARD_PACK = REPO_ROOT / "artifacts" / "hard_benchmark_pack_v0_49_2" / "summary.json"
DEFAULT_COMPARISON_BASELINE = REPO_ROOT / "artifacts" / "agent_comparison_baseline_summary_v0_50_1" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "benchmark_v1_relayer_v0_52_0"


def _unique(values: list[str]) -> list[str]:
    return sorted({value for value in values if value})


def build_benchmark_v1_relayer(
    *,
    hard_pack_summary: dict[str, Any],
    comparison_baseline_summary: dict[str, Any],
    version: str = "v0.52.0",
) -> dict[str, Any]:
    hard_case_ids = _unique([str(case_id) for case_id in hard_pack_summary.get("hard_case_ids") or []])
    easy_case_ids = _unique([str(case_id) for case_id in hard_pack_summary.get("easy_calibration_case_ids") or []])
    unstable_case_ids = _unique([str(case_id) for case_id in hard_pack_summary.get("unstable_case_ids") or []])
    baseline_pass = _unique([str(case_id) for case_id in comparison_baseline_summary.get("pass_case_ids") or []])
    baseline_fail = _unique([str(case_id) for case_id in comparison_baseline_summary.get("fail_case_ids") or []])

    # v0.52 is an evidence relayer, not a new live result. Medium candidates are
    # intentionally empty until v0.54 constructs cases in the target pass band.
    layer_case_ids = {
        "sanity": [],
        "easy": _unique(easy_case_ids + baseline_pass),
        "medium": [],
        "hard": hard_case_ids,
        "frontier": [],
    }
    unknown_failures = _unique([case_id for case_id in baseline_fail if case_id not in hard_case_ids and case_id not in unstable_case_ids])
    gaps = []
    if not layer_case_ids["sanity"]:
        gaps.append("missing_sanity_layer")
    if not layer_case_ids["medium"]:
        gaps.append("missing_medium_layer")
    if not layer_case_ids["frontier"]:
        gaps.append("missing_frontier_layer")
    if unknown_failures:
        gaps.append("unclassified_baseline_failures")
    if len(layer_case_ids["hard"]) > 0 and len(layer_case_ids["medium"]) == 0:
        gaps.append("hard_pack_cannot_be_sole_comparison_set")

    return {
        "version": version,
        "analysis_scope": "benchmark_v1_relayer",
        "status": "REVIEW" if gaps else "PASS",
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "artifact_complete": True,
        "readiness_status": "benchmark_layers_incomplete" if gaps else "benchmark_layers_ready",
        "layer_case_ids": layer_case_ids,
        "layer_counts": {layer: len(layer_case_ids[layer]) for layer in layer_names()},
        "unstable_case_ids": unstable_case_ids,
        "unclassified_baseline_failure_ids": unknown_failures,
        "gap_count": len(gaps),
        "gaps": gaps,
        "next_actions": [
            "add_sanity_pack",
            "construct_medium_hard_core",
            "separate_holdout_from_train_candidate",
            "fill_positive_supervision_or_reference_repair_labels",
        ],
    }


def write_benchmark_v1_relayer_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for layer, case_ids in summary["layer_case_ids"].items():
        (out_dir / f"{layer}_case_ids.txt").write_text("\n".join(case_ids) + ("\n" if case_ids else ""), encoding="utf-8")


def run_benchmark_v1_relayer(
    *,
    hard_pack_path: Path = DEFAULT_HARD_PACK,
    comparison_baseline_path: Path = DEFAULT_COMPARISON_BASELINE,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_benchmark_v1_relayer(
        hard_pack_summary=load_json(hard_pack_path),
        comparison_baseline_summary=load_json(comparison_baseline_path),
    )
    write_benchmark_v1_relayer_outputs(out_dir=out_dir, summary=summary)
    return summary
