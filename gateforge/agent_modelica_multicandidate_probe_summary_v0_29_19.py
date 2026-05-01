from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "multicandidate_probe_v0_29_19" / "run_01"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "multicandidate_probe_v0_29_19" / "summary"


def _normalize_model_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _candidate_texts(row: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for step in row.get("steps", []):
        for call in step.get("tool_calls", []):
            if not isinstance(call, dict):
                continue
            name = str(call.get("name") or "")
            args = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
            model_text = str(args.get("model_text") or "")
            if name in {"check_model", "simulate_model", "submit_final"} and model_text.strip():
                texts.append(model_text)
    return texts


def _tool_counts(row: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for step in row.get("steps", []):
        for call in step.get("tool_calls", []):
            if isinstance(call, dict) and call.get("name"):
                name = str(call["name"])
                counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def _unique_candidate_count(row: dict[str, Any]) -> int:
    return len({_normalize_model_text(text) for text in _candidate_texts(row) if _normalize_model_text(text)})


def _base_flow_policy_phrase_seen(row: dict[str, Any]) -> bool:
    for step in row.get("steps", []):
        text = str(step.get("text") or "").lower()
        if "partial base" in text and "flow" in text:
            return True
        if "base" in text and "flow equation" in text:
            return True
    return False


def build_multicandidate_probe_summary(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    rows = load_jsonl(run_dir / "results.jsonl")
    cases: list[dict[str, Any]] = []
    for row in rows:
        candidate_count = _unique_candidate_count(row)
        counts = _tool_counts(row)
        cases.append(
            {
                "case_id": str(row.get("case_id") or ""),
                "verdict": str(row.get("final_verdict") or ""),
                "submitted": bool(row.get("submitted")),
                "token_used": int(row.get("token_used") or 0),
                "unique_candidate_count": candidate_count,
                "multi_candidate_observed": candidate_count >= 2,
                "policy_tool_called": counts.get("replaceable_partial_policy_check", 0) > 0,
                "base_flow_policy_phrase_seen": _base_flow_policy_phrase_seen(row),
                "tool_counts": counts,
            }
        )
    pass_count = sum(1 for row in cases if row["verdict"] == "PASS")
    multicandidate_count = sum(1 for row in cases if row["multi_candidate_observed"])
    summary = {
        "version": "v0.29.19",
        "status": "PASS" if cases else "REVIEW",
        "analysis_scope": "transparent_multicandidate_probe",
        "case_count": len(cases),
        "pass_count": pass_count,
        "multicandidate_case_count": multicandidate_count,
        "cases": cases,
        "decision": (
            "multicandidate_positive_signal_needs_repeatability"
            if multicandidate_count and pass_count > 0
            else (
                "multicandidate_behavior_observed_without_success"
                if multicandidate_count
                else "multicandidate_probe_needs_more_evidence"
            )
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
