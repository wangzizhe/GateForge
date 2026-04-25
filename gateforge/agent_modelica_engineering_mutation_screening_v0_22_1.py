from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ADMISSION_PATH = (
    REPO_ROOT / "artifacts" / "engineering_mutation_probe_v0_22_0" / "engineering_candidates.jsonl"
)
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "engineering_mutation_screening_v0_22_1"
EXECUTOR_MODULE = "gateforge.agent_modelica_live_executor_v1"


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
    if row.get("target_admission_status") != "admitted_engineering_mutation_failure":
        return None
    candidate_id = str(row.get("candidate_id") or "")
    source_model_path = str(row.get("source_model_path") or "")
    mutated_model_path = str(row.get("target_model_path") or "")
    if not candidate_id or not source_model_path or not mutated_model_path:
        return None
    return {
        "candidate_id": candidate_id,
        "task_id": candidate_id,
        "benchmark_family": "engineering_refactor_residual",
        "mutation_family": str(row.get("mutation_pattern") or ""),
        "benchmark_version": "v0.22.1",
        "source_model_path": source_model_path,
        "mutated_model_path": mutated_model_path,
        "failure_type": str(row.get("target_bucket_id") or "model_check_error"),
        "expected_stage": "check",
        "expected_turns": 2,
        "difficulty_prior": "unknown_until_screened",
        "workflow_goal": (
            "Repair the incomplete engineering refactor in this Modelica model so it checks "
            "and simulates again, while preserving the original physical modeling intent. "
            "Use only the model text and compiler feedback; do not assume hidden benchmark metadata."
        ),
        "planner_backend": "gemini",
        "backend": "openmodelica_docker",
        "admission_source": "omc_engineering_mutation_verified",
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


def run_executor_case(case: dict[str, Any], out_path: Path, *, max_rounds: int, timeout_sec: int) -> dict[str, Any]:
    cmd = [
        sys.executable,
        "-m",
        EXECUTOR_MODULE,
        "--task-id",
        str(case.get("task_id") or case.get("candidate_id") or ""),
        "--failure-type",
        str(case.get("failure_type") or ""),
        "--expected-stage",
        str(case.get("expected_stage") or "check"),
        "--workflow-goal",
        str(case.get("workflow_goal") or ""),
        "--source-model-path",
        str(case.get("source_model_path") or ""),
        "--mutated-model-path",
        str(case.get("mutated_model_path") or ""),
        "--max-rounds",
        str(max_rounds),
        "--timeout-sec",
        "240",
        "--simulate-stop-time",
        "0.1",
        "--simulate-intervals",
        "20",
        "--backend",
        "openmodelica_docker",
        "--planner-backend",
        "gemini",
        "--remedy-pack-enabled",
        "off",
        "--capability-intervention-pack-enabled",
        "off",
        "--broader-change-pack-enabled",
        "off",
        "--experience-replay",
        "off",
        "--planner-experience-injection",
        "off",
        "--out",
        str(out_path),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_sec,
            cwd=str(REPO_ROOT),
        )
    except subprocess.TimeoutExpired:
        return {"error": "subprocess_timeout", "returncode": None}
    if proc.returncode != 0 or not out_path.exists():
        return {
            "error": "executor_failed",
            "returncode": proc.returncode,
            "stderr": proc.stderr[-1200:],
            "stdout": proc.stdout[-1200:],
        }
    return json.loads(out_path.read_text(encoding="utf-8"))


def classify_screening_result(payload: dict[str, Any], *, max_rounds: int) -> dict[str, Any]:
    if payload.get("error"):
        return {
            "executor_status": "INFRA_FAIL",
            "sample_quality": "infra_fail",
            "n_turns": 0,
            "termination": str(payload.get("error") or "executor_error"),
            "observed_error_sequence": [],
            "saw_layer_transition": False,
        }
    attempts = list(payload.get("attempts") or [])
    observed = [str(row.get("observed_failure_type") or "") for row in attempts]
    repair_round_count = sum(
        1
        for row in attempts
        if isinstance(row.get("declaration_fix_repair"), dict)
        and bool((row.get("declaration_fix_repair") or {}).get("applied"))
    )
    validation_round_count = max(0, len(attempts) - repair_round_count)
    executor_status = str(payload.get("executor_status") or "").upper()
    passed = executor_status == "PASS"
    if passed and len(attempts) <= 1:
        sample_quality = "single_turn_easy"
        termination = "success"
    elif passed and repair_round_count >= 2:
        sample_quality = "multi_turn_useful"
        termination = "success"
    elif passed:
        sample_quality = "single_repair_then_validate"
        termination = "success"
    elif len(attempts) >= max_rounds:
        sample_quality = "dead_end_hard"
        termination = "max_rounds"
    else:
        sample_quality = "invalid_or_brittle"
        termination = "early_stop"
    layer_transition = (
        "model_check_error" in observed
        and any(item in observed for item in ("constraint_violation", "simulate_error", "none"))
    )
    return {
        "executor_status": "PASS" if passed else "FAILED",
        "sample_quality": sample_quality,
        "n_turns": len(attempts),
        "repair_round_count": repair_round_count,
        "validation_round_count": validation_round_count,
        "termination": termination,
        "observed_error_sequence": observed,
        "saw_layer_transition": layer_transition,
        "remedy_pack_enabled": bool(payload.get("remedy_pack_enabled")),
        "capability_intervention_pack_enabled": bool(payload.get("capability_intervention_pack_enabled")),
        "broader_change_pack_enabled": bool(payload.get("broader_change_pack_enabled")),
        "experience_replay_used": bool((payload.get("experience_replay") or {}).get("used")),
        "planner_experience_injection_used": bool((payload.get("planner_experience_injection") or {}).get("used")),
    }


def summarize_case(case: dict[str, Any], payload: dict[str, Any], *, max_rounds: int) -> dict[str, Any]:
    result = classify_screening_result(payload, max_rounds=max_rounds)
    return {
        "candidate_id": str(case.get("candidate_id") or ""),
        "mutation_family": str(case.get("mutation_family") or ""),
        "failure_type": str(case.get("failure_type") or ""),
        **result,
    }


def aggregate(case_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [row for row in case_summaries if row.get("executor_status") != "INFRA_FAIL"]
    quality_counts = Counter(str(row.get("sample_quality") or "") for row in case_summaries)
    family_quality_counts: dict[str, dict[str, int]] = {}
    for row in case_summaries:
        family = str(row.get("mutation_family") or "")
        quality = str(row.get("sample_quality") or "")
        if family not in family_quality_counts:
            family_quality_counts[family] = {}
        family_quality_counts[family][quality] = family_quality_counts[family].get(quality, 0) + 1
    pass_rows = [row for row in valid if row.get("executor_status") == "PASS"]
    multi_turn_rows = [row for row in valid if row.get("sample_quality") == "multi_turn_useful"]
    strict = all(
        not row.get("remedy_pack_enabled")
        and not row.get("capability_intervention_pack_enabled")
        and not row.get("broader_change_pack_enabled")
        and not row.get("experience_replay_used")
        and not row.get("planner_experience_injection_used")
        for row in valid
    )
    return {
        "total_cases": len(valid),
        "infra_fail_count": len(case_summaries) - len(valid),
        "pass_count": len(pass_rows),
        "pass_rate": len(pass_rows) / len(valid) if valid else 0.0,
        "multi_turn_useful_count": len(multi_turn_rows),
        "multi_turn_useful_rate": len(multi_turn_rows) / len(valid) if valid else 0.0,
        "sample_quality_counts": dict(sorted(quality_counts.items())),
        "family_quality_counts": {
            family: dict(sorted(counts.items())) for family, counts in sorted(family_quality_counts.items())
        },
        "strict_no_auxiliary_packs": strict,
    }


def write_outputs(out_dir: Path, cases: list[dict[str, Any]], summaries: list[dict[str, Any]], report: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "admitted_cases.jsonl").open("w", encoding="utf-8") as fh:
        for case in cases:
            fh.write(json.dumps(case, sort_keys=True) + "\n")
    with (out_dir / "case_summaries.jsonl").open("w", encoding="utf-8") as fh:
        for row in summaries:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "summary.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_engineering_mutation_screening(
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
            "version": "v0.22.1",
            "discipline": "agent_llm_omc_only_no_deterministic_repair",
            "analysis_scope": "live_multiturn_sample_quality_screening",
            "case_count": len(cases),
            "summaries": summaries,
            "aggregate": aggregate(summaries),
        }
        write_outputs(out_dir, cases, summaries, report)
    report = {
        "version": "v0.22.1",
        "discipline": "agent_llm_omc_only_no_deterministic_repair",
        "analysis_scope": "live_multiturn_sample_quality_screening",
        "case_count": len(cases),
        "summaries": summaries,
        "aggregate": aggregate(summaries),
    }
    write_outputs(out_dir, cases, summaries, report)
    return report
