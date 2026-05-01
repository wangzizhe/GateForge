from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "replaceable_policy_probe_v0_29_18" / "run_01"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "replaceable_policy_probe_v0_29_18" / "summary"


def _tool_counts(row: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for step in row.get("steps", []):
        for call in step.get("tool_calls", []):
            if isinstance(call, dict) and call.get("name"):
                name = str(call["name"])
                counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def _policy_warning_overridden(row: dict[str, Any]) -> bool:
    saw_policy = False
    for step in row.get("steps", []):
        calls = [str(call.get("name") or "") for call in step.get("tool_calls", []) if isinstance(call, dict)]
        text = str(step.get("text") or "").lower()
        if "replaceable_partial_policy_check" in calls:
            saw_policy = True
            continue
        if saw_policy and (
            "risk but" in text
            or "warns about" in text
            or "check the model anyway" in text
            or "correct approach" in text
        ):
            return True
    return False


def build_policy_probe_summary(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    rows = load_jsonl(run_dir / "results.jsonl")
    cases: list[dict[str, Any]] = []
    for row in rows:
        counts = _tool_counts(row)
        cases.append(
            {
                "case_id": str(row.get("case_id") or ""),
                "verdict": str(row.get("final_verdict") or ""),
                "submitted": bool(row.get("submitted")),
                "token_used": int(row.get("token_used") or 0),
                "policy_tool_called": counts.get("replaceable_partial_policy_check", 0) > 0,
                "policy_warning_overridden": _policy_warning_overridden(row),
                "tool_counts": counts,
            }
        )
    pass_count = sum(1 for row in cases if row["verdict"] == "PASS")
    policy_called_count = sum(1 for row in cases if row["policy_tool_called"])
    overridden_count = sum(1 for row in cases if row["policy_warning_overridden"])
    summary = {
        "version": "v0.29.18",
        "status": "PASS" if cases else "REVIEW",
        "analysis_scope": "replaceable_policy_probe",
        "case_count": len(cases),
        "pass_count": pass_count,
        "policy_called_count": policy_called_count,
        "policy_warning_overridden_count": overridden_count,
        "cases": cases,
        "decision": (
            "policy_signal_seen_but_no_repair_gain"
            if policy_called_count and pass_count == 0
            else "policy_probe_needs_more_evidence"
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
