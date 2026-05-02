from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_jsonl


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QUEUE = REPO_ROOT / "artifacts" / "positive_supervision_queue_v0_47_2" / "annotation_queue.jsonl"
DEFAULT_TASK_DIR = REPO_ROOT / "assets_private" / "benchmarks" / "agent_comparison_v1" / "tasks" / "repair"
DEFAULT_ARTIFACT_ROOT = REPO_ROOT / "artifacts"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "positive_supervision_source_inventory_v0_47_4"

REFERENCE_FIELDS = {
    "reference_model",
    "repaired_model",
    "expected_model",
    "source_model",
    "reference_diff",
    "minimal_contract_change",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _task_reference_fields(task_dir: Path, case_id: str) -> list[str]:
    payload = load_json(task_dir / f"{case_id}.json")
    return sorted(field for field in REFERENCE_FIELDS if field in payload)


def _successful_trajectory_paths(artifact_root: Path, case_id: str) -> list[str]:
    paths: list[str] = []
    if not artifact_root.exists():
        return paths
    for result_path in artifact_root.glob("**/results.jsonl"):
        for row in load_jsonl(result_path):
            if str(row.get("case_id") or "") != case_id:
                continue
            if str(row.get("final_verdict") or "") == "PASS" and not row.get("provider_error"):
                paths.append(str(result_path))
                break
    return sorted(paths)


def build_positive_supervision_source_inventory(
    *,
    queue_rows: list[dict[str, Any]],
    task_dir: Path = DEFAULT_TASK_DIR,
    artifact_root: Path = DEFAULT_ARTIFACT_ROOT,
    version: str = "v0.47.4",
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    source_counts = {
        "task_reference_diff_present": 0,
        "successful_repaired_trajectory_present": 0,
        "no_positive_source_found": 0,
    }
    for queue_row in queue_rows:
        case_id = str(queue_row.get("case_id") or "")
        reference_fields = _task_reference_fields(task_dir, case_id)
        success_paths = _successful_trajectory_paths(artifact_root, case_id)
        has_reference = bool(reference_fields)
        has_success = bool(success_paths)
        if has_reference:
            source_counts["task_reference_diff_present"] += 1
        if has_success:
            source_counts["successful_repaired_trajectory_present"] += 1
        if not has_reference and not has_success:
            source_counts["no_positive_source_found"] += 1
        rows.append(
            {
                "case_id": case_id,
                "task_reference_fields": reference_fields,
                "successful_repaired_trajectory_count": len(success_paths),
                "positive_source_status": (
                    "source_available" if has_reference or has_success else "missing_positive_source"
                ),
            }
        )
    return {
        "version": version,
        "analysis_scope": "positive_supervision_source_inventory",
        "status": "PASS" if rows else "REVIEW",
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "case_count": len(rows),
        "source_counts": source_counts,
        "results": sorted(rows, key=lambda item: item["case_id"]),
        "decision": "derive_labels_only_from_available_positive_sources_or_human_review",
        "scope_note": (
            "This inventory only locates possible positive supervision sources. It does not read hidden answers into "
            "the live prompt, generate patches, route candidates, or claim a repair-policy improvement."
        ),
    }


def write_positive_supervision_source_inventory_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_positive_supervision_source_inventory(
    *,
    queue_path: Path = DEFAULT_QUEUE,
    task_dir: Path = DEFAULT_TASK_DIR,
    artifact_root: Path = DEFAULT_ARTIFACT_ROOT,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_positive_supervision_source_inventory(
        queue_rows=load_jsonl(queue_path),
        task_dir=task_dir,
        artifact_root=artifact_root,
    )
    write_positive_supervision_source_inventory_outputs(out_dir=out_dir, summary=summary)
    return summary
