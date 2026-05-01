from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "benchmark_blind_gate_v0_36_4"

USER_VISIBLE_FIELDS = (
    "description",
    "constraints",
    "workflow_goal",
    "task",
    "prompt",
    "instructions",
)

LEAKAGE_PATTERNS = {
    "correct_fix": re.compile(r"\b(correct|right|expected)\s+fix\s+(is|:)", re.IGNORECASE),
    "root_cause": re.compile(r"\b(root\s+cause|cause)\s+(is|:)", re.IGNORECASE),
    "solution_is": re.compile(r"\b(solution|answer)\s+(is|:)", re.IGNORECASE),
    "fix_by": re.compile(r"\bfix\s+by\s+", re.IGNORECASE),
    "must_add_exact": re.compile(r"\b(add|insert)\s+the\s+(equation|connect|declaration)\b", re.IGNORECASE),
}


def _visible_text(task: dict[str, Any]) -> dict[str, str]:
    visible: dict[str, str] = {}
    for field in USER_VISIBLE_FIELDS:
        value = task.get(field)
        if value is None:
            continue
        if isinstance(value, list):
            text = "\n".join(str(item) for item in value)
        elif isinstance(value, dict):
            text = json.dumps(value, sort_keys=True)
        else:
            text = str(value)
        visible[field] = text
    return visible


def lint_benchmark_blindness(task: dict[str, Any]) -> dict[str, Any]:
    visible = _visible_text(task)
    hits: list[dict[str, str]] = []
    for field, text in visible.items():
        for rule, pattern in LEAKAGE_PATTERNS.items():
            match = pattern.search(text)
            if match:
                hits.append(
                    {
                        "field": field,
                        "rule": rule,
                        "snippet": text[max(0, match.start() - 40) : match.end() + 40],
                    }
                )
    return {
        "case_id": str(task.get("case_id") or task.get("id") or ""),
        "status": "PASS" if not hits else "FAIL",
        "blind_benchmark_eligible": not hits,
        "leakage_risk_count": len(hits),
        "hits": hits,
    }


def build_benchmark_blind_lint_summary(
    tasks: list[dict[str, Any]],
    *,
    version: str = "v0.36.4",
) -> dict[str, Any]:
    rows = [lint_benchmark_blindness(task) for task in tasks]
    failed = [row for row in rows if row["status"] != "PASS"]
    return {
        "version": version,
        "analysis_scope": "benchmark_blind_lint",
        "status": "PASS" if not failed else "FAIL",
        "task_count": len(rows),
        "leaking_task_count": len(failed),
        "formal_benchmark_eligible": not failed,
        "results": rows,
    }


def write_benchmark_blind_lint_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

