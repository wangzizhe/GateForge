from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY = REPO_ROOT / "artifacts" / "hard_pool_registry_v0_42_3" / "registry.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "full_registry_baseline_v0_70_0"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_task_from_registry_row(row: dict[str, Any]) -> dict[str, Any]:
    source_reference = Path(str(row.get("source_reference") or ""))
    if not source_reference.is_absolute():
        source_reference = REPO_ROOT / source_reference
    source_payload = json.loads(source_reference.read_text(encoding="utf-8"))
    verification = dict(source_payload.get("verification") or {})
    simulate = verification.get("simulate") if isinstance(verification.get("simulate"), dict) else {}
    return {
        "case_id": str(row.get("case_id") or source_payload.get("case_id") or ""),
        "task_type": str(source_payload.get("task_type") or "repair"),
        "title": str(source_payload.get("title") or row.get("mutation_intent") or ""),
        "description": str(source_payload.get("description") or row.get("visible_task_description") or ""),
        "constraints": list(source_payload.get("constraints") or []),
        "initial_model": str(source_payload.get("initial_model") or ""),
        "submission_format": "Return the final repaired Modelica model text.",
        "verification": {
            "check_model": bool(verification.get("check_model", True)),
            "simulate": {
                "stop_time": float(simulate.get("stop_time", 0.1)),
                "intervals": int(simulate.get("intervals", 100)),
            },
        },
        "verification_command": "Run model check first, then simulation when model check succeeds.",
        "dataset_split": "holdout",
        "registry_bundle": "v0.70_full_registry",
        "registry_family": str(row.get("family") or ""),
        "registry_status": str(row.get("registry_status") or ""),
        "repeatability_status": str(row.get("repeatability_status") or ""),
        "known_hard_for": list(row.get("known_hard_for") or []),
    }


def build_full_registry_task_bundle(
    *,
    registry_path: Path = DEFAULT_REGISTRY,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    registry_rows = load_jsonl(registry_path)
    tasks = [build_task_from_registry_row(row) for row in registry_rows]
    out_dir.mkdir(parents=True, exist_ok=True)
    tasks_path = out_dir / "tasks.jsonl"
    tasks_path.write_text(
        "".join(json.dumps(task, sort_keys=True) + "\n" for task in tasks),
        encoding="utf-8",
    )
    family_counts = Counter(str(row.get("family") or "") for row in registry_rows)
    status_counts = Counter(str(row.get("registry_status") or "") for row in registry_rows)
    repeatability_counts = Counter(str(row.get("repeatability_status") or "") for row in registry_rows)
    summary = {
        "version": "v0.70.0",
        "analysis_scope": "full_registry_task_bundle",
        "status": "PASS" if len(tasks) == len(registry_rows) and tasks else "REVIEW",
        "artifact_complete": bool(tasks) and len(tasks) == len(registry_rows),
        "registry_path": str(registry_path),
        "tasks_path": str(tasks_path),
        "registry_seed_count": len(registry_rows),
        "task_count": len(tasks),
        "family_counts": dict(sorted(family_counts.items())),
        "registry_status_counts": dict(sorted(status_counts.items())),
        "repeatability_status_counts": dict(sorted(repeatability_counts.items())),
        "case_ids": [str(task.get("case_id") or "") for task in tasks],
    }
    write_json(out_dir / "summary.json", summary)
    return summary


def classify_workspace_result(row: dict[str, Any]) -> str:
    if row.get("provider_error"):
        return "provider_blocked"
    if row.get("harness_timeout"):
        return "timeout"
    if row.get("final_verdict") == "PASS":
        return "easy_or_solved"
    return "hard_candidate"


def summarize_full_registry_baseline(
    *,
    registry_path: Path = DEFAULT_REGISTRY,
    results_path: Path,
    out_dir: Path,
    summary_version: str = "v0.70.1",
) -> dict[str, Any]:
    registry_rows = load_jsonl(registry_path)
    result_rows = load_jsonl(results_path)
    registry_case_ids = {str(row.get("case_id") or "") for row in registry_rows}
    result_by_case = {str(row.get("case_id") or ""): row for row in result_rows}
    rows: list[dict[str, Any]] = []
    for registry_row in registry_rows:
        case_id = str(registry_row.get("case_id") or "")
        result = result_by_case.get(case_id)
        status = classify_workspace_result(result) if result else "not_run"
        rows.append(
            {
                "case_id": case_id,
                "family": str(registry_row.get("family") or ""),
                "registry_status": str(registry_row.get("registry_status") or ""),
                "repeatability_status": str(registry_row.get("repeatability_status") or ""),
                "known_hard_for": list(registry_row.get("known_hard_for") or []),
                "baseline_status": status,
                "final_verdict": str((result or {}).get("final_verdict") or ""),
                "submitted": bool((result or {}).get("submitted")),
                "candidate_count": len((result or {}).get("candidate_files") or []),
                "token_used": int((result or {}).get("token_used") or 0),
            }
        )
    status_counts = Counter(row["baseline_status"] for row in rows)
    family_counts = Counter(row["family"] for row in rows)
    family_status_counts: dict[str, dict[str, int]] = {}
    for row in rows:
        family_status_counts.setdefault(row["family"], {})
        family_status_counts[row["family"]][row["baseline_status"]] = (
            family_status_counts[row["family"]].get(row["baseline_status"], 0) + 1
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "case_difficulty.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    summary = {
        "version": summary_version,
        "analysis_scope": "full_registry_baseline_summary",
        "status": "PASS" if result_rows else "REVIEW",
        "artifact_complete": all(row["baseline_status"] != "not_run" for row in rows) and bool(registry_rows),
        "conclusion_allowed": all(row["baseline_status"] != "not_run" for row in rows)
        and not any(row["baseline_status"] == "provider_blocked" for row in rows)
        and bool(registry_rows),
        "registry_seed_count": len(registry_rows),
        "completed_case_count": sum(1 for row in rows if row["baseline_status"] != "not_run"),
        "merged_result_count": len(result_rows),
        "extra_result_case_count": len(set(result_by_case) - registry_case_ids),
        "status_counts": dict(sorted(status_counts.items())),
        "family_counts": dict(sorted(family_counts.items())),
        "family_status_counts": {
            family: dict(sorted(counts.items())) for family, counts in sorted(family_status_counts.items())
        },
        "not_run_case_ids": [row["case_id"] for row in rows if row["baseline_status"] == "not_run"],
        "hard_candidate_case_ids": [row["case_id"] for row in rows if row["baseline_status"] == "hard_candidate"],
        "timeout_case_ids": [row["case_id"] for row in rows if row["baseline_status"] == "timeout"],
        "provider_blocked_case_ids": [row["case_id"] for row in rows if row["baseline_status"] == "provider_blocked"],
    }
    write_json(out_dir / "summary.json", summary)
    return summary


def merge_workspace_results(
    *,
    result_paths: list[Path],
    out_path: Path,
) -> dict[str, Any]:
    by_case: dict[str, dict[str, Any]] = {}
    source_by_case: dict[str, str] = {}
    duplicate_count = 0
    for path in result_paths:
        for row in load_jsonl(path):
            case_id = str(row.get("case_id") or "")
            if not case_id:
                continue
            existing = by_case.get(case_id)
            if existing is not None:
                duplicate_count += 1
            if existing is None or _prefer_result(row, existing):
                by_case[case_id] = row
                source_by_case[case_id] = str(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged_rows = [by_case[case_id] for case_id in sorted(by_case)]
    out_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in merged_rows),
        encoding="utf-8",
    )
    summary = {
        "version": "v0.70.1",
        "analysis_scope": "workspace_result_merge",
        "status": "PASS" if merged_rows else "REVIEW",
        "result_path_count": len(result_paths),
        "merged_case_count": len(merged_rows),
        "duplicate_count": duplicate_count,
        "out_path": str(out_path),
        "source_by_case": source_by_case,
    }
    write_json(out_path.parent / "merge_summary.json", summary)
    return summary


def _prefer_result(candidate: dict[str, Any], existing: dict[str, Any]) -> bool:
    candidate_provider_error = bool(candidate.get("provider_error"))
    existing_provider_error = bool(existing.get("provider_error"))
    if candidate_provider_error != existing_provider_error:
        return not candidate_provider_error
    candidate_timeout = bool(candidate.get("harness_timeout"))
    existing_timeout = bool(existing.get("harness_timeout"))
    if candidate_timeout != existing_timeout:
        return not candidate_timeout
    candidate_pass = candidate.get("final_verdict") == "PASS"
    existing_pass = existing.get("final_verdict") == "PASS"
    if candidate_pass != existing_pass:
        return candidate_pass
    return int(candidate.get("token_used") or 0) > int(existing.get("token_used") or 0)


def summarize_hard_candidate_repeatability(
    *,
    baseline_summary_path: Path,
    repeat_results_path: Path,
    out_dir: Path,
    summary_version: str = "v0.70.2",
) -> dict[str, Any]:
    baseline_summary = json.loads(baseline_summary_path.read_text(encoding="utf-8"))
    baseline_hard = set(str(case_id) for case_id in baseline_summary.get("hard_candidate_case_ids") or [])
    repeat_rows = load_jsonl(repeat_results_path)
    repeat_by_case = {str(row.get("case_id") or ""): row for row in repeat_rows}
    rows: list[dict[str, Any]] = []
    for case_id in sorted(baseline_hard):
        repeat = repeat_by_case.get(case_id)
        if repeat is None:
            status = "not_rerun"
        elif repeat.get("provider_error"):
            status = "provider_blocked"
        elif repeat.get("harness_timeout"):
            status = "timeout"
        elif repeat.get("final_verdict") == "PASS":
            status = "unstable"
        else:
            status = "repeatable_hard_candidate"
        rows.append(
            {
                "case_id": case_id,
                "repeatability_status": status,
                "repeat_final_verdict": str((repeat or {}).get("final_verdict") or ""),
                "repeat_submitted": bool((repeat or {}).get("submitted")),
                "repeat_candidate_count": len((repeat or {}).get("candidate_files") or []),
                "repeat_token_used": int((repeat or {}).get("token_used") or 0),
            }
        )
    status_counts = Counter(row["repeatability_status"] for row in rows)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "repeatability_cases.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    blocked = any(row["repeatability_status"] in {"not_rerun", "provider_blocked", "timeout"} for row in rows)
    summary = {
        "version": summary_version,
        "analysis_scope": "hard_candidate_repeatability",
        "status": "PASS" if rows else "REVIEW",
        "artifact_complete": bool(rows) and not any(row["repeatability_status"] == "not_rerun" for row in rows),
        "conclusion_allowed": bool(rows) and not blocked,
        "baseline_hard_candidate_count": len(baseline_hard),
        "repeatability_status_counts": dict(sorted(status_counts.items())),
        "repeatable_hard_candidate_case_ids": [
            row["case_id"] for row in rows if row["repeatability_status"] == "repeatable_hard_candidate"
        ],
        "unstable_case_ids": [row["case_id"] for row in rows if row["repeatability_status"] == "unstable"],
        "blocked_case_ids": [
            row["case_id"]
            for row in rows
            if row["repeatability_status"] in {"not_rerun", "provider_blocked", "timeout"}
        ],
    }
    write_json(out_dir / "summary.json", summary)
    return summary
