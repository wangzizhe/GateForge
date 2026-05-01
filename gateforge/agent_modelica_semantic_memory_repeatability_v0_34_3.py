from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_SPECS = [
    {
        "run_id": "run_01_from_v0_34_1",
        "path": REPO_ROOT / "artifacts" / "semantic_memory_units_live_probe_v0_34_1",
        "case_id": "sem_19_arrayed_shared_probe_bus",
    },
    {
        "run_id": "run_02",
        "path": REPO_ROOT / "artifacts" / "semantic_memory_units_repeat_v0_34_3_sem19_run_02",
        "case_id": "sem_19_arrayed_shared_probe_bus",
    },
    {
        "run_id": "run_03",
        "path": REPO_ROOT / "artifacts" / "semantic_memory_units_repeat_v0_34_3_sem19_run_03",
        "case_id": "sem_19_arrayed_shared_probe_bus",
    },
]
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "semantic_memory_repeatability_v0_34_3"


def _load_case(run_dir: Path, case_id: str) -> dict[str, Any] | None:
    for row in load_jsonl(run_dir / "results.jsonl"):
        if str(row.get("case_id") or "") == case_id:
            return row
    return None


def _tool_sequence(row: dict[str, Any]) -> list[str]:
    return [
        str(call.get("name") or "")
        for step in row.get("steps", [])
        if isinstance(step, dict)
        for call in step.get("tool_calls", [])
        if isinstance(call, dict)
    ]


def build_semantic_memory_repeatability(
    *,
    run_specs: list[dict[str, Any]] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    specs = run_specs or DEFAULT_RUN_SPECS
    rows: list[dict[str, Any]] = []
    missing_runs: list[str] = []
    for spec in specs:
        row = _load_case(Path(spec["path"]), str(spec["case_id"]))
        if row is None:
            missing_runs.append(str(spec["run_id"]))
            continue
        rows.append(
            {
                "run_id": str(spec["run_id"]),
                "case_id": str(row.get("case_id") or ""),
                "final_verdict": str(row.get("final_verdict") or ""),
                "submitted": bool(row.get("submitted")),
                "provider_error": str(row.get("provider_error") or ""),
                "token_used": int(row.get("token_used") or 0),
                "step_count": int(row.get("step_count") or 0),
                "tool_sequence": _tool_sequence(row),
            }
        )
    pass_count = sum(1 for row in rows if row["final_verdict"] == "PASS")
    provider_error_count = sum(1 for row in rows if row["provider_error"])
    if rows and pass_count == len(rows) and provider_error_count == 0:
        decision = "semantic_memory_units_repeatably_rescue_case"
    elif pass_count and provider_error_count == 0:
        decision = "semantic_memory_units_positive_but_unstable"
    elif provider_error_count:
        decision = "semantic_memory_units_repeatability_blocked_by_provider_errors"
    else:
        decision = "semantic_memory_units_no_repeatable_rescue"
    summary = {
        "version": "v0.34.3",
        "status": "PASS" if rows and not missing_runs else "REVIEW",
        "analysis_scope": "semantic_memory_repeatability",
        "run_count": len(rows),
        "pass_count": pass_count,
        "provider_error_count": provider_error_count,
        "missing_runs": missing_runs,
        "runs": rows,
        "decision": decision,
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
