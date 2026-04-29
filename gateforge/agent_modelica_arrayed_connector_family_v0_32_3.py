from __future__ import annotations

from pathlib import Path
from typing import Any

from .agent_modelica_hard_family_expansion_v0_32_0 import build_hard_family_expansion_summary

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TASK_ROOT = REPO_ROOT / "assets_private" / "benchmarks" / "agent_comparison_v1" / "tasks" / "repair"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "arrayed_connector_family_v0_32_3"

V0323_CASE_IDS = (
    "sem_19_arrayed_shared_probe_bus",
    "sem_20_arrayed_adapter_cross_node",
    "sem_21_arrayed_mixed_probe_contract",
)


def build_arrayed_connector_family_summary(
    *,
    task_root: Path = DEFAULT_TASK_ROOT,
    out_dir: Path = DEFAULT_OUT_DIR,
    case_ids: tuple[str, ...] = V0323_CASE_IDS,
) -> dict[str, Any]:
    summary = build_hard_family_expansion_summary(
        task_root=task_root,
        out_dir=out_dir,
        case_ids=case_ids,
    )
    summary["version"] = "v0.32.3"
    summary["analysis_scope"] = "arrayed_connector_family_expansion"
    summary["decision"] = (
        "arrayed_connector_family_ready_for_live_baseline"
        if summary.get("status") == "PASS"
        else "arrayed_connector_family_needs_review"
    )
    return summary
