from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_jsonl


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXAMPLES = REPO_ROOT / "artifacts" / "residual_candidate_training_schema_v0_47_0" / "training_examples.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "residual_candidate_supervision_audit_v0_47_1"


def _has_positive_supervision(example: dict[str, Any]) -> bool:
    return bool(
        example.get("reference_candidate_family")
        or example.get("minimal_correct_contract_change")
        or example.get("accepted_next_action")
    )


def _is_negative_trajectory(example: dict[str, Any]) -> bool:
    return str(example.get("final_verdict") or "") != "PASS" and not bool(example.get("submitted"))


def build_residual_candidate_supervision_audit(
    *,
    examples: list[dict[str, Any]],
    version: str = "v0.47.1",
) -> dict[str, Any]:
    label_counts: dict[str, int] = {}
    cases: set[str] = set()
    positive_count = 0
    negative_only_count = 0
    for example in examples:
        cases.add(str(example.get("case_id") or ""))
        label = str(example.get("mapping_gap_label") or "unlabeled")
        label_counts[label] = label_counts.get(label, 0) + 1
        if _has_positive_supervision(example):
            positive_count += 1
        elif _is_negative_trajectory(example):
            negative_only_count += 1
    has_enough_positive = positive_count >= max(3, len(cases))
    has_enough_cases = len(cases) >= 4
    trainability_status = (
        "training_ready"
        if has_enough_positive and has_enough_cases
        else "negative_trajectory_schema_ready_positive_supervision_missing"
    )
    return {
        "version": version,
        "analysis_scope": "residual_candidate_supervision_audit",
        "status": "PASS" if examples else "REVIEW",
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "case_count": len([case_id for case_id in cases if case_id]),
        "example_count": len(examples),
        "negative_only_example_count": negative_only_count,
        "positive_supervision_example_count": positive_count,
        "mapping_gap_label_counts": dict(sorted(label_counts.items())),
        "trainability_status": trainability_status,
        "minimum_next_asset": (
            "Add transparent positive supervision: either source-backed accepted next-action labels, "
            "human-reviewed minimal contract-change labels, or successful repaired trajectories. Do not infer "
            "the correct candidate from failed trajectories alone."
        ),
        "dataset_contract": {
            "can_train_failure_classifier": bool(examples),
            "can_train_repair_policy": has_enough_positive and has_enough_cases,
            "contains_reference_solution": any(bool(example.get("input_contract", {}).get("contains_reference_solution")) for example in examples),
            "contains_wrapper_repair": any(bool(example.get("input_contract", {}).get("contains_wrapper_repair")) for example in examples),
        },
        "decision": "do_not_train_repair_policy_until_positive_supervision_exists",
        "scope_note": (
            "This audit decides data readiness only. It does not recover correct answers, generate patches, "
            "route candidates, or change live Agent behavior."
        ),
    }


def write_residual_candidate_supervision_audit_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_residual_candidate_supervision_audit(
    *,
    examples_path: Path = DEFAULT_EXAMPLES,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_residual_candidate_supervision_audit(examples=load_jsonl(examples_path))
    write_residual_candidate_supervision_audit_outputs(out_dir=out_dir, summary=summary)
    return summary
