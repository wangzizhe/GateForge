from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PACK_TASKS = REPO_ROOT / "artifacts" / "structural_ambiguity_medium_hard_pack_v0_78_7" / "tasks.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "medium_hard_training_trace_v0_80_0"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_medium_hard_training_trace_summary(
    *,
    tasks_path: Path = DEFAULT_PACK_TASKS,
    result_paths_by_arm: dict[str, Path],
    out_dir: Path = DEFAULT_OUT_DIR,
    summary_version: str = "v0.80.0",
) -> dict[str, Any]:
    tasks = load_jsonl(tasks_path)
    task_ids = [str(task.get("case_id") or "") for task in tasks if task.get("case_id")]
    family_by_case = {str(task.get("case_id") or ""): str(task.get("registry_family") or "") for task in tasks}
    rows_by_arm = {
        arm: {str(row.get("case_id") or ""): row for row in load_jsonl(path)}
        for arm, path in sorted(result_paths_by_arm.items())
    }
    traces: list[dict[str, Any]] = []
    missing_by_arm: dict[str, list[str]] = {}
    arm_taxonomy_counts: Counter[str] = Counter()
    learning_role_counts: Counter[str] = Counter()
    provider_error_count = 0
    harness_timeout_count = 0
    for arm, rows_by_case in rows_by_arm.items():
        missing_by_arm[arm] = [case_id for case_id in task_ids if case_id not in rows_by_case]
    for case_id in task_ids:
        arm_outcomes: dict[str, dict[str, Any]] = {}
        for arm, rows_by_case in rows_by_arm.items():
            row = rows_by_case.get(case_id) or {}
            outcome = _summarize_arm_outcome(row)
            arm_outcomes[arm] = outcome
            arm_taxonomy_counts[outcome["taxonomy"]] += 1
            if outcome["provider_error"]:
                provider_error_count += 1
            if outcome["harness_timeout"]:
                harness_timeout_count += 1
        learning_roles = _learning_roles(arm_outcomes)
        for role in learning_roles:
            learning_role_counts[role] += 1
        traces.append(
            {
                "schema_version": "medium_hard_training_trace_v0_80_0",
                "case_id": case_id,
                "registry_family": family_by_case.get(case_id, ""),
                "learning_roles": learning_roles,
                "arm_outcomes": arm_outcomes,
                "supervision_status": _supervision_status(learning_roles),
                "notes": _case_notes(learning_roles),
            }
        )
    artifact_complete = bool(task_ids) and all(not missing for missing in missing_by_arm.values())
    clean = artifact_complete and provider_error_count == 0 and harness_timeout_count == 0
    out_dir.mkdir(parents=True, exist_ok=True)
    traces_path = out_dir / "training_traces.jsonl"
    traces_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in traces), encoding="utf-8")
    summary = {
        "version": summary_version,
        "analysis_scope": "medium_hard_training_trace_taxonomy",
        "status": "PASS" if clean else "REVIEW",
        "artifact_complete": artifact_complete,
        "evidence_role": "smoke",
        "training_schema_ready": clean,
        "training_data_ready": False,
        "capability_conclusion_allowed": False,
        "case_count": len(task_ids),
        "arm_labels": sorted(rows_by_arm),
        "arm_taxonomy_counts": dict(sorted(arm_taxonomy_counts.items())),
        "learning_role_counts": dict(sorted(learning_role_counts.items())),
        "submit_decision_signal_case_count": learning_role_counts.get("submit_decision_supervision_candidate", 0),
        "budget_sensitive_positive_case_count": learning_role_counts.get("budget_sensitive_positive_transition", 0),
        "persistent_unsubmitted_success_case_count": learning_role_counts.get(
            "persistent_failure_with_unsubmitted_success_candidate", 0
        ),
        "negative_only_generation_case_count": learning_role_counts.get("candidate_generation_negative_only", 0),
        "substrate_interpretation": _substrate_interpretation(learning_role_counts, len(task_ids)),
        "provider_error_count": provider_error_count,
        "harness_timeout_count": harness_timeout_count,
        "missing_by_arm": missing_by_arm,
        "training_traces_path": str(traces_path),
        "scope_note": (
            "This summary prepares trace-level supervision metadata. It does not contain reference patches and must "
            "not be connected to wrapper repair, hidden routing, or automatic candidate selection."
        ),
    }
    write_json(out_dir / "summary.json", summary)
    return summary


def _summarize_arm_outcome(row: dict[str, Any]) -> dict[str, Any]:
    candidate_files = row.get("candidate_files") if isinstance(row.get("candidate_files"), list) else []
    successful_candidate_ids = [
        str(candidate.get("candidate_id") or "")
        for candidate in candidate_files
        if bool(candidate.get("write_check_ok")) and bool(candidate.get("write_simulate_ok"))
    ]
    provider_error = str(row.get("provider_error") or "")
    harness_timeout = bool(row.get("harness_timeout"))
    final_verdict = str(row.get("final_verdict") or "MISSING")
    submitted = bool(row.get("submitted"))
    if provider_error or harness_timeout:
        taxonomy = "blocked"
    elif final_verdict == "PASS" and submitted:
        taxonomy = "solved_submitted"
    elif final_verdict == "PASS":
        taxonomy = "solved_without_submission"
    elif successful_candidate_ids:
        taxonomy = "successful_candidate_not_submitted"
    elif final_verdict == "MISSING":
        taxonomy = "missing"
    else:
        taxonomy = "candidate_generation_failure"
    return {
        "taxonomy": taxonomy,
        "final_verdict": final_verdict,
        "submitted": submitted,
        "candidate_count": len(candidate_files),
        "successful_candidate_ids": successful_candidate_ids,
        "token_used": int(row.get("token_used") or 0),
        "provider_error": provider_error,
        "harness_timeout": harness_timeout,
    }


def _learning_roles(arm_outcomes: dict[str, dict[str, Any]]) -> list[str]:
    roles: set[str] = set()
    any_pass = any(outcome["taxonomy"] in {"solved_submitted", "solved_without_submission"} for outcome in arm_outcomes.values())
    any_fail_with_successful_candidate = any(
        outcome["taxonomy"] == "successful_candidate_not_submitted" for outcome in arm_outcomes.values()
    )
    all_clean_fail = all(
        outcome["taxonomy"] in {"successful_candidate_not_submitted", "candidate_generation_failure"}
        for outcome in arm_outcomes.values()
    )
    if any_pass:
        roles.add("positive_solution_available")
    if any_fail_with_successful_candidate:
        roles.add("submit_decision_supervision_candidate")
    if all_clean_fail and any_fail_with_successful_candidate:
        roles.add("persistent_failure_with_unsubmitted_success_candidate")
    if all_clean_fail and not any_fail_with_successful_candidate:
        roles.add("candidate_generation_negative_only")
    if any_pass and any(
        outcome["taxonomy"] in {"successful_candidate_not_submitted", "candidate_generation_failure"}
        for outcome in arm_outcomes.values()
    ):
        roles.add("budget_sensitive_positive_transition")
    return sorted(roles) or ["unclassified"]


def _substrate_interpretation(learning_role_counts: Counter[str], case_count: int) -> str:
    if case_count and learning_role_counts.get("submit_decision_supervision_candidate", 0) == case_count:
        return "submit_decision_signal_present_in_all_cases"
    if learning_role_counts.get("candidate_generation_negative_only", 0):
        return "contains_pure_candidate_generation_negative_cases"
    if learning_role_counts.get("budget_sensitive_positive_transition", 0):
        return "contains_budget_sensitive_positive_transitions"
    return "review"


def _supervision_status(learning_roles: list[str]) -> str:
    roles = set(learning_roles)
    if "candidate_generation_negative_only" in roles:
        return "negative_only"
    if "submit_decision_supervision_candidate" in roles:
        return "needs_submit_decision_label"
    if "positive_solution_available" in roles:
        return "positive_solution_observed"
    return "review"


def _case_notes(learning_roles: list[str]) -> list[str]:
    notes: list[str] = []
    roles = set(learning_roles)
    if "submit_decision_supervision_candidate" in roles:
        notes.append("A clean successful candidate exists in at least one failed arm, so this is not pure candidate generation failure.")
    if "budget_sensitive_positive_transition" in roles:
        notes.append("At least one higher-budget arm solved the case while another clean arm failed.")
    if "candidate_generation_negative_only" in roles:
        notes.append("No successful candidate was observed in any clean failed arm.")
    return notes
