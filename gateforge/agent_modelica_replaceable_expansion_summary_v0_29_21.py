from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .agent_modelica_dyad_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "replaceable_expansion_v0_29_21" / "run_01"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "replaceable_expansion_v0_29_21" / "summary"


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


def _tool_counts(row: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for step in row.get("steps", []):
        for call in step.get("tool_calls", []):
            if isinstance(call, dict) and call.get("name"):
                name = str(call["name"])
                counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def _sample_role(row: dict[str, Any]) -> str:
    if row.get("final_verdict") == "PASS":
        return "solvable_anchor"
    if int(row.get("token_used") or 0) >= 45000 and not bool(row.get("submitted")):
        return "hard_negative_candidate"
    return "review_candidate"


def build_replaceable_expansion_summary(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    rows = load_jsonl(run_dir / "results.jsonl")
    cases: list[dict[str, Any]] = []
    for row in rows:
        cases.append(
            {
                "case_id": str(row.get("case_id") or ""),
                "verdict": str(row.get("final_verdict") or ""),
                "submitted": bool(row.get("submitted")),
                "token_used": int(row.get("token_used") or 0),
                "unique_candidate_count": _unique_candidate_count(row),
                "tool_counts": _tool_counts(row),
                "sample_role": _sample_role(row),
            }
        )
    pass_count = sum(1 for row in cases if row["verdict"] == "PASS")
    hard_negative_count = sum(1 for row in cases if row["sample_role"] == "hard_negative_candidate")
    summary = {
        "version": "v0.29.21",
        "status": "PASS" if cases else "REVIEW",
        "analysis_scope": "replaceable_partial_family_expansion",
        "case_count": len(cases),
        "pass_count": pass_count,
        "hard_negative_candidate_count": hard_negative_count,
        "cases": cases,
        "decision": (
            "family_expansion_yields_mixed_anchor_and_hard_negative_samples"
            if pass_count and hard_negative_count
            else "family_expansion_needs_more_screening"
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
