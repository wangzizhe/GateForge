from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_ROOT = REPO_ROOT / "artifacts" / "methodology_semantic_rerun_v0_29_14"
DEFAULT_OUT_DIR = DEFAULT_RUN_ROOT / "summary"


def _tool_counts(row: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for step in row.get("steps", []):
        for call in step.get("tool_calls", []):
            if isinstance(call, dict) and call.get("name"):
                name = str(call["name"])
                counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def load_run_results(run_dir: Path) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("case_id") or ""): row
        for row in load_jsonl(run_dir / "results.jsonl")
        if row.get("case_id")
    }


def build_semantic_rerun_summary(
    *,
    run_dirs: list[Path],
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    runs = {run_dir.name: load_run_results(run_dir) for run_dir in run_dirs}
    case_ids = sorted({case_id for rows in runs.values() for case_id in rows})
    cases: list[dict[str, Any]] = []
    unstable_count = 0
    for case_id in case_ids:
        verdicts = {
            run_name: str(rows.get(case_id, {}).get("final_verdict") or "MISSING")
            for run_name, rows in runs.items()
        }
        pass_count = sum(1 for verdict in verdicts.values() if verdict == "PASS")
        unstable = len(set(verdicts.values())) > 1
        if unstable:
            unstable_count += 1
        cases.append(
            {
                "case_id": case_id,
                "verdicts": verdicts,
                "pass_count": pass_count,
                "run_count": len(runs),
                "unstable": unstable,
                "tool_counts": {
                    run_name: _tool_counts(rows.get(case_id, {}))
                    for run_name, rows in runs.items()
                },
                "token_used": {
                    run_name: int(rows.get(case_id, {}).get("token_used") or 0)
                    for run_name, rows in runs.items()
                },
                "submitted": {
                    run_name: bool(rows.get(case_id, {}).get("submitted"))
                    for run_name, rows in runs.items()
                },
            }
        )

    run_pass_counts = {
        run_name: sum(1 for row in rows.values() if row.get("final_verdict") == "PASS")
        for run_name, rows in runs.items()
    }
    summary = {
        "version": "v0.29.14",
        "status": "PASS" if runs and case_ids else "REVIEW",
        "analysis_scope": "semantic_narrow_rerun_stability",
        "run_count": len(runs),
        "case_count": len(case_ids),
        "run_pass_counts": run_pass_counts,
        "unstable_case_count": unstable_count,
        "cases": cases,
        "decision": (
            "semantic_narrow_not_stable_enough_for_promotion"
            if unstable_count
            else "semantic_narrow_stable_on_rerun_slice"
        ),
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "llm_capability_gain_claimed": False,
        },
    }
    write_outputs(out_dir=out_dir, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
