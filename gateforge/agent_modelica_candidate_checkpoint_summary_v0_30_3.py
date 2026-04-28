from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_candidate_critique_summary_v0_30_0 import _critique_tool_count
from .agent_modelica_submit_discipline_summary_v0_29_23 import _row_summary, _rows

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASELINE_DIR = REPO_ROOT / "artifacts" / "candidate_critique_salience_v0_30_1" / "run_01"
DEFAULT_PROBE_DIR = REPO_ROOT / "artifacts" / "candidate_checkpoint_probe_v0_30_3" / "run_01"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "candidate_checkpoint_probe_v0_30_3" / "summary"


def _checkpoint_count(row: dict[str, Any]) -> int:
    return sum(len(step.get("checkpoint_messages", [])) for step in row.get("steps", []) if isinstance(step, dict))


def _checkpoint_guard_count(row: dict[str, Any]) -> int:
    return sum(len(step.get("checkpoint_guard_violations", [])) for step in row.get("steps", []) if isinstance(step, dict))


def build_candidate_checkpoint_summary(
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
        baseline_row = baseline.get(case_id, {})
        probe_row = probe.get(case_id, {})
        baseline_summary = _row_summary(baseline_row)
        probe_summary = _row_summary(probe_row)
        cases.append(
            {
                "case_id": case_id,
                "baseline": baseline_summary,
                "probe": probe_summary,
                "baseline_critique_tool_count": _critique_tool_count(baseline_row),
                "probe_critique_tool_count": _critique_tool_count(probe_row),
                "probe_checkpoint_count": _checkpoint_count(probe_row),
                "probe_checkpoint_guard_count": _checkpoint_guard_count(probe_row),
                "missed_success_fixed": bool(baseline_summary["missed_successful_candidate"])
                and bool(probe_summary["submit_after_success"]),
                "pass_delta": int(probe_summary["verdict"] == "PASS") - int(baseline_summary["verdict"] == "PASS"),
            }
        )

    baseline_pass = sum(1 for row in cases if row["baseline"]["verdict"] == "PASS")
    probe_pass = sum(1 for row in cases if row["probe"]["verdict"] == "PASS")
    baseline_missed = sum(1 for row in cases if row["baseline"]["missed_successful_candidate"])
    probe_missed = sum(1 for row in cases if row["probe"]["missed_successful_candidate"])
    checkpoint_count = sum(int(row["probe_checkpoint_count"]) for row in cases)
    checkpoint_guard_count = sum(int(row["probe_checkpoint_guard_count"]) for row in cases)
    critique_count = sum(int(row["probe_critique_tool_count"]) for row in cases)
    fixed_count = sum(1 for row in cases if row["missed_success_fixed"])
    if checkpoint_count == 0:
        decision = "checkpoint_not_triggered"
    elif probe_pass > baseline_pass or probe_missed < baseline_missed or fixed_count:
        decision = "transparent_checkpoint_positive_signal"
    else:
        decision = "transparent_checkpoint_no_observed_gain"

    summary = {
        "version": "v0.30.3",
        "status": "PASS" if cases else "REVIEW",
        "analysis_scope": "candidate_checkpoint_probe",
        "case_count": len(cases),
        "baseline_pass_count": baseline_pass,
        "probe_pass_count": probe_pass,
        "baseline_missed_success_count": baseline_missed,
        "probe_missed_success_count": probe_missed,
        "probe_checkpoint_count": checkpoint_count,
        "probe_checkpoint_guard_count": checkpoint_guard_count,
        "probe_critique_tool_count": critique_count,
        "missed_success_fixed_count": fixed_count,
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
