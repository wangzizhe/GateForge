from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_semantic_memory_units_v0_34_0 import (
    SEMANTIC_MEMORY_UNITS,
    render_memory_units,
    validate_memory_unit,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "semantic_memory_focus_v0_34_6"
DEFAULT_FOCUS_UNIT_IDS = ["arrayed_measurement_flow_ownership"]


def select_memory_units(unit_ids: list[str]) -> list[dict[str, Any]]:
    wanted = set(unit_ids)
    return [unit for unit in SEMANTIC_MEMORY_UNITS if str(unit.get("unit_id") or "") in wanted]


def build_semantic_memory_focus(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    unit_ids: list[str] | None = None,
) -> dict[str, Any]:
    active_ids = unit_ids or DEFAULT_FOCUS_UNIT_IDS
    units = select_memory_units(active_ids)
    invalid_units = {
        str(unit.get("unit_id") or index): errors
        for index, unit in enumerate(units)
        if (errors := validate_memory_unit(unit))
    }
    missing_unit_ids = sorted(set(active_ids) - {str(unit.get("unit_id") or "") for unit in units})
    context_text = render_memory_units(units)
    summary = {
        "version": "v0.34.6",
        "status": "PASS" if units and not invalid_units and not missing_unit_ids else "REVIEW",
        "analysis_scope": "semantic_memory_focus",
        "focus_unit_ids": active_ids,
        "unit_count": len(units),
        "missing_unit_ids": missing_unit_ids,
        "invalid_units": invalid_units,
        "context_chars": len(context_text),
        "context_path": str(out_dir / "semantic_memory_focus_context.md"),
        "decision": "semantic_memory_focus_ready_for_live_probe" if units and not invalid_units and not missing_unit_ids else "semantic_memory_focus_needs_review",
        "discipline": {
            "manual_ablation_not_default": True,
            "deterministic_repair_added": False,
            "candidate_selection_added": False,
            "auto_submit_added": False,
            "wrapper_patch_generated": False,
        },
    }
    write_outputs(out_dir=out_dir, summary=summary, context_text=context_text)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any], context_text: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "semantic_memory_focus_context.md").write_text(context_text, encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
