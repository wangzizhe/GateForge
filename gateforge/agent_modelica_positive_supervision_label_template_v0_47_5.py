from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_jsonl
from .agent_modelica_positive_supervision_label_gate_v0_47_3 import (
    ALLOWED_LABEL_SOURCES,
    FORBIDDEN_LABEL_SOURCES,
)
from .agent_modelica_positive_supervision_queue_v0_47_2 import REQUIRED_LABEL_FIELDS


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QUEUE = REPO_ROOT / "artifacts" / "positive_supervision_queue_v0_47_2" / "annotation_queue.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "positive_supervision_label_template_v0_47_5"


def build_label_template_rows(queue_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in sorted(queue_rows, key=lambda item: str(item.get("case_id") or "")):
        rows.append(
            {
                "case_id": str(row.get("case_id") or ""),
                "label_source": "",
                "accepted_next_action_family": "",
                "minimal_contract_change_summary": "",
                "why_failed_candidate_family_was_wrong": "",
                "verification_requirement": "",
                "reviewer": "",
                "review_notes": "",
                "contains_wrapper_repair": False,
                "used_hidden_routing": False,
                "inferred_from_failed_trajectory_only": False,
                "context": {
                    "source_example_mapping_gap_label": str(row.get("source_example_mapping_gap_label") or ""),
                    "residual_signal_sequence": list(row.get("residual_signal_sequence") or []),
                    "detected_candidate_families": list(row.get("detected_candidate_families") or []),
                    "untried_candidate_families": list(row.get("untried_candidate_families") or []),
                },
            }
        )
    return rows


def build_positive_supervision_label_template(
    *,
    queue_rows: list[dict[str, Any]],
    version: str = "v0.47.5",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = build_label_template_rows(queue_rows)
    summary = {
        "version": version,
        "analysis_scope": "positive_supervision_label_template",
        "status": "PASS" if rows else "REVIEW",
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "template_row_count": len(rows),
        "required_label_fields": list(REQUIRED_LABEL_FIELDS),
        "allowed_label_sources": sorted(ALLOWED_LABEL_SOURCES),
        "forbidden_label_sources": sorted(FORBIDDEN_LABEL_SOURCES),
        "dataset_contract": {
            "contains_reference_solution": False,
            "contains_wrapper_repair": False,
            "contains_generated_patch": False,
            "ready_for_manual_annotation": bool(rows),
        },
        "decision": "fill_labels_then_run_positive_supervision_label_gate",
        "scope_note": (
            "This template is an annotation carrier only. Blank label fields are intentional; it does not generate "
            "answers, patches, candidate choices, or live-runner hints."
        ),
    }
    return summary, rows


def write_positive_supervision_label_template_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "labels_template.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def run_positive_supervision_label_template(
    *,
    queue_path: Path = DEFAULT_QUEUE,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary, rows = build_positive_supervision_label_template(queue_rows=load_jsonl(queue_path))
    write_positive_supervision_label_template_outputs(out_dir=out_dir, summary=summary, rows=rows)
    return summary
