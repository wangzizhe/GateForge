from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIRS = [
    REPO_ROOT / "artifacts" / "engineering_mutation_screening_v0_22_1",
    REPO_ROOT / "artifacts" / "complex_single_root_repair_trajectory_v0_21_10_strict",
    REPO_ROOT / "artifacts" / "complex_single_root_repair_trajectory_v0_21_11_repeat_1",
    REPO_ROOT / "artifacts" / "raw_only_underdetermined_trajectory_v0_19_42",
    REPO_ROOT / "artifacts" / "raw_only_triple_trajectory_v0_19_45",
    REPO_ROOT / "artifacts" / "raw_only_triple_triple_underdetermined_experiment_v0_19_45_pp_pv_pv",
]
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "true_multiturn_audit_v0_22_2"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def raw_payload_paths(run_dir: Path) -> list[Path]:
    raw_dir = run_dir / "raw"
    if raw_dir.exists():
        return sorted(raw_dir.glob("*.json"))
    return sorted(run_dir.glob("*.json"))


def payload_status(payload: dict[str, Any]) -> str:
    for key in ("executor_status", "final_status", "status"):
        value = str(payload.get(key) or "").upper()
        if value:
            if value in {"PASS", "PASSED", "SUCCESS"}:
                return "PASS"
            if value in {"FAIL", "FAILED", "ERROR"}:
                return "FAILED"
    attempts = list(payload.get("attempts") or [])
    if attempts and bool(attempts[-1].get("check_pass_after_patch")):
        return "PASS"
    return "FAILED"


def observed_error_sequence(payload: dict[str, Any]) -> list[str]:
    sequence: list[str] = []
    for attempt in payload.get("attempts") or []:
        observed = str(
            attempt.get("observed_failure_type")
            or attempt.get("observed_state_before_patch")
            or attempt.get("failure_type")
            or ""
        )
        if observed:
            sequence.append(observed)
    if not sequence:
        sequence = [str(item) for item in (payload.get("observed_sequence") or []) if str(item).strip()]
    return sequence


def attempt_has_llm_repair(attempt: dict[str, Any]) -> bool:
    repair = attempt.get("declaration_fix_repair")
    if isinstance(repair, dict):
        return bool(repair.get("applied"))
    if "patched_text_present" in attempt or "model_changed" in attempt:
        return bool(attempt.get("patched_text_present")) and bool(attempt.get("model_changed"))
    return False


def repair_round_count(payload: dict[str, Any]) -> int:
    return sum(1 for attempt in (payload.get("attempts") or []) if attempt_has_llm_repair(attempt))


def provider_error_count(payload: dict[str, Any]) -> int:
    count = 0
    for attempt in payload.get("attempts") or []:
        repair = attempt.get("declaration_fix_repair")
        if isinstance(repair, dict) and str(repair.get("err") or "").strip():
            count += 1
        if str(attempt.get("llm_error") or "").strip():
            count += 1
    return count


def validation_round_count(payload: dict[str, Any]) -> int:
    attempts = list(payload.get("attempts") or [])
    return max(0, len(attempts) - repair_round_count(payload))


def classify_quality(payload: dict[str, Any]) -> str:
    status = payload_status(payload)
    attempts = list(payload.get("attempts") or [])
    repairs = repair_round_count(payload)
    if status == "PASS":
        if repairs >= 2:
            return "true_multi_repair_pass"
        if repairs == 1:
            return "single_repair_then_validate"
        return "already_or_direct_pass"
    if provider_error_count(payload):
        return "infra_or_provider_noise"
    if repairs >= 2:
        return "multi_repair_fail"
    if repairs == 1:
        return "single_repair_fail"
    if attempts:
        return "no_repair_fail"
    return "unreadable_or_empty"


def is_false_multiturn_candidate(payload: dict[str, Any]) -> bool:
    return payload_status(payload) == "PASS" and len(payload.get("attempts") or []) >= 2 and repair_round_count(payload) < 2


def audit_payload(run_dir: Path, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    attempts = list(payload.get("attempts") or [])
    candidate_id = str(payload.get("task_id") or payload.get("candidate_id") or path.stem)
    sequence = observed_error_sequence(payload)
    return {
        "run_dir": str(run_dir),
        "artifact_path": str(path),
        "candidate_id": candidate_id,
        "status": payload_status(payload),
        "n_turns": len(attempts),
        "repair_round_count": repair_round_count(payload),
        "validation_round_count": validation_round_count(payload),
        "provider_error_count": provider_error_count(payload),
        "observed_error_sequence": sequence,
        "sample_quality": classify_quality(payload),
        "false_multiturn_by_attempt_count": is_false_multiturn_candidate(payload),
    }


def audit_run_dir(run_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in raw_payload_paths(run_dir):
        payload = load_json(path)
        if not payload:
            continue
        if not isinstance(payload.get("attempts"), list):
            continue
        rows.append(audit_payload(run_dir, path, payload))
    return rows


def summarize_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    quality_counts = Counter(str(row.get("sample_quality") or "") for row in rows)
    status_counts = Counter(str(row.get("status") or "") for row in rows)
    by_run: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        by_run[str(row.get("run_dir") or "")][str(row.get("sample_quality") or "")] += 1
    pass_rows = [row for row in rows if row.get("status") == "PASS"]
    true_multi = [row for row in rows if row.get("sample_quality") == "true_multi_repair_pass"]
    false_multi = [row for row in rows if row.get("false_multiturn_by_attempt_count")]
    return {
        "version": "v0.22.2",
        "status": "PASS" if rows else "REVIEW",
        "analysis_scope": "offline_true_multiturn_repair_round_audit",
        "audited_case_count": len(rows),
        "pass_count": len(pass_rows),
        "true_multi_repair_pass_count": len(true_multi),
        "false_multiturn_by_attempt_count": len(false_multi),
        "quality_counts": dict(sorted(quality_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "quality_counts_by_run_dir": {
            run_dir: dict(sorted(counter.items())) for run_dir, counter in sorted(by_run.items())
        },
        "discipline": "repair_round_count_not_executor_attempt_count",
        "conclusion": (
            "true_multiturn_audit_ready"
            if rows
            else "true_multiturn_audit_has_no_rows"
        ),
    }


def write_outputs(out_dir: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "case_audit.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def run_true_multiturn_audit(
    *,
    run_dirs: list[Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    selected_run_dirs = list(run_dirs or DEFAULT_RUN_DIRS)
    rows: list[dict[str, Any]] = []
    for run_dir in selected_run_dirs:
        rows.extend(audit_run_dir(run_dir))
    summary = summarize_audit(rows)
    write_outputs(out_dir, rows, summary)
    return summary
