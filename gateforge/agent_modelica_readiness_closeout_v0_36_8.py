from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_readiness_closeout_v0_36_8"


def build_readiness_closeout(
    component_summaries: list[dict[str, Any]],
    *,
    version: str = "v0.36.8",
) -> dict[str, Any]:
    incomplete = [
        str(summary.get("version") or summary.get("analysis_scope") or "unknown")
        for summary in component_summaries
        if str(summary.get("status") or "") not in {"PASS"}
        or str(summary.get("readiness_status") or "") == "readiness_incomplete"
    ]
    return {
        "version": version,
        "analysis_scope": "gateforge_agent_readiness_closeout",
        "status": "PASS" if not incomplete else "REVIEW",
        "readiness_status": "readiness_complete" if not incomplete else "readiness_incomplete",
        "component_count": len(component_summaries),
        "incomplete_components": incomplete,
        "conclusion": (
            "GateForge Agent readiness contract is complete."
            if not incomplete
            else "GateForge Agent readiness contract still has open gaps."
        ),
        "scope_note": (
            "This closeout only evaluates harness readiness. It does not reinterpret Dyad methodology, "
            "expand benchmarks, train models, or claim pass-rate gains."
        ),
        "component_summaries": component_summaries,
    }


def write_readiness_closeout_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
