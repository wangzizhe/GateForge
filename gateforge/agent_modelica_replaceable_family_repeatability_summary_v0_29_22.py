from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .agent_modelica_dyad_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIRS = [
    REPO_ROOT / "artifacts" / "replaceable_expansion_v0_29_21" / "run_01",
    REPO_ROOT / "artifacts" / "replaceable_family_repeatability_v0_29_22" / "run_01",
]
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "replaceable_family_repeatability_v0_29_22" / "summary"


def _normalize_model_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


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


def _successful_tool_observed(row: dict[str, Any]) -> bool:
    for step in row.get("steps", []):
        for result in step.get("tool_results", []):
            if not isinstance(result, dict):
                continue
            name = str(result.get("name") or "")
            text = str(result.get("result") or "")
            if name in {"check_model", "simulate_model"} and 'resultFile = "/workspace/' in text:
                return True
    return False


def build_replaceable_family_repeatability_summary(
    *,
    run_dirs: list[Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    dirs = list(run_dirs or DEFAULT_RUN_DIRS)
    runs: list[dict[str, Any]] = []
    per_case: dict[str, list[dict[str, Any]]] = {}
    for index, run_dir in enumerate(dirs, start=1):
        rows = load_jsonl(run_dir / "results.jsonl")
        pass_count = sum(1 for row in rows if row.get("final_verdict") == "PASS")
        missed_success_count = sum(
            1
            for row in rows
            if row.get("final_verdict") != "PASS" and _successful_tool_observed(row) and not bool(row.get("submitted"))
        )
        runs.append(
            {
                "run_index": index,
                "run_dir": str(run_dir),
                "case_count": len(rows),
                "pass_count": pass_count,
                "missed_success_count": missed_success_count,
            }
        )
        for row in rows:
            case_id = str(row.get("case_id") or "")
            per_case.setdefault(case_id, []).append(
                {
                    "run_index": index,
                    "verdict": str(row.get("final_verdict") or ""),
                    "submitted": bool(row.get("submitted")),
                    "token_used": int(row.get("token_used") or 0),
                    "unique_candidate_count": _unique_candidate_count(row),
                    "successful_tool_observed": _successful_tool_observed(row),
                }
            )
    cases: list[dict[str, Any]] = []
    for case_id, records in sorted(per_case.items()):
        pass_count = sum(1 for record in records if record["verdict"] == "PASS")
        missed_success_count = sum(
            1
            for record in records
            if record["verdict"] != "PASS" and record["successful_tool_observed"] and not record["submitted"]
        )
        cases.append(
            {
                "case_id": case_id,
                "run_count": len(records),
                "pass_count": pass_count,
                "missed_success_count": missed_success_count,
                "stable_pass": bool(records) and pass_count == len(records),
                "stable_fail": bool(records) and pass_count == 0 and missed_success_count == 0,
                "submission_discipline_issue": missed_success_count > 0,
                "records": records,
            }
        )
    stable_anchor_count = sum(1 for case in cases if case["stable_pass"])
    stable_hard_negative_count = sum(1 for case in cases if case["stable_fail"])
    submission_issue_count = sum(1 for case in cases if case["submission_discipline_issue"])
    summary = {
        "version": "v0.29.22",
        "status": "PASS" if runs else "REVIEW",
        "analysis_scope": "replaceable_partial_family_repeatability",
        "run_count": len(runs),
        "stable_anchor_count": stable_anchor_count,
        "stable_hard_negative_count": stable_hard_negative_count,
        "submission_discipline_issue_count": submission_issue_count,
        "runs": runs,
        "cases": cases,
        "decision": (
            "family_roles_mixed_with_submission_discipline_issue"
            if submission_issue_count
            else "family_roles_repeatable"
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
