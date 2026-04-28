from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_candidate_critique_summary_v0_30_0 import _critique_tool_count
from .agent_modelica_submit_discipline_summary_v0_29_23 import _row_summary, _rows

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASELINE_DIR = REPO_ROOT / "artifacts" / "candidate_critique_probe_v0_30_0" / "run_01"
DEFAULT_PROBE_DIR = REPO_ROOT / "artifacts" / "candidate_critique_salience_v0_30_1" / "run_01"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "candidate_critique_salience_v0_30_1" / "summary"


def build_candidate_critique_salience_summary(
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
        base_row = baseline.get(case_id, {})
        probe_raw = probe.get(case_id, {})
        base = _row_summary(base_row)
        probe_summary = _row_summary(probe_raw)
        cases.append(
            {
                "case_id": case_id,
                "baseline": base,
                "probe": probe_summary,
                "baseline_critique_tool_count": _critique_tool_count(base_row),
                "probe_critique_tool_count": _critique_tool_count(probe_raw),
                "critique_invocation_delta": _critique_tool_count(probe_raw) - _critique_tool_count(base_row),
                "pass_delta": int(probe_summary["verdict"] == "PASS") - int(base["verdict"] == "PASS"),
            }
        )
    baseline_pass = sum(1 for row in cases if row["baseline"]["verdict"] == "PASS")
    probe_pass = sum(1 for row in cases if row["probe"]["verdict"] == "PASS")
    baseline_critique = sum(int(row["baseline_critique_tool_count"]) for row in cases)
    probe_critique = sum(int(row["probe_critique_tool_count"]) for row in cases)
    if probe_critique <= baseline_critique:
        decision = "candidate_critique_still_not_invoked"
    elif probe_pass > baseline_pass:
        decision = "candidate_critique_salience_positive_signal"
    else:
        decision = "candidate_critique_invoked_without_capability_gain"
    summary = {
        "version": "v0.30.1",
        "status": "PASS" if cases else "REVIEW",
        "analysis_scope": "candidate_critique_salience_probe",
        "case_count": len(cases),
        "baseline_pass_count": baseline_pass,
        "probe_pass_count": probe_pass,
        "baseline_critique_tool_count": baseline_critique,
        "probe_critique_tool_count": probe_critique,
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
