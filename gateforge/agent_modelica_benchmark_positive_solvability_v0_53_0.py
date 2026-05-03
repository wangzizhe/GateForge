from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_json


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HARD_PACK = REPO_ROOT / "artifacts" / "hard_benchmark_pack_v0_49_2" / "summary.json"
DEFAULT_SOURCE_INVENTORY = REPO_ROOT / "artifacts" / "positive_supervision_source_inventory_v0_47_4" / "summary.json"
DEFAULT_LABEL_GATE = REPO_ROOT / "artifacts" / "positive_supervision_label_gate_v0_47_3" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "benchmark_positive_solvability_v0_53_0"


def _case_ids(rows: list[dict[str, Any]], *, field: str, value: str) -> list[str]:
    return sorted(
        str(row.get("case_id") or "")
        for row in rows
        if str(row.get(field) or "") == value and str(row.get("case_id") or "")
    )


def build_benchmark_positive_solvability_audit(
    *,
    hard_pack_summary: dict[str, Any],
    source_inventory_summary: dict[str, Any],
    label_gate_summary: dict[str, Any],
    version: str = "v0.53.0",
) -> dict[str, Any]:
    hard_case_ids = sorted(str(case_id) for case_id in hard_pack_summary.get("hard_case_ids") or [])
    hard_set = set(hard_case_ids)
    source_available = [
        case_id
        for case_id in _case_ids(source_inventory_summary.get("results") or [], field="positive_source_status", value="source_available")
        if case_id in hard_set
    ]
    accepted_labels = [
        case_id
        for case_id in _case_ids(label_gate_summary.get("results") or [], field="label_status", value="PASS")
        if case_id in hard_set
    ]
    positive_evidence = sorted(set(source_available + accepted_labels))
    missing = sorted(case_id for case_id in hard_case_ids if case_id not in positive_evidence)
    label_ready_missing = sorted(case_id for case_id in hard_case_ids if case_id not in set(accepted_labels))
    gaps: list[str] = []
    if missing:
        gaps.append("missing_positive_solvability_source_for_hard_cases")
    if label_ready_missing:
        gaps.append("missing_reference_ready_positive_labels")
    return {
        "version": version,
        "analysis_scope": "benchmark_positive_solvability_audit",
        "status": "REVIEW" if gaps else "PASS",
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "artifact_complete": True,
        "readiness_status": "positive_solvability_incomplete" if gaps else "positive_solvability_ready",
        "hard_case_count": len(hard_case_ids),
        "positive_source_available_count": len(source_available),
        "accepted_positive_label_count": len(accepted_labels),
        "positive_evidence_case_count": len(positive_evidence),
        "missing_positive_source_count": len(missing),
        "missing_reference_label_count": len(label_ready_missing),
        "positive_source_available_case_ids": source_available,
        "accepted_positive_label_case_ids": accepted_labels,
        "missing_positive_source_case_ids": missing,
        "missing_reference_label_case_ids": label_ready_missing,
        "gaps": gaps,
        "benchmark_use": {
            "hard_negative_boundary_use_allowed": bool(hard_case_ids),
            "full_solvable_scoring_use_allowed": not missing,
            "training_use_allowed": not label_ready_missing,
            "hidden_reference_may_enter_prompt": False,
        },
        "next_actions": [
            "derive_or_review_reference_repairs_for_missing_cases",
            "record_minimal_contract_change_labels",
            "keep_reference_repairs_hidden_from_agent_prompts",
        ],
    }


def write_benchmark_positive_solvability_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "missing_positive_source_case_ids.txt").write_text(
        "\n".join(summary["missing_positive_source_case_ids"]) + ("\n" if summary["missing_positive_source_case_ids"] else ""),
        encoding="utf-8",
    )


def run_benchmark_positive_solvability_audit(
    *,
    hard_pack_path: Path = DEFAULT_HARD_PACK,
    source_inventory_path: Path = DEFAULT_SOURCE_INVENTORY,
    label_gate_path: Path = DEFAULT_LABEL_GATE,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_benchmark_positive_solvability_audit(
        hard_pack_summary=load_json(hard_pack_path),
        source_inventory_summary=load_json(source_inventory_path),
        label_gate_summary=load_json(label_gate_path),
    )
    write_benchmark_positive_solvability_outputs(out_dir=out_dir, summary=summary)
    return summary
