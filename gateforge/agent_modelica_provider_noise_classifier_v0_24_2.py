from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TRAJECTORY_PATHS = [
    REPO_ROOT / "artifacts" / "trajectory_schema_v0_23_2" / "normalized_trajectories.jsonl",
    REPO_ROOT / "artifacts" / "unified_repeatability_runner_v0_24_1" / "repeat_observations.jsonl",
]
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "provider_noise_classifier_v0_24_2"
PROVIDER_MARKERS = {
    "503": "provider_503",
    "service unavailable": "provider_503",
    "timeout": "provider_timeout",
    "timed out": "provider_timeout",
    "empty output": "provider_empty_output",
    "empty response": "provider_empty_output",
    "truncated": "provider_truncated_output",
    "parse error": "provider_parse_failure",
    "invalid json": "provider_parse_failure",
}
INFRA_MARKERS = {
    "docker": "infra_runtime_error",
    "class modelica": "infra_msl_load_error",
    "not found in scope": "infra_msl_load_error",
    "omc failed to start": "infra_runtime_error",
}


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


def classify_noise(row: dict[str, Any]) -> str:
    if bool(row.get("provider_failure")):
        return "provider_failure"
    if bool(row.get("oracle_failure")):
        return "infra_or_oracle_failure"
    text_parts = [
        str(row.get("final_verdict") or ""),
        str(row.get("termination") or ""),
        str(row.get("raw_feedback") or ""),
        " ".join(str(value) for value in row.get("feedback_sequence") or []),
    ]
    text = " ".join(text_parts).lower()
    for marker, label in PROVIDER_MARKERS.items():
        if marker in text:
            return label
    for marker, label in INFRA_MARKERS.items():
        if marker in text:
            return label
    if str(row.get("trajectory_class") or "") == "multi_turn_useful":
        return "llm_success"
    if str(row.get("final_verdict") or "") == "DRY_RUN":
        return "not_executed"
    return "llm_or_task_failure"


def build_noise_rows(rows: list[dict[str, Any]], *, source_artifact: str) -> list[dict[str, Any]]:
    noise_rows: list[dict[str, Any]] = []
    for row in rows:
        noise_class = classify_noise(row)
        noise_rows.append(
            {
                "case_id": str(row.get("case_id") or row.get("candidate_id") or ""),
                "candidate_id": str(row.get("candidate_id") or row.get("case_id") or ""),
                "run_id": str(row.get("run_id") or "unknown"),
                "trajectory_class": str(row.get("trajectory_class") or "unknown"),
                "final_verdict": str(row.get("final_verdict") or "UNKNOWN"),
                "noise_class": noise_class,
                "is_provider_noise": noise_class.startswith("provider_") or noise_class == "provider_failure",
                "is_infra_noise": noise_class.startswith("infra_") or noise_class == "infra_or_oracle_failure",
                "is_llm_failure": noise_class == "llm_or_task_failure",
                "is_llm_success": noise_class == "llm_success",
                "source_artifact": source_artifact,
            }
        )
    return noise_rows


def build_provider_noise_report(
    *,
    trajectory_paths: list[Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    paths = trajectory_paths or DEFAULT_TRAJECTORY_PATHS
    all_noise_rows: list[dict[str, Any]] = []
    missing_inputs: list[str] = []
    for path in paths:
        rows = load_jsonl(path)
        if not rows:
            missing_inputs.append(str(path))
            continue
        source_artifact = str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path)
        all_noise_rows.extend(build_noise_rows(rows, source_artifact=source_artifact))

    counts = Counter(row["noise_class"] for row in all_noise_rows)
    provider_noise_count = sum(1 for row in all_noise_rows if row["is_provider_noise"])
    infra_noise_count = sum(1 for row in all_noise_rows if row["is_infra_noise"])
    llm_failure_count = sum(1 for row in all_noise_rows if row["is_llm_failure"])
    llm_success_count = sum(1 for row in all_noise_rows if row["is_llm_success"])
    interpreted_denominator = len(all_noise_rows) - provider_noise_count - infra_noise_count
    status = "PASS" if all_noise_rows and not missing_inputs else "REVIEW"
    summary = {
        "version": "v0.24.2",
        "status": status,
        "analysis_scope": "provider_noise_classifier",
        "input_count": len(paths),
        "missing_inputs": missing_inputs,
        "observation_count": len(all_noise_rows),
        "noise_class_counts": dict(sorted(counts.items())),
        "provider_noise_count": provider_noise_count,
        "infra_noise_count": infra_noise_count,
        "llm_success_count": llm_success_count,
        "llm_failure_count": llm_failure_count,
        "raw_success_rate": llm_success_count / len(all_noise_rows) if all_noise_rows else 0.0,
        "noise_adjusted_interpretive_success_rate": (
            llm_success_count / interpreted_denominator if interpreted_denominator else 0.0
        ),
        "decision_metric_policy": "raw_view_remains_conservative_default",
        "discipline": {
            "executor_changes": "none",
            "deterministic_repair_added": False,
            "noise_adjusted_view_is_interpretive_only": True,
            "do_not_relabel_provider_noise_as_llm_failure": True,
        },
        "conclusion": (
            "provider_noise_classifier_ready_for_budget_policy_freeze"
            if status == "PASS"
            else "provider_noise_classifier_needs_review"
        ),
    }
    write_outputs(out_dir=out_dir, noise_rows=all_noise_rows, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, noise_rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "noise_rows.jsonl").open("w", encoding="utf-8") as fh:
        for row in noise_rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
