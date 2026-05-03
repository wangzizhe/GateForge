from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_agent_comparison_protocol_v0_50_0 import PILOT_CASE_IDS
from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_json, load_jsonl


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TASK_ROOTS = (
    REPO_ROOT / "assets_private" / "benchmarks" / "agent_comparison_v1" / "tasks" / "repair",
    REPO_ROOT / "artifacts" / "hard_core_adjacent_variants_v0_48_1" / "task_files",
)
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "external_agent_task_bundle_v0_50_2"


def _load_task(case_id: str, roots: tuple[Path, ...]) -> dict[str, Any]:
    for root in roots:
        payload = load_json(root / f"{case_id}.json")
        if payload:
            return payload
    return {}


def build_external_agent_task_bundle(
    *,
    case_ids: tuple[str, ...] = PILOT_CASE_IDS,
    task_roots: tuple[Path, ...] = DEFAULT_TASK_ROOTS,
    version: str = "v0.50.2",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    tasks: list[dict[str, Any]] = []
    missing: list[str] = []
    for case_id in case_ids:
        task = _load_task(case_id, task_roots)
        if not task:
            missing.append(case_id)
            continue
        tasks.append(
            {
                "case_id": case_id,
                "title": str(task.get("title") or ""),
                "description": str(task.get("description") or ""),
                "constraints": list(task.get("constraints") or []),
                "initial_model": str(task.get("initial_model") or ""),
                "verification_command": (
                    "Run OpenModelica checkModel and simulate for the submitted model. "
                    "A valid submission must compile and simulate successfully."
                ),
                "submission_format": {
                    "final_model_text": "full repaired Modelica model",
                    "final_verdict": "PASS or FAIL",
                    "notes": "brief explanation of attempted repair",
                },
            }
        )
    summary = {
        "version": version,
        "analysis_scope": "external_agent_task_bundle",
        "status": "PASS" if tasks and not missing else "REVIEW",
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "task_count": len(tasks),
        "missing_case_ids": missing,
        "case_ids": [task["case_id"] for task in tasks],
        "leakage_contract": {
            "contains_hidden_oracle": False,
            "contains_reference_solution": False,
            "contains_gateforge_internal_artifacts": False,
        },
    }
    return summary, tasks


def write_external_agent_task_bundle_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
    tasks: list[dict[str, Any]],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "tasks.jsonl").open("w", encoding="utf-8") as fh:
        for task in tasks:
            fh.write(json.dumps(task, sort_keys=True) + "\n")


def run_external_agent_task_bundle(*, out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    summary, tasks = build_external_agent_task_bundle()
    write_external_agent_task_bundle_outputs(out_dir=out_dir, summary=summary, tasks=tasks)
    return summary
