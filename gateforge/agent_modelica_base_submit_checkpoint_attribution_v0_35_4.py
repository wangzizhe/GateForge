from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_connector_flow_family_live_attribution_v0_35_1 import _classify_run
from .agent_modelica_dyad_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "connector_flow_family_base_checkpoint_live_v0_35_4"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "base_submit_checkpoint_attribution_v0_35_4"


def _checkpoint_message_count(row: dict[str, Any]) -> int:
    return sum(
        len(step.get("checkpoint_messages", []))
        for step in row.get("steps", [])
        if isinstance(step, dict)
    )


def _checkpoint_guard_violations(row: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    for step in row.get("steps", []):
        if isinstance(step, dict):
            violations.extend(str(name) for name in step.get("checkpoint_guard_violations", []))
    return violations


def build_base_submit_checkpoint_attribution(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    rows = load_jsonl(run_dir / "results.jsonl")
    cases: list[dict[str, Any]] = []
    for row in rows:
        case = _classify_run(row)
        case["checkpoint_message_count"] = _checkpoint_message_count(row)
        case["checkpoint_guard_violations"] = _checkpoint_guard_violations(row)
        cases.append(case)
    pass_count = sum(1 for case in cases if case["final_verdict"] == "PASS")
    checkpoint_message_count = sum(int(case["checkpoint_message_count"]) for case in cases)
    guard_violation_count = sum(len(case["checkpoint_guard_violations"]) for case in cases)
    if not rows:
        decision = "missing_base_submit_checkpoint_live_run"
    elif pass_count:
        decision = "base_submit_checkpoint_converts_success_candidate_to_pass"
    elif checkpoint_message_count:
        decision = "base_submit_checkpoint_triggered_without_pass"
    else:
        decision = "base_submit_checkpoint_not_reached_candidate_discovery_gap"
    summary = {
        "version": "v0.35.4",
        "status": "PASS" if rows else "REVIEW",
        "analysis_scope": "base_submit_checkpoint_attribution",
        "run_id": run_dir.name,
        "case_count": len(cases),
        "pass_count": pass_count,
        "submitted_count": sum(1 for case in cases if case["submitted"]),
        "success_candidate_seen_count": sum(1 for case in cases if case["success_evidence_steps"]),
        "checkpoint_message_count": checkpoint_message_count,
        "checkpoint_guard_violation_count": guard_violation_count,
        "cases": cases,
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
