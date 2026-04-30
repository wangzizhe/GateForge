from __future__ import annotations

from pathlib import Path
from typing import Any

from .agent_modelica_hard_family_expansion_v0_32_0 import build_hard_family_expansion_summary

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TASK_ROOT = REPO_ROOT / "assets_private" / "benchmarks" / "agent_comparison_v1" / "tasks" / "repair"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "connector_flow_family_expansion_v0_35_0"

V0350_CASE_IDS = (
    "sem_22_arrayed_three_branch_probe_bus",
    "sem_23_nested_probe_contract_bus",
    "sem_24_bridge_probe_transfer_bus",
)


def build_connector_flow_family_expansion_summary(
    *,
    task_root: Path = DEFAULT_TASK_ROOT,
    out_dir: Path = DEFAULT_OUT_DIR,
    case_ids: tuple[str, ...] = V0350_CASE_IDS,
) -> dict[str, Any]:
    summary = build_hard_family_expansion_summary(
        task_root=task_root,
        out_dir=out_dir,
        case_ids=case_ids,
    )
    summary["version"] = "v0.35.0"
    summary["analysis_scope"] = "connector_flow_family_expansion"
    summary["decision"] = (
        "connector_flow_family_ready_for_live_baseline"
        if summary.get("status") == "PASS"
        else "connector_flow_family_needs_review"
    )
    return summary
