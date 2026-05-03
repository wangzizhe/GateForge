from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_jsonl


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CANDIDATES = REPO_ROOT / "artifacts" / "medium_candidate_mining_v0_54_0" / "medium_candidates.jsonl"
DEFAULT_TASK_DIRS = (
    REPO_ROOT / "assets_private" / "benchmarks" / "agent_comparison_v1" / "tasks" / "repair",
)
DEFAULT_TASK_JSONL = (
    REPO_ROOT / "artifacts" / "hard_core_adjacent_variants_v0_48_1" / "tasks.jsonl",
)
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "medium_candidate_admission_v0_55_0"

FORBIDDEN_VISIBLE_PHRASES = (
    "correct fix is",
    "root cause is",
    "the answer is",
    "add this equation",
    "remove this equation",
    "reference repair",
)

FORBIDDEN_TASK_FIELDS = (
    "hidden_oracle",
    "reference_repair",
    "reference_diff",
    "known_hard_for",
    "gateforge_internal_artifacts",
)


def load_task_records(*, task_dirs: tuple[Path, ...], task_jsonl_paths: tuple[Path, ...]) -> dict[str, dict[str, Any]]:
    tasks: dict[str, dict[str, Any]] = {}
    for task_dir in task_dirs:
        if not task_dir.exists():
            continue
        for path in sorted(task_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and str(payload.get("case_id") or ""):
                task = dict(payload)
                task["_source_path"] = str(path)
                tasks[str(task["case_id"])] = task
    for path in task_jsonl_paths:
        for row in load_jsonl(path):
            case_id = str(row.get("case_id") or "")
            if case_id and case_id not in tasks:
                task = dict(row)
                task["_source_path"] = str(path)
                tasks[case_id] = task
    return tasks


def audit_visible_blindness(task: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    text_parts = [
        str(task.get("title") or ""),
        str(task.get("description") or ""),
        str(task.get("visible_task_description") or ""),
        " ".join(str(item) for item in task.get("constraints") or []),
    ]
    visible_text = "\n".join(text_parts).lower()
    for phrase in FORBIDDEN_VISIBLE_PHRASES:
        if phrase in visible_text:
            issues.append(f"forbidden_visible_phrase:{phrase}")
    for field in FORBIDDEN_TASK_FIELDS:
        if field in task:
            issues.append(f"forbidden_task_field:{field}")
    return issues


def audit_medium_candidate(candidate: dict[str, Any], task: dict[str, Any] | None) -> dict[str, Any]:
    case_id = str(candidate.get("case_id") or "")
    issues: list[str] = []
    if not task:
        issues.append("missing_task_record")
        return {
            "case_id": case_id,
            "admission_status": "REVIEW",
            "issues": issues,
            "task_source_path": "",
            "pass_rate": candidate.get("pass_rate"),
            "evidence_count": candidate.get("evidence_count"),
        }
    if not bool(task.get("source_backed")):
        issues.append("not_source_backed")
    if str(task.get("task_type") or "") != "repair":
        issues.append("not_repair_task")
    if not str(task.get("initial_model") or "").strip():
        issues.append("missing_initial_model")
    verification = task.get("verification") if isinstance(task.get("verification"), dict) else {}
    if not bool(verification.get("check_model")):
        issues.append("missing_check_model_verification")
    if "simulate" not in verification:
        issues.append("missing_simulation_verification")
    issues.extend(audit_visible_blindness(task))
    evidence_count = int(candidate.get("evidence_count") or 0)
    pass_rate = float(candidate.get("pass_rate") or 0.0)
    if evidence_count < 2:
        issues.append("insufficient_medium_evidence")
    if pass_rate < 0.2 or pass_rate > 0.7:
        issues.append("outside_medium_pass_rate_band")
    return {
        "case_id": case_id,
        "admission_status": "PASS" if not issues else "REVIEW",
        "issues": sorted(issues),
        "task_source_path": str(task.get("_source_path") or ""),
        "pass_rate": pass_rate,
        "evidence_count": evidence_count,
        "source_backed": bool(task.get("source_backed")),
        "model_check_first": bool(verification.get("check_model")),
        "has_simulation_verification": "simulate" in verification,
    }


def build_medium_candidate_admission(
    *,
    candidates: list[dict[str, Any]],
    tasks_by_case: dict[str, dict[str, Any]],
    version: str = "v0.55.0",
) -> dict[str, Any]:
    results = [audit_medium_candidate(candidate, tasks_by_case.get(str(candidate.get("case_id") or ""))) for candidate in candidates]
    admitted = sorted(row["case_id"] for row in results if row["admission_status"] == "PASS")
    review = sorted(row["case_id"] for row in results if row["admission_status"] != "PASS")
    return {
        "version": version,
        "analysis_scope": "medium_candidate_admission",
        "status": "PASS" if admitted and not review else "REVIEW",
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "artifact_complete": True,
        "readiness_status": "medium_layer_candidates_admitted" if admitted and not review else "medium_layer_candidates_need_review",
        "candidate_count": len(candidates),
        "admitted_count": len(admitted),
        "review_count": len(review),
        "admitted_case_ids": admitted,
        "review_case_ids": review,
        "results": sorted(results, key=lambda row: row["case_id"]),
        "next_actions": [
            "rerun_admitted_medium_candidates_under_current_provider",
            "move_stable_medium_candidates_into_dev_or_holdout_split",
            "repair_or_exclude_review_candidates",
        ],
    }


def write_medium_candidate_admission_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "admitted_medium_case_ids.txt").write_text(
        "\n".join(summary["admitted_case_ids"]) + ("\n" if summary["admitted_case_ids"] else ""),
        encoding="utf-8",
    )


def run_medium_candidate_admission(
    *,
    candidates_path: Path = DEFAULT_CANDIDATES,
    task_dirs: tuple[Path, ...] = DEFAULT_TASK_DIRS,
    task_jsonl_paths: tuple[Path, ...] = DEFAULT_TASK_JSONL,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_medium_candidate_admission(
        candidates=load_jsonl(candidates_path),
        tasks_by_case=load_task_records(task_dirs=task_dirs, task_jsonl_paths=task_jsonl_paths),
    )
    write_medium_candidate_admission_outputs(out_dir=out_dir, summary=summary)
    return summary
