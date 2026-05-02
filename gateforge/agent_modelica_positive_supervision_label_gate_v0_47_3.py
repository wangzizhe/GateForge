from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_jsonl
from .agent_modelica_positive_supervision_queue_v0_47_2 import REQUIRED_LABEL_FIELDS


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QUEUE = REPO_ROOT / "artifacts" / "positive_supervision_queue_v0_47_2" / "annotation_queue.jsonl"
DEFAULT_LABELS = REPO_ROOT / "artifacts" / "positive_supervision_queue_v0_47_2" / "labels.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "positive_supervision_label_gate_v0_47_3"

ALLOWED_LABEL_SOURCES = {
    "human_reviewed_minimal_contract_change",
    "source_backed_reference_model_diff",
    "successful_repaired_trajectory",
}

FORBIDDEN_LABEL_SOURCES = {
    "wrapper_generated_patch",
    "hidden_candidate_routing",
    "inferred_correct_answer_from_failed_trajectory_only",
}


def _labels_by_case(labels: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for label in labels:
        case_id = str(label.get("case_id") or "")
        if case_id:
            out[case_id] = label
    return out


def validate_positive_supervision_label(label: dict[str, Any]) -> tuple[str, list[str]]:
    issues: list[str] = []
    source = str(label.get("label_source") or "")
    if source not in ALLOWED_LABEL_SOURCES:
        issues.append("label_source_not_allowed")
    if source in FORBIDDEN_LABEL_SOURCES:
        issues.append("forbidden_label_source")
    for field in REQUIRED_LABEL_FIELDS:
        if not str(label.get(field) or "").strip():
            issues.append(f"missing_{field}")
    if bool(label.get("contains_wrapper_repair")):
        issues.append("contains_wrapper_repair")
    if bool(label.get("used_hidden_routing")):
        issues.append("used_hidden_routing")
    if bool(label.get("inferred_from_failed_trajectory_only")):
        issues.append("inferred_from_failed_trajectory_only")
    return ("PASS" if not issues else "REVIEW"), issues


def build_positive_supervision_label_gate(
    *,
    queue_rows: list[dict[str, Any]],
    labels: list[dict[str, Any]],
    version: str = "v0.47.3",
) -> dict[str, Any]:
    labels_by_case = _labels_by_case(labels)
    results: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}
    for row in queue_rows:
        case_id = str(row.get("case_id") or "")
        label = labels_by_case.get(case_id)
        if not label:
            status = "MISSING"
            issues = ["missing_label"]
        else:
            status, issues = validate_positive_supervision_label(label)
        status_counts[status] = status_counts.get(status, 0) + 1
        results.append(
            {
                "case_id": case_id,
                "label_status": status,
                "issues": issues,
            }
        )
    accepted_count = status_counts.get("PASS", 0)
    summary_status = "PASS" if queue_rows and accepted_count == len(queue_rows) else "REVIEW"
    return {
        "version": version,
        "analysis_scope": "positive_supervision_label_gate",
        "status": summary_status,
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "queue_case_count": len(queue_rows),
        "provided_label_count": len(labels_by_case),
        "accepted_label_count": accepted_count,
        "label_status_counts": dict(sorted(status_counts.items())),
        "results": sorted(results, key=lambda item: item["case_id"]),
        "admission_contract": {
            "required_label_fields": list(REQUIRED_LABEL_FIELDS),
            "allowed_label_sources": sorted(ALLOWED_LABEL_SOURCES),
            "forbidden_label_sources": sorted(FORBIDDEN_LABEL_SOURCES),
            "labels_may_be_used_for_training": bool(queue_rows and accepted_count == len(queue_rows)),
            "labels_may_be_used_as_wrapper_logic": False,
        },
        "decision": "block_repair_policy_training_until_all_labels_pass_gate",
        "scope_note": (
            "This gate validates label provenance and completeness. It does not generate labels, generate patches, "
            "route candidates, or change live Agent behavior."
        ),
    }


def write_positive_supervision_label_gate_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_positive_supervision_label_gate(
    *,
    queue_path: Path = DEFAULT_QUEUE,
    labels_path: Path = DEFAULT_LABELS,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_positive_supervision_label_gate(
        queue_rows=load_jsonl(queue_path),
        labels=load_jsonl(labels_path),
    )
    write_positive_supervision_label_gate_outputs(out_dir=out_dir, summary=summary)
    return summary
