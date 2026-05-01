from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASELINE_DIR = REPO_ROOT / "artifacts" / "replaceable_family_repeatability_v0_29_22" / "run_01"
DEFAULT_PROBE_DIR = REPO_ROOT / "artifacts" / "submit_discipline_probe_v0_29_23" / "run_01"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "submit_discipline_probe_v0_29_23" / "summary"


def _normalize_model_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _successful_tool_steps(row: dict[str, Any]) -> list[int]:
    steps: list[int] = []
    for step in row.get("steps", []):
        step_id = step.get("step")
        if not isinstance(step_id, int):
            continue
        for result in step.get("tool_results", []):
            if not isinstance(result, dict):
                continue
            name = str(result.get("name") or "")
            text = str(result.get("result") or "")
            if name in {"check_model", "simulate_model"} and 'resultFile = "/workspace/' in text:
                steps.append(step_id)
                break
    return steps


def _unique_candidate_count(row: dict[str, Any]) -> int:
    texts: set[str] = set()
    for step in row.get("steps", []):
        for call in step.get("tool_calls", []):
            if not isinstance(call, dict):
                continue
            name = str(call.get("name") or "")
            args = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
            model_text = _normalize_model_text(str(args.get("model_text") or ""))
            if name in {"check_model", "simulate_model", "submit_final"} and model_text:
                texts.add(model_text)
    return len(texts)


def _row_summary(row: dict[str, Any]) -> dict[str, Any]:
    successful_steps = _successful_tool_steps(row)
    return {
        "verdict": str(row.get("final_verdict") or "MISSING"),
        "submitted": bool(row.get("submitted")),
        "token_used": int(row.get("token_used") or 0),
        "unique_candidate_count": _unique_candidate_count(row),
        "successful_candidate_observed": bool(successful_steps),
        "first_successful_tool_step": min(successful_steps) if successful_steps else None,
        "submit_after_success": bool(row.get("submitted")) and bool(successful_steps),
        "missed_successful_candidate": bool(successful_steps) and not bool(row.get("submitted")),
    }


def _rows(path: Path) -> dict[str, dict[str, Any]]:
    return {str(row.get("case_id") or ""): row for row in load_jsonl(path / "results.jsonl") if row.get("case_id")}


def build_submit_discipline_summary(
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
        probe_row = _row_summary(probe.get(case_id, {}))
        cases.append(
            {
                "case_id": case_id,
                "baseline": base,
                "probe": probe_row,
                "missed_success_fixed": bool(base["missed_successful_candidate"]) and bool(probe_row["submit_after_success"]),
                "pass_delta": int(probe_row["verdict"] == "PASS") - int(base["verdict"] == "PASS"),
            }
        )
    baseline_pass = sum(1 for row in cases if row["baseline"]["verdict"] == "PASS")
    probe_pass = sum(1 for row in cases if row["probe"]["verdict"] == "PASS")
    baseline_missed = sum(1 for row in cases if row["baseline"]["missed_successful_candidate"])
    probe_missed = sum(1 for row in cases if row["probe"]["missed_successful_candidate"])
    fixed_count = sum(1 for row in cases if row["missed_success_fixed"])
    summary = {
        "version": "v0.29.23",
        "status": "PASS" if cases else "REVIEW",
        "analysis_scope": "submit_discipline_probe",
        "case_count": len(cases),
        "baseline_pass_count": baseline_pass,
        "probe_pass_count": probe_pass,
        "baseline_missed_success_count": baseline_missed,
        "probe_missed_success_count": probe_missed,
        "missed_success_fixed_count": fixed_count,
        "cases": cases,
        "decision": (
            "submit_discipline_positive_signal"
            if probe_pass > baseline_pass or probe_missed < baseline_missed
            else "submit_discipline_no_observed_gain"
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
