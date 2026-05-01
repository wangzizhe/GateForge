from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIRS = {
    "selection_run_01": REPO_ROOT / "artifacts" / "semantic_memory_selection_probe_v0_34_4_sem19_run_01",
    "selection_run_02": REPO_ROOT / "artifacts" / "semantic_memory_selection_probe_v0_34_4_sem19_run_02",
    "focused_memory_run": REPO_ROOT / "artifacts" / "semantic_memory_focus_probe_v0_34_6_sem19_run_01",
    "focused_checkpoint_run": REPO_ROOT / "artifacts" / "semantic_memory_focus_checkpoint_probe_v0_34_7_sem19_run_01",
}
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "semantic_memory_boundary_attribution_v0_34_7"


def _success_seen(row: dict[str, Any]) -> bool:
    for step in row.get("steps", []):
        if not isinstance(step, dict):
            continue
        for result in step.get("tool_results", []):
            if not isinstance(result, dict):
                continue
            if result.get("name") in {"check_model", "simulate_model"} and 'resultFile = "/workspace/' in str(result.get("result") or ""):
                return True
    return False


def _selection_units(row: dict[str, Any]) -> list[str]:
    selected: set[str] = set()
    for step in row.get("steps", []):
        if not isinstance(step, dict):
            continue
        for call in step.get("tool_calls", []):
            if not isinstance(call, dict) or call.get("name") != "record_semantic_memory_selection":
                continue
            args = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
            for unit_id in args.get("selected_unit_ids", []):
                if str(unit_id).strip():
                    selected.add(str(unit_id).strip())
    return sorted(selected)


def _critique_concerns(row: dict[str, Any]) -> list[dict[str, Any]]:
    concerns: list[dict[str, Any]] = []
    for step in row.get("steps", []):
        if not isinstance(step, dict):
            continue
        for call in step.get("tool_calls", []):
            if not isinstance(call, dict) or call.get("name") != "candidate_acceptance_critique":
                continue
            args = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
            concern = str(args.get("concern") or "")
            constraints = args.get("task_constraints") if isinstance(args.get("task_constraints"), list) else []
            concerns.append(
                {
                    "step": step.get("step"),
                    "omc_passed": bool(args.get("omc_passed")),
                    "constraint_count": len(constraints),
                    "mentions_reusable_contract": "reusable" in concern.lower() or "contract" in concern.lower(),
                    "mentions_success": "compiles" in concern.lower() or "simulates" in concern.lower(),
                }
            )
    return concerns


def _run_row(run_id: str, run_dir: Path) -> dict[str, Any] | None:
    rows = load_jsonl(run_dir / "results.jsonl")
    if not rows:
        return None
    row = rows[0]
    return {
        "run_id": run_id,
        "case_id": str(row.get("case_id") or ""),
        "final_verdict": str(row.get("final_verdict") or ""),
        "submitted": bool(row.get("submitted")),
        "provider_error": str(row.get("provider_error") or ""),
        "success_candidate_seen": _success_seen(row),
        "selected_units": _selection_units(row),
        "critique_concerns": _critique_concerns(row),
        "tool_sequence": [
            str(call.get("name") or "")
            for step in row.get("steps", [])
            if isinstance(step, dict)
            for call in step.get("tool_calls", [])
            if isinstance(call, dict)
        ],
    }


def build_semantic_memory_boundary_attribution(
    *,
    run_dirs: dict[str, Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    active = run_dirs or DEFAULT_RUN_DIRS
    rows: list[dict[str, Any]] = []
    missing_runs: list[str] = []
    for run_id, run_dir in sorted(active.items()):
        row = _run_row(run_id, run_dir)
        if row is None:
            missing_runs.append(run_id)
            continue
        rows.append(row)
    success_seen_count = sum(1 for row in rows if row["success_candidate_seen"])
    submitted_count = sum(1 for row in rows if row["submitted"])
    standard_library_selection_count = sum(
        1 for row in rows if "standard_library_semantic_substitution" in row["selected_units"]
    )
    reusable_contract_concern_count = sum(
        1
        for row in rows
        for concern in row["critique_concerns"]
        if concern["mentions_reusable_contract"]
    )
    if success_seen_count and not submitted_count and reusable_contract_concern_count:
        decision = "semantic_memory_exposes_oracle_boundary_gap"
    elif standard_library_selection_count and not submitted_count:
        decision = "semantic_memory_selection_prefers_unstable_memory_unit"
    elif submitted_count:
        decision = "semantic_memory_boundary_positive_signal"
    else:
        decision = "semantic_memory_boundary_attribution_inconclusive"
    summary = {
        "version": "v0.34.7",
        "status": "PASS" if rows and not missing_runs else "REVIEW",
        "analysis_scope": "semantic_memory_boundary_attribution",
        "run_count": len(rows),
        "success_candidate_seen_count": success_seen_count,
        "submitted_count": submitted_count,
        "standard_library_selection_count": standard_library_selection_count,
        "reusable_contract_concern_count": reusable_contract_concern_count,
        "missing_runs": missing_runs,
        "runs": rows,
        "decision": decision,
        "discipline": {
            "deterministic_repair_added": False,
            "candidate_selection_added": False,
            "auto_submit_added": False,
            "wrapper_patch_generated": False,
            "oracle_extended": False,
        },
    }
    write_outputs(out_dir=out_dir, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
