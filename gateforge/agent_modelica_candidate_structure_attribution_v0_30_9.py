from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .agent_modelica_candidate_discovery_attribution_v0_30_5 import REPO_ROOT, write_outputs
from .agent_modelica_dyad_ab_summary_v0_29_11 import load_jsonl

DEFAULT_RUN_DIRS = {
    "run_01": REPO_ROOT / "artifacts" / "checkpoint_budget_grace_probe_v0_30_7" / "run_01",
    "run_02": REPO_ROOT / "artifacts" / "checkpoint_budget_grace_repeatability_v0_30_8" / "run_02",
    "run_03": REPO_ROOT / "artifacts" / "checkpoint_budget_grace_repeatability_v0_30_8" / "run_03",
}
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "candidate_structure_attribution_v0_30_9"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _candidate_features(model_text: str) -> dict[str, Any]:
    text = str(model_text or "")
    normalized = _normalize(text)
    flow_equations = re.findall(r"\b[\w.]+\s*\.i\s*=", text)
    return {
        "connect_count": text.count("connect("),
        "equation_keyword_count": len(re.findall(r"\bequation\b", text)),
        "partial_count": len(re.findall(r"\bpartial\s+model\b", text)),
        "replaceable_count": len(re.findall(r"\breplaceable\s+model\b", text)),
        "extends_count": len(re.findall(r"\bextends\b", text)),
        "flow_equation_count": len(flow_equations),
        "model_text_len": len(text),
        "fingerprint": (
            text.count("connect("),
            len(re.findall(r"\bequation\b", text)),
            len(re.findall(r"\bpartial\s+model\b", text)),
            len(re.findall(r"\breplaceable\s+model\b", text)),
            len(re.findall(r"\bextends\b", text)),
            len(flow_equations),
        ),
        "normalized_hash": str(abs(hash(normalized))),
    }


def _result_success(step: dict[str, Any]) -> bool:
    for result in step.get("tool_results", []):
        if not isinstance(result, dict):
            continue
        if result.get("name") in {"check_model", "simulate_model"} and 'resultFile = "/workspace/' in str(result.get("result") or ""):
            return True
    return False


def _candidate_rows(row: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen_exact: set[str] = set()
    for step in row.get("steps", []):
        if not isinstance(step, dict):
            continue
        step_success = _result_success(step)
        for call in step.get("tool_calls", []):
            if not isinstance(call, dict):
                continue
            name = str(call.get("name") or "")
            if name not in {"check_model", "simulate_model", "submit_final"}:
                continue
            args = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
            model_text = str(args.get("model_text") or "")
            if not model_text.strip():
                continue
            normalized = _normalize(model_text)
            features = _candidate_features(model_text)
            candidates.append(
                {
                    "step": step.get("step"),
                    "tool": name,
                    "exact_duplicate": normalized in seen_exact,
                    "success_evidence": bool(step_success and name in {"check_model", "simulate_model"}),
                    **features,
                }
            )
            seen_exact.add(normalized)
    return candidates


def _row_status(row: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
    if row.get("final_verdict") == "PASS":
        return "pass"
    if any(candidate["success_evidence"] for candidate in candidates) and not row.get("submitted"):
        return "acceptance_failure"
    return "discovery_failure"


def _structure_cluster_count(candidates: list[dict[str, Any]]) -> int:
    return len({tuple(candidate["fingerprint"]) for candidate in candidates})


def _case_summary(case_id: str, run_rows: list[dict[str, Any]]) -> dict[str, Any]:
    pass_rows = [row for row in run_rows if row["status"] == "pass"]
    failed_rows = [row for row in run_rows if row["status"] != "pass"]
    pass_clusters = {tuple(candidate["fingerprint"]) for row in pass_rows for candidate in row["candidates"]}
    failed_clusters = {tuple(candidate["fingerprint"]) for row in failed_rows for candidate in row["candidates"]}
    success_clusters = {
        tuple(candidate["fingerprint"])
        for row in run_rows
        for candidate in row["candidates"]
        if candidate["success_evidence"]
    }
    if not pass_rows:
        classification = "no_successful_run"
    elif not failed_rows:
        classification = "stable_success_structure"
    elif pass_clusters - failed_clusters:
        classification = "success_requires_distinct_structure"
    elif success_clusters and success_clusters.issubset(failed_clusters | pass_clusters):
        classification = "structure_found_but_acceptance_or_timing_unstable"
    else:
        classification = "candidate_search_unstable"
    return {
        "case_id": case_id,
        "classification": classification,
        "run_count": len(run_rows),
        "pass_count": len(pass_rows),
        "failed_count": len(failed_rows),
        "success_structure_cluster_count": len(success_clusters),
        "pass_structure_cluster_count": len(pass_clusters),
        "failed_structure_cluster_count": len(failed_clusters),
        "runs": run_rows,
    }


def build_candidate_structure_attribution(
    *,
    run_dirs: dict[str, Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    active_run_dirs = run_dirs or DEFAULT_RUN_DIRS
    by_case: dict[str, list[dict[str, Any]]] = {}
    for run_id, run_dir in sorted(active_run_dirs.items()):
        for row in load_jsonl(run_dir / "results.jsonl"):
            case_id = str(row.get("case_id") or "")
            if not case_id:
                continue
            candidates = _candidate_rows(row)
            by_case.setdefault(case_id, []).append(
                {
                    "run_id": run_id,
                    "status": _row_status(row, candidates),
                    "final_verdict": str(row.get("final_verdict") or "MISSING"),
                    "submitted": bool(row.get("submitted")),
                    "candidate_count": len(candidates),
                    "exact_unique_candidate_count": len({candidate["normalized_hash"] for candidate in candidates}),
                    "structure_cluster_count": _structure_cluster_count(candidates),
                    "success_candidate_count": sum(1 for candidate in candidates if candidate["success_evidence"]),
                    "candidates": candidates,
                }
            )

    cases = [_case_summary(case_id, rows) for case_id, rows in sorted(by_case.items())]
    run_case_count = sum(len(case["runs"]) for case in cases)
    low_structure_diversity_failures = sum(
        1
        for case in cases
        for row in case["runs"]
        if row["status"] != "pass" and row["candidate_count"] >= 4 and row["structure_cluster_count"] <= 2
    )
    distinct_success_cases = sum(1 for case in cases if case["classification"] == "success_requires_distinct_structure")
    if low_structure_diversity_failures:
        decision = "candidate_discovery_limited_by_structure_homogeneity"
    elif distinct_success_cases:
        decision = "candidate_discovery_needs_distinct_structure"
    else:
        decision = "candidate_structure_signal_inconclusive"

    summary = {
        "version": "v0.30.9",
        "status": "PASS" if run_case_count else "REVIEW",
        "analysis_scope": "candidate_structure_attribution",
        "run_count": len(active_run_dirs),
        "case_count": len(cases),
        "run_case_count": run_case_count,
        "low_structure_diversity_failure_count": low_structure_diversity_failures,
        "distinct_success_case_count": distinct_success_cases,
        "cases": cases,
        "decision": decision,
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "auto_submit_added": False,
            "llm_capability_gain_claimed": False,
        },
    }
    write_outputs(out_dir=out_dir, summary=summary)
    return summary
