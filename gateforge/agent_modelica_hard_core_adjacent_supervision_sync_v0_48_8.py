from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_json
from .agent_modelica_positive_supervision_label_template_v0_47_5 import build_positive_supervision_label_template


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIFFICULTY = REPO_ROOT / "artifacts" / "hard_core_adjacent_difficulty_summary_v0_48_7" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hard_core_adjacent_supervision_sync_v0_48_8"


def _queue_rows_from_difficulty(difficulty_summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in difficulty_summary.get("results") or []:
        if str(result.get("difficulty_bucket") or "") != "hard_negative_candidate":
            continue
        rows.append(
            {
                "case_id": str(result.get("case_id") or ""),
                "source_example_mapping_gap_label": "hard_core_adjacent_repeatable_failure",
                "residual_signal_sequence": [],
                "detected_candidate_families": [],
                "untried_candidate_families": [],
            }
        )
    return rows


def build_hard_core_adjacent_supervision_sync(
    *,
    difficulty_summary: dict[str, Any],
    version: str = "v0.48.8",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    queue_rows = _queue_rows_from_difficulty(difficulty_summary)
    template_summary, template_rows = build_positive_supervision_label_template(queue_rows=queue_rows)
    summary = {
        "version": version,
        "analysis_scope": "hard_core_adjacent_supervision_sync",
        "status": "PASS" if queue_rows else "REVIEW",
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "hard_candidate_count": len(queue_rows),
        "label_template_row_count": len(template_rows),
        "case_ids": [row["case_id"] for row in template_rows],
        "template_contract": template_summary["dataset_contract"],
        "decision": "attach_blank_positive_supervision_templates_to_new_hard_candidates",
    }
    return summary, template_rows


def write_hard_core_adjacent_supervision_sync_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
    template_rows: list[dict[str, Any]],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "labels_template.jsonl").open("w", encoding="utf-8") as fh:
        for row in template_rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def run_hard_core_adjacent_supervision_sync(
    *,
    difficulty_path: Path = DEFAULT_DIFFICULTY,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary, template_rows = build_hard_core_adjacent_supervision_sync(difficulty_summary=load_json(difficulty_path))
    write_hard_core_adjacent_supervision_sync_outputs(out_dir=out_dir, summary=summary, template_rows=template_rows)
    return summary
