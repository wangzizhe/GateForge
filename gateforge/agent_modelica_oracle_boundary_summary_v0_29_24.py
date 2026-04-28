from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_submit_discipline_summary_v0_29_23 import _row_summary, _rows

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASELINE_DIR = REPO_ROOT / "artifacts" / "submit_discipline_probe_v0_29_23" / "run_01"
DEFAULT_PROBE_DIR = REPO_ROOT / "artifacts" / "oracle_boundary_probe_v0_29_24" / "run_01"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "oracle_boundary_probe_v0_29_24" / "summary"


def _constraint_citation_seen(row: dict[str, Any]) -> bool:
    terms = ("constraint", "requirement", "oracle", "task", "violates", "violate")
    for step in row.get("steps", []):
        text = str(step.get("text") or "").lower()
        if any(term in text for term in terms):
            return True
    return False


def build_oracle_boundary_summary(
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
                "constraint_citation_seen": _constraint_citation_seen(probe_raw),
                "missed_success_fixed": bool(base["missed_successful_candidate"]) and bool(probe_summary["submit_after_success"]),
                "pass_delta": int(probe_summary["verdict"] == "PASS") - int(base["verdict"] == "PASS"),
            }
        )
    baseline_pass = sum(1 for row in cases if row["baseline"]["verdict"] == "PASS")
    probe_pass = sum(1 for row in cases if row["probe"]["verdict"] == "PASS")
    baseline_missed = sum(1 for row in cases if row["baseline"]["missed_successful_candidate"])
    probe_missed = sum(1 for row in cases if row["probe"]["missed_successful_candidate"])
    fixed_count = sum(1 for row in cases if row["missed_success_fixed"])
    summary = {
        "version": "v0.29.24",
        "status": "PASS" if cases else "REVIEW",
        "analysis_scope": "oracle_boundary_probe",
        "case_count": len(cases),
        "baseline_pass_count": baseline_pass,
        "probe_pass_count": probe_pass,
        "baseline_missed_success_count": baseline_missed,
        "probe_missed_success_count": probe_missed,
        "missed_success_fixed_count": fixed_count,
        "cases": cases,
        "decision": (
            "oracle_boundary_positive_signal"
            if probe_pass > baseline_pass or probe_missed < baseline_missed
            else "oracle_boundary_no_observed_gain"
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
