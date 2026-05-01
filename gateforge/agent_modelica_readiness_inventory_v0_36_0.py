from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_readiness_inventory_v0_36_0"

REQUIRED_COMPONENTS = [
    "tool_use_runner",
    "provider_adapter",
    "artifact_summary",
    "benchmark_task_schema",
    "oracle",
    "repair_report",
]


def classify_component_readiness(component: dict[str, Any]) -> dict[str, Any]:
    name = str(component.get("name") or "")
    present = bool(component.get("present"))
    audited = bool(component.get("audited"))
    gaps = [str(gap) for gap in component.get("gaps", []) if str(gap).strip()]
    status = "PASS" if present and audited and not gaps else "GAP"
    return {
        "name": name,
        "present": present,
        "audited": audited,
        "gaps": gaps,
        "status": status,
    }


def build_readiness_inventory(
    components: list[dict[str, Any]],
    *,
    version: str = "v0.36.0",
) -> dict[str, Any]:
    normalized = [classify_component_readiness(component) for component in components]
    by_name = {row["name"]: row for row in normalized}
    missing = [name for name in REQUIRED_COMPONENTS if name not in by_name]
    gaps = [row for row in normalized if row["status"] != "PASS"]
    status = "PASS" if not missing and not gaps else "REVIEW"
    return {
        "version": version,
        "analysis_scope": "gateforge_agent_readiness_inventory",
        "status": status,
        "readiness_status": "inventory_complete" if status == "PASS" else "inventory_has_gaps",
        "component_count": len(normalized),
        "missing_components": missing,
        "gap_count": len(gaps) + len(missing),
        "components": normalized,
        "discipline": {
            "llm_capability_claim_made": False,
            "pass_rate_claim_made": False,
            "wrapper_repair_added": False,
        },
    }


def write_inventory_outputs(*, out_dir: Path = DEFAULT_OUT_DIR, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_readiness_inventory(
    *,
    components: list[dict[str, Any]] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    default_components = [
        {"name": name, "present": False, "audited": False, "gaps": ["not_provided"]}
        for name in REQUIRED_COMPONENTS
    ]
    summary = build_readiness_inventory(components or default_components)
    write_inventory_outputs(out_dir=out_dir, summary=summary)
    return summary

