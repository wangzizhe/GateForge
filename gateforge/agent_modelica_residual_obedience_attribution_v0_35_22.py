from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .agent_modelica_dyad_ab_summary_v0_29_11 import load_jsonl
from .agent_modelica_sem22_failure_attribution_v0_35_17 import TARGET_CASE_ID

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "connector_flow_residual_consistency_live_v0_35_21_sem22"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "residual_obedience_attribution_v0_35_22"


def _zero_flow_equation_count(model_text: str) -> int:
    total = 0
    loop_pattern = re.compile(
        r"for\s+[A-Za-z_][A-Za-z0-9_]*\s+in\s+(\d+)\s*:\s*(\d+)\s+loop(?P<body>.*?)end\s+for\s*;",
        re.DOTALL,
    )
    loop_spans: list[tuple[int, int]] = []
    for loop in loop_pattern.finditer(str(model_text or "")):
        start = int(loop.group(1))
        stop = int(loop.group(2))
        multiplier = max(0, stop - start + 1)
        total += multiplier * _zero_flow_equation_count(loop.group("body"))
        loop_spans.append(loop.span())
    remaining: list[str] = []
    cursor = 0
    for start, stop in loop_spans:
        remaining.append(str(model_text or "")[cursor:start])
        cursor = stop
    remaining.append(str(model_text or "")[cursor:])
    count = 0
    for row in "".join(remaining).split(";"):
        normalized = " ".join(row.strip().split())
        if re.search(r"\b[A-Za-z_][A-Za-z0-9_\[\]]*\.i\s*=\s*0(?:\.0)?$", normalized):
            count += 1
    return total + count


def _steps_after_consistency(row: dict[str, Any]) -> list[dict[str, Any]]:
    consistency_step = 0
    for step in row.get("steps", []):
        if not isinstance(step, dict):
            continue
        for call in step.get("tool_calls", []):
            if isinstance(call, dict) and call.get("name") == "residual_hypothesis_consistency_check":
                consistency_step = _step_number(step)
    return [step for step in row.get("steps", []) if isinstance(step, dict) and _step_number(step) > consistency_step]


def _step_number(step: dict[str, Any]) -> int:
    try:
        return int(step.get("step") or 0)
    except (TypeError, ValueError):
        return 0


def _post_consistency_candidate_counts(row: dict[str, Any]) -> list[int]:
    counts: list[int] = []
    for step in _steps_after_consistency(row):
        for call in step.get("tool_calls", []):
            if not isinstance(call, dict) or call.get("name") not in {"check_model", "simulate_model", "submit_final"}:
                continue
            arguments = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
            counts.append(_zero_flow_equation_count(str(arguments.get("model_text") or "")))
    return counts


def _text_mentions_mismatch(row: dict[str, Any]) -> bool:
    text = "\n".join(str(step.get("text") or "") for step in row.get("steps", []) if isinstance(step, dict)).lower()
    return "delta of 6 exceeds" in text or "exceeds the 4" in text or "consistency check says" in text


def _case_row(row: dict[str, Any]) -> dict[str, Any]:
    post_counts = _post_consistency_candidate_counts(row)
    return {
        "case_id": str(row.get("case_id") or ""),
        "final_verdict": str(row.get("final_verdict") or ""),
        "submitted": bool(row.get("submitted")),
        "mismatch_acknowledged_in_text": _text_mentions_mismatch(row),
        "post_consistency_candidate_zero_flow_counts": post_counts,
        "post_consistency_over_residual_candidate_count": sum(1 for count in post_counts if count > 4),
    }


def build_residual_obedience_attribution(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
    target_case_id: str = TARGET_CASE_ID,
) -> dict[str, Any]:
    rows = [row for row in load_jsonl(run_dir / "results.jsonl") if row.get("case_id") == target_case_id]
    cases = [_case_row(row) for row in rows]
    acknowledged_count = sum(1 for case in cases if case["mismatch_acknowledged_in_text"])
    violation_count = sum(1 for case in cases if case["post_consistency_over_residual_candidate_count"] > 0)
    if not rows:
        decision = "residual_obedience_run_missing"
    elif acknowledged_count and violation_count:
        decision = "residual_critique_acknowledged_but_not_obeyed"
    elif violation_count:
        decision = "residual_critique_not_obeyed"
    elif acknowledged_count:
        decision = "residual_critique_obeyed_without_success"
    else:
        decision = "residual_obedience_unclear"
    summary = {
        "version": "v0.35.22",
        "status": "PASS" if rows else "REVIEW",
        "analysis_scope": "residual_obedience_attribution",
        "target_case_id": target_case_id,
        "case_count": len(cases),
        "mismatch_acknowledged_count": acknowledged_count,
        "post_consistency_violation_count": violation_count,
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
