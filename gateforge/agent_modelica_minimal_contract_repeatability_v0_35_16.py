from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_minimal_contract_attribution_v0_35_15 import _case_row
from .agent_modelica_dyad_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIRS = [
    REPO_ROOT / "artifacts" / "connector_flow_minimal_contract_live_v0_35_15",
    REPO_ROOT / "artifacts" / "connector_flow_minimal_contract_repeat_v0_35_16_run_02",
]
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "minimal_contract_repeatability_v0_35_16"


def _run_row(run_dir: Path) -> dict[str, Any] | None:
    rows = load_jsonl(run_dir / "results.jsonl")
    if not rows:
        return None
    cases = [_case_row(row) for row in rows]
    return {
        "run_id": run_dir.name,
        "case_count": len(cases),
        "pass_count": sum(1 for case in cases if case["final_verdict"] == "PASS"),
        "minimal_pass_count": sum(1 for case in cases if case["pass_with_minimal_implemented_contract"]),
        "passed_case_ids": [case["case_id"] for case in cases if case["final_verdict"] == "PASS"],
        "failed_case_ids": [case["case_id"] for case in cases if case["final_verdict"] != "PASS"],
        "cases": cases,
    }


def build_minimal_contract_repeatability(
    *,
    run_dirs: list[Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    dirs = run_dirs or DEFAULT_RUN_DIRS
    runs: list[dict[str, Any]] = []
    missing_runs: list[str] = []
    for run_dir in dirs:
        row = _run_row(run_dir)
        if row is None:
            missing_runs.append(run_dir.name)
        else:
            runs.append(row)
    passed_sets = [set(str(case_id) for case_id in run["passed_case_ids"]) for run in runs]
    failed_sets = [set(str(case_id) for case_id in run["failed_case_ids"]) for run in runs]
    stable_pass_case_ids = sorted(set.intersection(*passed_sets)) if passed_sets else []
    stable_fail_case_ids = sorted(set.intersection(*failed_sets)) if failed_sets else []
    pass_counts = [int(run["pass_count"]) for run in runs]
    if missing_runs:
        decision = "minimal_contract_repeatability_incomplete"
    elif stable_pass_case_ids and stable_fail_case_ids:
        decision = "minimal_contract_stable_partial_gain"
    elif stable_pass_case_ids:
        decision = "minimal_contract_stable_gain"
    else:
        decision = "minimal_contract_not_repeatable"
    summary = {
        "version": "v0.35.16",
        "status": "PASS" if runs and not missing_runs else "REVIEW",
        "analysis_scope": "minimal_contract_repeatability",
        "run_count": len(runs),
        "missing_runs": missing_runs,
        "pass_counts": pass_counts,
        "stable_pass_case_ids": stable_pass_case_ids,
        "stable_fail_case_ids": stable_fail_case_ids,
        "runs": runs,
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
