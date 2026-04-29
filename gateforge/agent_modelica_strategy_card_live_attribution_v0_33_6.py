from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .agent_modelica_dyad_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "semantic_strategy_cards_live_probe_v0_33_5"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "strategy_card_live_attribution_v0_33_6"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _has_success_evidence(step: dict[str, Any]) -> bool:
    for result in step.get("tool_results", []):
        if not isinstance(result, dict):
            continue
        if result.get("name") not in {"check_model", "simulate_model"}:
            continue
        if 'resultFile = "/workspace/' in str(result.get("result") or ""):
            return True
    return False


def _candidate_tags(model_text: str) -> list[str]:
    text = str(model_text or "")
    tags: list[str] = []
    if "Modelica.Electrical.Analog" in text:
        tags.append("standard_library_migration_attempted")
    if re.search(r"\.[A-Za-z_][A-Za-z0-9_]*\.i\s*=", text) or re.search(r"\.[ipn]\s*=", text):
        tags.append("direct_flow_equation_attempted")
    if re.search(r"\bconnect\s*\([^)]*\[[^)]*\)", text):
        tags.append("arrayed_connection_attempted")
    if re.search(r"\bflow\s+Real\s+i\b", text):
        tags.append("custom_flow_connector_retained")
    return sorted(set(tags))


def _case_row(row: dict[str, Any]) -> dict[str, Any]:
    candidate_count = 0
    all_tags: set[str] = set()
    success_steps: list[Any] = []
    for step in row.get("steps", []):
        if not isinstance(step, dict):
            continue
        if _has_success_evidence(step):
            success_steps.append(step.get("step"))
        for call in step.get("tool_calls", []):
            if not isinstance(call, dict):
                continue
            args = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
            model_text = str(args.get("model_text") or "")
            if not model_text.strip():
                continue
            candidate_count += 1
            all_tags.update(_candidate_tags(model_text))
    success_seen = bool(success_steps)
    submitted = bool(row.get("submitted"))
    if submitted and row.get("final_verdict") == "PASS":
        classification = "submitted_success"
    elif success_seen and not submitted:
        classification = "success_candidate_seen_without_submit"
    elif "standard_library_migration_attempted" in all_tags:
        classification = "semantic_direction_attempted_without_success"
    else:
        classification = "candidate_discovery_failure"
    return {
        "case_id": str(row.get("case_id") or ""),
        "final_verdict": str(row.get("final_verdict") or ""),
        "submitted": submitted,
        "token_used": int(row.get("token_used") or 0),
        "step_count": int(row.get("step_count") or 0),
        "candidate_count": candidate_count,
        "success_candidate_seen": success_seen,
        "success_steps": success_steps,
        "strategy_tags": sorted(all_tags),
        "classification": classification,
    }


def build_strategy_card_live_attribution(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary_path = run_dir / "summary.json"
    run_summary = load_json(summary_path) if summary_path.exists() else {}
    cases = [_case_row(row) for row in load_jsonl(run_dir / "results.jsonl")]
    success_without_submit = sum(1 for row in cases if row["classification"] == "success_candidate_seen_without_submit")
    discovery_failures = sum(1 for row in cases if row["classification"] == "candidate_discovery_failure")
    semantic_attempt_failures = sum(1 for row in cases if row["classification"] == "semantic_direction_attempted_without_success")
    if success_without_submit:
        decision = "strategy_card_probe_mixes_discovery_and_submit_budget_failures"
    elif discovery_failures or semantic_attempt_failures:
        decision = "strategy_card_context_does_not_rescue_current_hard_family"
    else:
        decision = "strategy_card_live_attribution_inconclusive"
    summary = {
        "version": "v0.33.6",
        "status": "PASS" if cases else "REVIEW",
        "analysis_scope": "strategy_card_live_attribution",
        "source_run_version": str(run_summary.get("version") or ""),
        "case_count": len(cases),
        "success_without_submit_count": success_without_submit,
        "candidate_discovery_failure_count": discovery_failures,
        "semantic_attempt_failure_count": semantic_attempt_failures,
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
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
