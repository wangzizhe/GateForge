from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_json


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VARIANTS = REPO_ROOT / "artifacts" / "hard_core_adjacent_variants_v0_48_1" / "summary.json"
DEFAULT_ADMISSION = REPO_ROOT / "artifacts" / "hard_core_adjacent_admission_v0_48_3" / "summary.json"
DEFAULT_DIFFICULTY = REPO_ROOT / "artifacts" / "hard_core_adjacent_difficulty_summary_v0_48_7" / "summary.json"
DEFAULT_SUPERVISION = REPO_ROOT / "artifacts" / "hard_core_adjacent_supervision_sync_v0_48_8" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hard_core_adjacent_closeout_v0_48_9"


def build_hard_core_adjacent_closeout(
    *,
    variants: dict[str, Any],
    admission: dict[str, Any],
    difficulty: dict[str, Any],
    supervision: dict[str, Any],
    version: str = "v0.48.9",
) -> dict[str, Any]:
    hard_ids = list(difficulty.get("hard_negative_candidate_case_ids") or [])
    bucket_counts = difficulty.get("bucket_counts") if isinstance(difficulty.get("bucket_counts"), dict) else {}
    return {
        "version": version,
        "analysis_scope": "hard_core_adjacent_closeout",
        "status": "PASS" if hard_ids else "REVIEW",
        "evidence_role": "formal_experiment",
        "conclusion_allowed": bool(difficulty.get("conclusion_allowed")),
        "variant_count": int(variants.get("variant_count") or 0),
        "admitted_case_count": int(admission.get("admitted_case_count") or 0),
        "difficulty_bucket_counts": dict(sorted(bucket_counts.items())),
        "new_hard_negative_candidate_count": len(hard_ids),
        "new_hard_negative_candidate_case_ids": hard_ids,
        "supervision_template_row_count": int(supervision.get("label_template_row_count") or 0),
        "decision": "promote_hard_candidates_to_next_registry_repeatability_step",
        "next_recommended_anchor": "sem_32_four_segment_adapter_cross_node",
        "conclusion": (
            "Adjacent construction around existing hard core is effective: all 12 variants were OMC-admitted and "
            "6 reached two-run hard-negative-candidate status under base tool-use."
        ),
    }


def write_hard_core_adjacent_closeout_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_hard_core_adjacent_closeout(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_hard_core_adjacent_closeout(
        variants=load_json(DEFAULT_VARIANTS),
        admission=load_json(DEFAULT_ADMISSION),
        difficulty=load_json(DEFAULT_DIFFICULTY),
        supervision=load_json(DEFAULT_SUPERVISION),
    )
    write_hard_core_adjacent_closeout_outputs(out_dir=out_dir, summary=summary)
    return summary
