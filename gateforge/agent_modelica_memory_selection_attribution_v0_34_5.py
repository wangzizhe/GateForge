from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_dyad_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIRS = [
    REPO_ROOT / "artifacts" / "semantic_memory_selection_probe_v0_34_4_sem19_run_01",
    REPO_ROOT / "artifacts" / "semantic_memory_selection_probe_v0_34_4_sem19_run_02",
]
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "memory_selection_attribution_v0_34_5"


def _selection_calls(row: dict[str, Any]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for step in row.get("steps", []):
        if not isinstance(step, dict):
            continue
        for call in step.get("tool_calls", []):
            if not isinstance(call, dict) or call.get("name") != "record_semantic_memory_selection":
                continue
            args = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
            calls.append(
                {
                    "step": step.get("step"),
                    "selected_unit_ids": [str(item) for item in args.get("selected_unit_ids", []) if str(item)],
                    "rejected_unit_ids": [str(item) for item in args.get("rejected_unit_ids", []) if str(item)],
                    "rationale_present": bool(str(args.get("rationale") or "").strip()),
                    "risk_present": bool(str(args.get("risk") or "").strip()),
                }
            )
    return calls


def _run_row(run_dir: Path) -> dict[str, Any] | None:
    rows = load_jsonl(run_dir / "results.jsonl")
    if not rows:
        return None
    row = rows[0]
    selections = _selection_calls(row)
    selected_units = sorted({unit for selection in selections for unit in selection["selected_unit_ids"]})
    return {
        "run_id": run_dir.name,
        "case_id": str(row.get("case_id") or ""),
        "final_verdict": str(row.get("final_verdict") or ""),
        "submitted": bool(row.get("submitted")),
        "provider_error": str(row.get("provider_error") or ""),
        "token_used": int(row.get("token_used") or 0),
        "step_count": int(row.get("step_count") or 0),
        "selection_call_count": len(selections),
        "selected_units": selected_units,
        "selection_calls": selections,
    }


def build_memory_selection_attribution(
    *,
    run_dirs: list[Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    dirs = run_dirs or DEFAULT_RUN_DIRS
    missing_runs: list[str] = []
    rows: list[dict[str, Any]] = []
    for run_dir in dirs:
        row = _run_row(run_dir)
        if row is None:
            missing_runs.append(run_dir.name)
            continue
        rows.append(row)
    selected_unit_counts: dict[str, int] = {}
    for row in rows:
        for unit in row["selected_units"]:
            selected_unit_counts[unit] = selected_unit_counts.get(unit, 0) + 1
    pass_count = sum(1 for row in rows if row["final_verdict"] == "PASS")
    selection_call_count = sum(int(row["selection_call_count"]) for row in rows)
    provider_error_count = sum(1 for row in rows if row["provider_error"])
    if selection_call_count and pass_count == 0 and selected_unit_counts:
        decision = "memory_selection_visible_but_not_capability_improving"
    elif pass_count:
        decision = "memory_selection_has_positive_signal"
    elif provider_error_count:
        decision = "memory_selection_blocked_by_provider_errors"
    else:
        decision = "memory_selection_not_invoked"
    summary = {
        "version": "v0.34.5",
        "status": "PASS" if rows and not missing_runs else "REVIEW",
        "analysis_scope": "memory_selection_attribution",
        "run_count": len(rows),
        "pass_count": pass_count,
        "selection_call_count": selection_call_count,
        "provider_error_count": provider_error_count,
        "selected_unit_counts": dict(sorted(selected_unit_counts.items())),
        "missing_runs": missing_runs,
        "runs": rows,
        "decision": decision,
        "discipline": {
            "deterministic_repair_added": False,
            "candidate_selection_added": False,
            "auto_submit_added": False,
            "wrapper_patch_generated": False,
            "wrapper_memory_selection_added": False,
        },
    }
    write_outputs(out_dir=out_dir, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
