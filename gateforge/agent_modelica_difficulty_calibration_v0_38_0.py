from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "difficulty_calibration_v0_38_0"

DIFFICULTY_BUCKETS = {
    "easy",
    "unstable",
    "hard_positive",
    "hard_candidate",
    "hard_negative",
    "known_hard_prior",
    "needs_baseline",
    "invalid",
}


def _known_hard_count(seed: dict[str, Any]) -> int:
    return len([item for item in seed.get("known_hard_for") or [] if str(item).strip()])


def _has_prompt_leakage(gate_row: dict[str, Any] | None) -> bool:
    return bool(gate_row and "prompt_leakage" in gate_row.get("blockers", []))


def classify_seed_difficulty(
    seed: dict[str, Any],
    *,
    gate_row: dict[str, Any] | None = None,
    pass_count: int = 0,
    fail_count: int = 0,
) -> dict[str, Any]:
    case_id = str(seed.get("case_id") or "")
    registry_status = str(seed.get("registry_status") or "")
    admission_status = str(seed.get("admission_status") or "")
    repeatability_status = str(seed.get("repeatability_status") or "")
    known_hard_count = _known_hard_count(seed)
    leakage = _has_prompt_leakage(gate_row)
    formal_eligible = bool(gate_row.get("formal_benchmark_eligible")) if gate_row else False

    bucket = "needs_baseline"
    reasons: list[str] = []
    if leakage or str(gate_row.get("status") if gate_row else "PASS") == "FAIL":
        bucket = "invalid"
        reasons.append("benchmark_gate_failed")
    elif pass_count > 0 and fail_count > 0:
        bucket = "unstable"
        reasons.append("mixed_pass_fail_evidence")
    elif pass_count > 0 and fail_count == 0:
        bucket = "easy"
        reasons.append("baseline_pass_evidence")
    elif fail_count >= 2 and pass_count == 0:
        bucket = "hard_negative"
        reasons.append("repeat_baseline_failure")
    elif fail_count > 0 and pass_count == 0:
        bucket = "hard_candidate"
        reasons.append("single_run_failure_needs_repeatability")
    elif formal_eligible and known_hard_count > 0 and repeatability_status == "repeatable":
        bucket = "hard_negative"
        reasons.append("repeatable_known_hard_failure")
    elif admission_status == "admitted_via_live_failure" and known_hard_count > 0:
        bucket = "known_hard_prior"
        reasons.append("known_hard_without_formal_repeatability")
    elif registry_status in {"admitted", "repeatable_candidate", "formal_benchmark_seed"}:
        bucket = "needs_baseline"
        reasons.append("admitted_without_baseline_evidence")
    else:
        bucket = "needs_baseline"
        reasons.append("candidate_needs_admission_or_baseline")

    return {
        "case_id": case_id,
        "family": str(seed.get("family") or ""),
        "difficulty_bucket": bucket,
        "reasons": reasons,
        "formal_benchmark_eligible": formal_eligible,
        "known_hard_count": known_hard_count,
        "pass_count": int(pass_count),
        "fail_count": int(fail_count),
        "registry_status": registry_status,
        "admission_status": admission_status,
        "repeatability_status": repeatability_status,
    }


def build_difficulty_calibration_summary(
    seeds: list[dict[str, Any]],
    *,
    gate_rows: list[dict[str, Any]] | None = None,
    run_evidence_by_case: dict[str, dict[str, int]] | None = None,
    version: str = "v0.38.0",
) -> dict[str, Any]:
    gate_by_case = {str(row.get("case_id") or ""): row for row in gate_rows or []}
    evidence = run_evidence_by_case or {}
    rows = []
    bucket_counts: dict[str, int] = {}
    for seed in seeds:
        case_id = str(seed.get("case_id") or "")
        counts = evidence.get(case_id, {})
        row = classify_seed_difficulty(
            seed,
            gate_row=gate_by_case.get(case_id),
            pass_count=int(counts.get("pass_count") or 0),
            fail_count=int(counts.get("fail_count") or 0),
        )
        rows.append(row)
        bucket = row["difficulty_bucket"]
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
    return {
        "version": version,
        "analysis_scope": "difficulty_calibration",
        "status": "PASS" if rows else "REVIEW",
        "seed_count": len(rows),
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "formal_hard_negative_case_ids": [
            row["case_id"] for row in rows if row["difficulty_bucket"] == "hard_negative"
        ],
        "known_hard_prior_case_ids": [
            row["case_id"] for row in rows if row["difficulty_bucket"] == "known_hard_prior"
        ],
        "invalid_case_ids": [row["case_id"] for row in rows if row["difficulty_bucket"] == "invalid"],
        "results": rows,
        "scope_note": (
            "Known-hard prior is not the same as calibrated hard negative. Formal hard negatives require repeatable "
            "known-hard evidence under the hard pool gate."
        ),
    }


def write_difficulty_calibration_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
