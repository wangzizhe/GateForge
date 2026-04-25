from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from gateforge.agent_modelica_engineering_mutation_screening_v0_22_1 import (
    aggregate,
    load_jsonl,
    run_executor_case,
    summarize_case,
    write_outputs,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ADMISSION_PATH = REPO_ROOT / "artifacts" / "single_point_complex_pack_v0_22_6" / "single_point_candidates.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "single_point_complex_screening_v0_22_6"


def build_repair_case(row: dict[str, Any]) -> dict[str, Any] | None:
    if row.get("target_admission_status") != "admitted_single_point_complex_failure":
        return None
    candidate_id = str(row.get("candidate_id") or "")
    source_model_path = str(row.get("source_model_path") or "")
    mutated_model_path = str(row.get("target_model_path") or "")
    if not candidate_id or not source_model_path or not mutated_model_path:
        return None
    return {
        "candidate_id": candidate_id,
        "task_id": candidate_id,
        "benchmark_family": "single_point_complex_true_multiturn_candidate",
        "mutation_family": str(row.get("mutation_pattern") or ""),
        "benchmark_version": "v0.22.6",
        "source_model_path": source_model_path,
        "mutated_model_path": mutated_model_path,
        "failure_type": str(row.get("target_bucket_id") or "model_check_error"),
        "expected_stage": "check",
        "expected_turns": 3,
        "difficulty_prior": "true_multiturn_candidate",
        "workflow_goal": (
            "Repair the incomplete single-component Modelica refactor so it checks and simulates again. "
            "Use only the model text and compiler feedback. Do not assume hidden benchmark metadata."
        ),
        "planner_backend": "gemini",
        "backend": "openmodelica_docker",
        "admission_source": "omc_single_point_complex_verified",
    }


def build_repair_cases(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        case = build_repair_case(row)
        if not case:
            continue
        candidate_id = str(case["candidate_id"])
        if candidate_id in seen:
            continue
        seen.add(candidate_id)
        cases.append(case)
    return cases


def run_single_point_complex_screening(
    *,
    admission_path: Path = DEFAULT_ADMISSION_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
    max_rounds: int = 8,
    timeout_sec: int = 420,
    limit: int | None = None,
    executor: Callable[[dict[str, Any], Path], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    admitted_rows = load_jsonl(admission_path)
    cases = build_repair_cases(admitted_rows)
    if limit is not None:
        cases = cases[: max(0, int(limit))]
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        candidate_id = str(case.get("candidate_id") or f"case_{index}")
        raw_path = raw_dir / f"{candidate_id}.json"
        if executor is None:
            payload = run_executor_case(case, raw_path, max_rounds=max_rounds, timeout_sec=timeout_sec)
        else:
            payload = executor(case, raw_path)
            raw_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        summary = summarize_case(case, payload, max_rounds=max_rounds)
        summaries.append(summary)
        report = {
            "version": "v0.22.6",
            "discipline": "agent_llm_omc_only_no_deterministic_repair",
            "analysis_scope": "live_true_multiturn_screening_for_single_point_complex_refactors",
            "case_count": len(cases),
            "summaries": summaries,
            "aggregate": aggregate(summaries),
        }
        write_outputs(out_dir, cases, summaries, report)
    report = {
        "version": "v0.22.6",
        "discipline": "agent_llm_omc_only_no_deterministic_repair",
        "analysis_scope": "live_true_multiturn_screening_for_single_point_complex_refactors",
        "case_count": len(cases),
        "summaries": summaries,
        "aggregate": aggregate(summaries),
    }
    write_outputs(out_dir, cases, summaries, report)
    return report
