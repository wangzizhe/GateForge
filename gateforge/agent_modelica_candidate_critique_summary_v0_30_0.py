from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_submit_discipline_summary_v0_29_23 import _row_summary, _rows

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASELINE_DIR = REPO_ROOT / "artifacts" / "submit_discipline_probe_v0_29_23" / "run_01"
DEFAULT_PROBE_DIR = REPO_ROOT / "artifacts" / "candidate_critique_probe_v0_30_0" / "run_01"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "candidate_critique_probe_v0_30_0" / "summary"


def _critique_tool_count(row: dict[str, Any]) -> int:
    count = 0
    for step in row.get("steps", []):
        for call in step.get("tool_calls", []):
            if isinstance(call, dict) and call.get("name") == "candidate_acceptance_critique":
                count += 1
    return count


def build_candidate_critique_summary(
    *,
    baseline_dir: Path = DEFAULT_BASELINE_DIR,
    probe_dir: Path = DEFAULT_PROBE_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    baseline = _rows(baseline_dir)
    probe = _rows(probe_dir)
    case_ids = sorted(set(baseline) | set(probe))
    cases: list[dict[str, Any]] = []
    for case_id in case_ids:
        base = _row_summary(baseline.get(case_id, {}))
        probe_raw = probe.get(case_id, {})
        probe_summary = _row_summary(probe_raw)
        critique_count = _critique_tool_count(probe_raw)
        cases.append(
            {
                "case_id": case_id,
                "baseline": base,
                "probe": probe_summary,
                "critique_tool_count": critique_count,
                "critique_used": critique_count > 0,
                "missed_success_fixed": bool(base["missed_successful_candidate"]) and bool(probe_summary["submit_after_success"]),
                "pass_delta": int(probe_summary["verdict"] == "PASS") - int(base["verdict"] == "PASS"),
            }
        )
    baseline_pass = sum(1 for row in cases if row["baseline"]["verdict"] == "PASS")
    probe_pass = sum(1 for row in cases if row["probe"]["verdict"] == "PASS")
    baseline_missed = sum(1 for row in cases if row["baseline"]["missed_successful_candidate"])
    probe_missed = sum(1 for row in cases if row["probe"]["missed_successful_candidate"])
    critique_used = sum(1 for row in cases if row["critique_used"])
    if critique_used == 0:
        decision = "candidate_critique_not_invoked"
    elif probe_pass > baseline_pass or probe_missed < baseline_missed:
        decision = "candidate_critique_positive_signal"
    else:
        decision = "candidate_critique_no_observed_gain"
    summary = {
        "version": "v0.30.0",
        "status": "PASS" if cases else "REVIEW",
        "analysis_scope": "candidate_critique_probe",
        "case_count": len(cases),
        "baseline_pass_count": baseline_pass,
        "probe_pass_count": probe_pass,
        "baseline_missed_success_count": baseline_missed,
        "probe_missed_success_count": probe_missed,
        "critique_used_count": critique_used,
        "cases": cases,
        "decision": decision,
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "auto_submit_added": False,
            "llm_capability_gain_claimed": False,
        },
    }
    write_outputs(out_dir=out_dir, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
