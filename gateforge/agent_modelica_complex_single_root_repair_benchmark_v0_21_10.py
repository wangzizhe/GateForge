from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ADMISSION_PATH = (
    REPO_ROOT / "artifacts" / "complex_single_root_admission_v0_21_9" / "admitted_complex_targets.jsonl"
)
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "complex_single_root_repair_benchmark_v0_21_10"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def build_repair_case(row: dict[str, Any]) -> dict[str, Any] | None:
    if row.get("target_admission_status") != "admitted_complex_target_failure":
        return None
    candidate_id = str(row.get("candidate_id") or "")
    source_model_path = str(row.get("source_model_path") or "")
    mutated_model_path = str(row.get("target_model_path") or "")
    if not candidate_id or not source_model_path or not mutated_model_path:
        return None
    return {
        "candidate_id": candidate_id,
        "task_id": candidate_id,
        "benchmark_family": "complex_single_root_refactor_residual",
        "mutation_family": str(row.get("mutation_pattern") or ""),
        "benchmark_version": "v0.21.10",
        "source_model_path": source_model_path,
        "mutated_model_path": mutated_model_path,
        "failure_type": str(row.get("target_bucket_id") or "model_check_error"),
        "expected_stage": "check",
        "expected_turns": 2,
        "difficulty_prior": "hard",
        "workflow_goal": (
            "Repair the partially migrated Modelica model so it checks and simulates again, "
            "while preserving the original physical modeling intent. Use only the compiler "
            "feedback and the model text; do not assume hidden benchmark metadata."
        ),
        "planner_backend": str(os.getenv("LLM_PROVIDER") or "").strip(),
        "backend": "openmodelica_docker",
        "admission_source": "omc_complex_single_root_verified",
    }


def build_repair_benchmark(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def summarize_benchmark(cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "version": "v0.21.10",
        "status": "PASS" if cases else "REVIEW",
        "case_count": len(cases),
        "benchmark_path": str(DEFAULT_OUT_DIR / "admitted_cases.jsonl"),
        "repair_eval_discipline": "agent_llm_omc_only_no_deterministic_repair",
        "next_action": "run_live_executor_multiturn_screening",
    }


def write_outputs(out_dir: Path, cases: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "admitted_cases.jsonl").open("w", encoding="utf-8") as fh:
        for case in cases:
            fh.write(json.dumps(case, sort_keys=True) + "\n")
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_complex_single_root_repair_benchmark_builder(
    *,
    admission_path: Path = DEFAULT_ADMISSION_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    rows = load_jsonl(admission_path)
    cases = build_repair_benchmark(rows)
    summary = summarize_benchmark(cases)
    write_outputs(out_dir, cases, summary)
    return summary
