from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_jsonl


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXAMPLES = REPO_ROOT / "artifacts" / "residual_candidate_training_schema_v0_47_0" / "training_examples.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "positive_supervision_queue_v0_47_2"


REQUIRED_LABEL_FIELDS = (
    "accepted_next_action_family",
    "minimal_contract_change_summary",
    "why_failed_candidate_family_was_wrong",
    "verification_requirement",
)


def build_positive_supervision_queue(
    *,
    examples: list[dict[str, Any]],
    version: str = "v0.47.2",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    seen_cases: set[str] = set()
    for example in sorted(examples, key=lambda item: str(item.get("case_id") or "")):
        case_id = str(example.get("case_id") or "")
        if not case_id or case_id in seen_cases:
            continue
        seen_cases.add(case_id)
        rows.append(
            {
                "case_id": case_id,
                "queue_role": "positive_supervision_required",
                "source_example_mapping_gap_label": str(example.get("mapping_gap_label") or ""),
                "residual_signal_sequence": list(example.get("residual_signal_sequence") or []),
                "detected_candidate_families": list(example.get("detected_candidate_families") or []),
                "untried_candidate_families": list(example.get("untried_candidate_families") or []),
                "required_label_fields": list(REQUIRED_LABEL_FIELDS),
                "allowed_label_sources": [
                    "human_reviewed_minimal_contract_change",
                    "source_backed_reference_model_diff",
                    "successful_repaired_trajectory",
                ],
                "forbidden_label_sources": [
                    "wrapper_generated_patch",
                    "hidden_candidate_routing",
                    "inferred_correct_answer_from_failed_trajectory_only",
                ],
                "label_status": "missing",
            }
        )
    summary = {
        "version": version,
        "analysis_scope": "positive_supervision_queue",
        "status": "PASS" if rows else "REVIEW",
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "queue_case_count": len(rows),
        "required_label_fields": list(REQUIRED_LABEL_FIELDS),
        "label_status_counts": {"missing": len(rows)},
        "dataset_contract": {
            "contains_reference_solution": False,
            "contains_wrapper_repair": False,
            "contains_generated_patch": False,
            "purpose": "positive_supervision_intake_before_repair_policy_training",
        },
        "decision": "collect_positive_supervision_before_training_repair_policy",
        "scope_note": (
            "This queue records what must be labeled next. It deliberately contains no answer, no patch, no hidden "
            "oracle content, and no live-runner routing instruction."
        ),
    }
    return summary, rows


def write_positive_supervision_queue_outputs(
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
    with (out_dir / "annotation_queue.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def run_positive_supervision_queue(
    *,
    examples_path: Path = DEFAULT_EXAMPLES,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary, rows = build_positive_supervision_queue(examples=load_jsonl(examples_path))
    write_positive_supervision_queue_outputs(out_dir=out_dir, summary=summary, rows=rows)
    return summary
