from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PACK_TASKS = REPO_ROOT / "artifacts" / "structural_ambiguity_medium_hard_pack_v0_78_7" / "tasks.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "medium_hard_pack_sanity_v0_79_0"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_medium_hard_pack_sanity_summary(
    *,
    tasks_path: Path = DEFAULT_PACK_TASKS,
    result_paths_by_arm: dict[str, Path],
    out_dir: Path = DEFAULT_OUT_DIR,
    summary_version: str = "v0.79.0",
) -> dict[str, Any]:
    tasks = load_jsonl(tasks_path)
    task_ids = [str(task.get("case_id") or "") for task in tasks if task.get("case_id")]
    task_family = {str(task.get("case_id") or ""): str(task.get("registry_family") or "") for task in tasks}
    rows_by_arm: dict[str, dict[str, dict[str, Any]]] = {
        arm: {str(row.get("case_id") or ""): row for row in load_jsonl(path)}
        for arm, path in sorted(result_paths_by_arm.items())
    }
    per_case_rows: list[dict[str, Any]] = []
    missing_by_arm: dict[str, list[str]] = {}
    provider_error_count = 0
    timeout_count = 0
    for arm, rows_by_case in rows_by_arm.items():
        missing_by_arm[arm] = [case_id for case_id in task_ids if case_id not in rows_by_case]
        for row in rows_by_case.values():
            if row.get("provider_error"):
                provider_error_count += 1
            if bool(row.get("harness_timeout")):
                timeout_count += 1
    arm_labels = sorted(rows_by_arm)
    for case_id in task_ids:
        outcomes: dict[str, dict[str, Any]] = {}
        for arm in arm_labels:
            row = rows_by_arm[arm].get(case_id) or {}
            outcomes[arm] = {
                "final_verdict": str(row.get("final_verdict") or "MISSING"),
                "pass": str(row.get("final_verdict") or "") == "PASS",
                "submitted": bool(row.get("submitted")),
                "candidate_count": len(row.get("candidate_files") or []),
                "token_used": int(row.get("token_used") or 0),
                "provider_error": str(row.get("provider_error") or ""),
                "harness_timeout": bool(row.get("harness_timeout")),
            }
        per_case_rows.append(
            {
                "case_id": case_id,
                "registry_family": task_family.get(case_id, ""),
                "outcomes": outcomes,
                "paired_status": _paired_status(outcomes),
            }
        )
    status_counts = Counter(row["paired_status"] for row in per_case_rows)
    pass_counts_by_arm = {
        arm: sum(1 for row in per_case_rows if row["outcomes"][arm]["pass"])
        for arm in arm_labels
    }
    all_complete = all(not missing for missing in missing_by_arm.values())
    artifact_complete = bool(task_ids) and bool(arm_labels) and all_complete
    clean = artifact_complete and provider_error_count == 0 and timeout_count == 0
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "paired_cases.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in per_case_rows),
        encoding="utf-8",
    )
    summary = {
        "version": summary_version,
        "analysis_scope": "medium_hard_pack_paired_sanity",
        "status": "PASS" if clean else "REVIEW",
        "artifact_complete": artifact_complete,
        "evidence_role": "smoke",
        "reporting_conclusion_allowed": clean,
        "capability_conclusion_allowed": False,
        "case_count": len(task_ids),
        "arm_labels": arm_labels,
        "pass_counts_by_arm": pass_counts_by_arm,
        "paired_status_counts": dict(sorted(status_counts.items())),
        "provider_error_count": provider_error_count,
        "harness_timeout_count": timeout_count,
        "missing_by_arm": missing_by_arm,
        "paired_cases_path": str(out_dir / "paired_cases.jsonl"),
        "scope_note": (
            "This is a small sanity report for paired outcome and artifact quality. It must not be used as a final "
            "capability comparison because the pack has only five cases and is family-skewed."
        ),
    }
    write_json(out_dir / "summary.json", summary)
    return summary


def _paired_status(outcomes: dict[str, dict[str, Any]]) -> str:
    if any(outcome["provider_error"] or outcome["harness_timeout"] for outcome in outcomes.values()):
        return "blocked"
    if any(outcome["final_verdict"] == "MISSING" for outcome in outcomes.values()):
        return "missing"
    passed = [arm for arm, outcome in outcomes.items() if outcome["pass"]]
    if len(passed) == len(outcomes):
        return "all_pass"
    if not passed:
        return "all_fail"
    return "split_" + "_".join(sorted(passed)) + "_only"
