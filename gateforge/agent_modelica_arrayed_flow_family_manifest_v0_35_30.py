from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TASK_ROOT = REPO_ROOT / "assets_private" / "benchmarks" / "agent_comparison_v1" / "tasks" / "repair"
DEFAULT_CASE_IDS = [
    "sem_19_arrayed_shared_probe_bus",
    "sem_20_arrayed_adapter_cross_node",
    "sem_21_arrayed_mixed_probe_contract",
    "sem_22_arrayed_three_branch_probe_bus",
    "sem_23_nested_probe_contract_bus",
    "sem_24_bridge_probe_transfer_bus",
]
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "arrayed_flow_family_manifest_v0_35_30"


def _load_task(task_root: Path, case_id: str) -> dict[str, Any] | None:
    path = task_root / f"{case_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _case_features(task: dict[str, Any]) -> dict[str, Any]:
    model_text = str(task.get("initial_model") or "")
    text = model_text.lower()
    return {
        "case_id": str(task.get("case_id") or ""),
        "title": str(task.get("title") or ""),
        "has_arrayed_connectors": bool(re.search(r"\bpin\s+[A-Za-z_][A-Za-z0-9_]*\s*\[", model_text, re.IGNORECASE)),
        "has_for_loop_connects": "for " in text and "connect(" in text,
        "has_replaceable_interface": "replaceable model" in text,
        "has_partial_base": "partial model" in text,
        "has_probe_or_adapter": any(token in text for token in ("probe", "adapter", "monitor")),
        "has_flow_connector": "flow real" in text,
        "workflow_constraints": [str(item) for item in task.get("constraints") or []],
    }


def build_arrayed_flow_family_manifest(
    *,
    task_root: Path = DEFAULT_TASK_ROOT,
    case_ids: list[str] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    ids = case_ids or DEFAULT_CASE_IDS
    cases: list[dict[str, Any]] = []
    missing_case_ids: list[str] = []
    for case_id in ids:
        task = _load_task(task_root, case_id)
        if task is None:
            missing_case_ids.append(case_id)
            continue
        cases.append(_case_features(task))
    family_feature_counts = {
        "arrayed_connectors": sum(1 for case in cases if case["has_arrayed_connectors"]),
        "for_loop_connects": sum(1 for case in cases if case["has_for_loop_connects"]),
        "replaceable_interface": sum(1 for case in cases if case["has_replaceable_interface"]),
        "partial_base": sum(1 for case in cases if case["has_partial_base"]),
        "probe_or_adapter": sum(1 for case in cases if case["has_probe_or_adapter"]),
        "flow_connector": sum(1 for case in cases if case["has_flow_connector"]),
    }
    summary = {
        "version": "v0.35.30",
        "status": "PASS" if cases and not missing_case_ids else "REVIEW",
        "analysis_scope": "arrayed_flow_family_manifest",
        "case_count": len(cases),
        "missing_case_ids": missing_case_ids,
        "case_ids": [case["case_id"] for case in cases],
        "family_feature_counts": family_feature_counts,
        "cases": cases,
        "decision": (
            "arrayed_connector_flow_family_slice_ready"
            if cases and not missing_case_ids
            else "arrayed_connector_flow_family_slice_incomplete"
        ),
        "discipline": {
            "deterministic_repair_added": False,
            "candidate_selection_added": False,
            "auto_submit_added": False,
            "wrapper_patch_generated": False,
        },
    }
    write_outputs(out_dir=out_dir, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
