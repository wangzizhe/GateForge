from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_jsonl


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESULT_PATHS = (
    REPO_ROOT / "artifacts" / "hard_core_adjacent_baseline_smoke_v0_48_5" / "results.jsonl",
    REPO_ROOT / "artifacts" / "hard_core_adjacent_baseline_batch2_v0_48_5" / "results.jsonl",
    REPO_ROOT / "artifacts" / "hard_core_adjacent_baseline_batch3_v0_48_5" / "results.jsonl",
    REPO_ROOT / "artifacts" / "hard_core_adjacent_baseline_batch4_v0_48_5" / "results.jsonl",
    REPO_ROOT / "artifacts" / "hard_core_adjacent_baseline_repeat_v0_48_6" / "results.jsonl",
    REPO_ROOT / "artifacts" / "hard_core_adjacent_baseline_repeat_batch2_v0_48_6" / "results.jsonl",
    REPO_ROOT / "artifacts" / "hard_core_adjacent_baseline_repeat_batch3_v0_48_6" / "results.jsonl",
)
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hard_core_adjacent_difficulty_summary_v0_48_7"


def _rows_by_case(paths: list[Path]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for path in paths:
        for row in load_jsonl(path):
            case_id = str(row.get("case_id") or "")
            if case_id:
                out.setdefault(case_id, []).append(row)
    return out


def classify_case_difficulty(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "needs_baseline"
    if any(row.get("provider_error") for row in rows):
        return "needs_more_runs"
    verdicts = [str(row.get("final_verdict") or "") for row in rows]
    if len(rows) >= 2 and all(verdict != "PASS" for verdict in verdicts):
        return "hard_negative_candidate"
    if len(rows) >= 2 and any(verdict == "PASS" for verdict in verdicts) and any(verdict != "PASS" for verdict in verdicts):
        return "unstable"
    if all(verdict == "PASS" for verdict in verdicts):
        return "easy"
    return "single_run_fail_needs_repeat"


def build_hard_core_adjacent_difficulty_summary(
    *,
    result_paths: list[Path],
    version: str = "v0.48.7",
) -> dict[str, Any]:
    rows_by_case = _rows_by_case(result_paths)
    results: list[dict[str, Any]] = []
    bucket_counts: dict[str, int] = {}
    for case_id, rows in sorted(rows_by_case.items()):
        bucket = classify_case_difficulty(rows)
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
        results.append(
            {
                "case_id": case_id,
                "run_count": len(rows),
                "pass_count": sum(1 for row in rows if row.get("final_verdict") == "PASS"),
                "fail_count": sum(1 for row in rows if row.get("final_verdict") != "PASS"),
                "provider_error_count": sum(1 for row in rows if row.get("provider_error")),
                "difficulty_bucket": bucket,
            }
        )
    hard_candidates = [row["case_id"] for row in results if row["difficulty_bucket"] == "hard_negative_candidate"]
    return {
        "version": version,
        "analysis_scope": "hard_core_adjacent_difficulty_summary",
        "status": "PASS" if results else "REVIEW",
        "evidence_role": "formal_experiment",
        "conclusion_allowed": bool(results and not any(row["provider_error_count"] for row in results)),
        "case_count": len(results),
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "hard_negative_candidate_case_ids": hard_candidates,
        "results": results,
        "decision": (
            "expand_around_stable_hard_candidate"
            if hard_candidates
            else "construct_more_adjacent_variants"
        ),
        "scope_note": (
            "Two-run failure is a hard-negative candidate for this expansion batch. Promotion to formal hard negative "
            "still requires registry/repeatability integration."
        ),
    }


def write_hard_core_adjacent_difficulty_summary_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_hard_core_adjacent_difficulty_summary(
    *,
    result_paths: tuple[Path, ...] = DEFAULT_RESULT_PATHS,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_hard_core_adjacent_difficulty_summary(result_paths=list(result_paths))
    write_hard_core_adjacent_difficulty_summary_outputs(out_dir=out_dir, summary=summary)
    return summary
