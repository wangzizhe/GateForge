from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIRS = [
    REPO_ROOT / "artifacts" / "multicandidate_probe_v0_29_19" / "run_01",
    REPO_ROOT / "artifacts" / "multicandidate_repeatability_v0_29_20" / "run_01",
    REPO_ROOT / "artifacts" / "multicandidate_repeatability_v0_29_20" / "run_02",
]
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "multicandidate_repeatability_v0_29_20" / "summary"


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


def _run_label(path: Path) -> str:
    return path.name if path.name.startswith("run_") else str(path)


def build_multicandidate_repeatability_summary(
    *,
    run_dirs: list[Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    dirs = list(run_dirs or DEFAULT_RUN_DIRS)
    runs: list[dict[str, Any]] = []
    per_case: dict[str, list[dict[str, Any]]] = {}
    for index, run_dir in enumerate(dirs, start=1):
        rows = load_jsonl(run_dir / "results.jsonl")
        run_pass_count = sum(1 for row in rows if row.get("final_verdict") == "PASS")
        run_record = {
            "run_index": index,
            "run_label": _run_label(run_dir),
            "run_dir": str(run_dir),
            "case_count": len(rows),
            "pass_count": run_pass_count,
        }
        runs.append(run_record)
        for row in rows:
            case_id = str(row.get("case_id") or "")
            case_record = {
                "run_index": index,
                "verdict": str(row.get("final_verdict") or ""),
                "submitted": bool(row.get("submitted")),
                "token_used": int(row.get("token_used") or 0),
                "unique_candidate_count": _unique_candidate_count(row),
            }
            per_case.setdefault(case_id, []).append(case_record)
    cases: list[dict[str, Any]] = []
    for case_id, records in sorted(per_case.items()):
        pass_count = sum(1 for row in records if row["verdict"] == "PASS")
        cases.append(
            {
                "case_id": case_id,
                "run_count": len(records),
                "pass_count": pass_count,
                "stable_pass": pass_count == len(records) and bool(records),
                "records": records,
            }
        )
    positive_run_count = sum(1 for run in runs if int(run["pass_count"]) > 0)
    summary = {
        "version": "v0.29.20",
        "status": "PASS" if runs else "REVIEW",
        "analysis_scope": "transparent_multicandidate_repeatability",
        "run_count": len(runs),
        "positive_run_count": positive_run_count,
        "runs": runs,
        "cases": cases,
        "decision": (
            "multicandidate_positive_signal_not_repeatable"
            if positive_run_count < len(runs)
            else "multicandidate_positive_signal_repeatable"
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
