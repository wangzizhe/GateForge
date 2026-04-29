from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .agent_modelica_dyad_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIRS = {
    "sem13_base_run_01": REPO_ROOT / "artifacts" / "hard_family_live_baseline_v0_32_1",
    "sem13_base_run_02": REPO_ROOT / "artifacts" / "hard_family_live_baseline_v0_32_1_repeat_sem13_run_02",
    "sem13_base_run_03": REPO_ROOT / "artifacts" / "hard_family_live_baseline_v0_32_1_repeat_sem13_run_03",
    "arrayed_base_run_01": REPO_ROOT / "artifacts" / "arrayed_connector_live_baseline_v0_32_4",
    "arrayed_base_run_02": REPO_ROOT / "artifacts" / "arrayed_connector_live_baseline_v0_32_4_repeat_failures_run_02",
    "connector_contract_run_01": REPO_ROOT / "artifacts" / "connector_contract_probe_v0_32_6",
}
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "repair_strategy_attribution_v0_33_0"

TARGET_CASE_IDS = {
    "sem_13_arrayed_connector_bus_refactor",
    "sem_19_arrayed_shared_probe_bus",
    "sem_20_arrayed_adapter_cross_node",
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _candidate_texts(row: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for step in row.get("steps", []):
        if not isinstance(step, dict):
            continue
        success_evidence = any(
            isinstance(result, dict)
            and result.get("name") in {"check_model", "simulate_model"}
            and 'resultFile = "/workspace/' in str(result.get("result") or "")
            for result in step.get("tool_results", [])
        )
        for call in step.get("tool_calls", []):
            if not isinstance(call, dict):
                continue
            if call.get("name") not in {"check_model", "simulate_model", "submit_final"}:
                continue
            args = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
            model_text = str(args.get("model_text") or "")
            if not model_text.strip():
                continue
            norm = _normalize(model_text)
            candidates.append(
                {
                    "step": step.get("step"),
                    "tool": str(call.get("name") or ""),
                    "model_text": model_text,
                    "exact_duplicate": norm in seen,
                    "success_evidence": bool(success_evidence),
                }
            )
            seen.add(norm)
    return candidates


def classify_repair_strategy(model_text: str) -> dict[str, Any]:
    text = str(model_text or "")
    flow_assignments = re.findall(r"\b[A-Za-z_][A-Za-z0-9_.\[\]]*\.i\s*=", text)
    potential_reads = re.findall(r"\b[A-Za-z_][A-Za-z0-9_.\[\]]*\.v\b", text)
    arrayed_connects = re.findall(r"\bconnect\s*\([^)]*\[[^)]*\)", text)
    custom_connector = bool(re.search(r"\bconnector\s+[A-Za-z_][A-Za-z0-9_]*\b", text))
    replaceable = bool(re.search(r"\breplaceable\s+model\b", text))
    partial = bool(re.search(r"\bpartial\s+model\b", text))
    sensor_components = len(re.findall(r"Modelica\.Electrical\.Analog\.Sensors\.", text))
    strategy_tags: list[str] = []
    if potential_reads and not flow_assignments:
        strategy_tags.append("potential_only_probe_contract")
    if flow_assignments:
        strategy_tags.append("explicit_flow_assignment")
    if len(flow_assignments) >= 2:
        strategy_tags.append("multi_flow_assignment")
    if arrayed_connects:
        strategy_tags.append("arrayed_connection_set")
    if custom_connector:
        strategy_tags.append("custom_connector_contract")
    if replaceable or partial:
        strategy_tags.append("reusable_partial_replaceable_contract")
    if sensor_components:
        strategy_tags.append("msl_sensor_substitution")
    if "p.i = 0" in text or "n.i = 0" in text:
        strategy_tags.append("zero_current_sensor_assumption")
    if "connect(" not in text:
        strategy_tags.append("equation_only_collapse")
    return {
        "strategy_tags": sorted(set(strategy_tags)),
        "flow_assignment_count": len(flow_assignments),
        "potential_read_count": len(potential_reads),
        "arrayed_connect_count": len(arrayed_connects),
        "sensor_component_count": sensor_components,
        "fingerprint": (
            int(bool(potential_reads)),
            len(flow_assignments),
            len(arrayed_connects),
            int(custom_connector),
            int(replaceable),
            int(partial),
            sensor_components,
        ),
    }


def _run_row(*, run_id: str, row: dict[str, Any]) -> dict[str, Any]:
    candidates = []
    for candidate in _candidate_texts(row):
        strategy = classify_repair_strategy(str(candidate["model_text"]))
        candidates.append({key: value for key, value in candidate.items() if key != "model_text"} | strategy)
    strategy_tags = sorted({tag for candidate in candidates for tag in candidate["strategy_tags"]})
    return {
        "run_id": run_id,
        "case_id": str(row.get("case_id") or ""),
        "tool_profile": str(row.get("tool_profile") or ""),
        "final_verdict": str(row.get("final_verdict") or ""),
        "submitted": bool(row.get("submitted")),
        "candidate_count": len(candidates),
        "success_candidate_count": sum(1 for candidate in candidates if candidate["success_evidence"]),
        "strategy_cluster_count": len({tuple(candidate["fingerprint"]) for candidate in candidates}),
        "strategy_tags": strategy_tags,
        "candidates": candidates,
    }


def _case_summary(case_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    all_tags = sorted({tag for row in rows for tag in row["strategy_tags"]})
    pass_count = sum(1 for row in rows if row["final_verdict"] == "PASS")
    success_candidates = sum(int(row["success_candidate_count"]) for row in rows)
    dominant_tags: dict[str, int] = {}
    for row in rows:
        for tag in row["strategy_tags"]:
            dominant_tags[tag] = dominant_tags.get(tag, 0) + 1
    if pass_count:
        classification = "mixed_or_solved_case"
    elif success_candidates:
        classification = "acceptance_or_submission_failure"
    elif all("arrayed_connection_set" in row["strategy_tags"] for row in rows):
        classification = "persistent_arrayed_connector_strategy_failure"
    else:
        classification = "persistent_discovery_failure"
    return {
        "case_id": case_id,
        "classification": classification,
        "run_count": len(rows),
        "pass_count": pass_count,
        "success_candidate_count": success_candidates,
        "all_strategy_tags": all_tags,
        "tag_run_counts": dict(sorted(dominant_tags.items())),
        "runs": rows,
    }


def build_repair_strategy_attribution(
    *,
    run_dirs: dict[str, Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
    target_case_ids: set[str] | None = None,
) -> dict[str, Any]:
    active_run_dirs = run_dirs or DEFAULT_RUN_DIRS
    active_targets = target_case_ids or TARGET_CASE_IDS
    by_case: dict[str, list[dict[str, Any]]] = {}
    for run_id, run_dir in sorted(active_run_dirs.items()):
        for row in load_jsonl(run_dir / "results.jsonl"):
            case_id = str(row.get("case_id") or "")
            if case_id not in active_targets:
                continue
            by_case.setdefault(case_id, []).append(_run_row(run_id=run_id, row=row))
    cases = [_case_summary(case_id, rows) for case_id, rows in sorted(by_case.items())]
    persistent_failures = sum(
        1
        for case in cases
        if case["classification"] == "persistent_arrayed_connector_strategy_failure"
    )
    run_case_count = sum(int(case["run_count"]) for case in cases)
    decision = (
        "repair_strategy_discovery_needs_external_strategy_source"
        if persistent_failures >= 2
        else "repair_strategy_attribution_inconclusive"
    )
    summary = {
        "version": "v0.33.0",
        "status": "PASS" if run_case_count else "REVIEW",
        "analysis_scope": "repair_strategy_attribution",
        "case_count": len(cases),
        "run_case_count": run_case_count,
        "persistent_arrayed_connector_failure_count": persistent_failures,
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


def write_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
