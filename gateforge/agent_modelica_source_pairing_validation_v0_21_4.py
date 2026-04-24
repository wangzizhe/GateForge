from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from gateforge.agent_modelica_generation_audit_v0_19_60 import (
    classify_generation_failure,
    extract_model_name,
)
from gateforge.experiment_runner_shared import run_check_only_omc


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FAMILY_CANDIDATE_PATH = (
    REPO_ROOT / "artifacts" / "early_compile_family_v0_21_1" / "family_candidates.jsonl"
)
DEFAULT_GENERATION_TASK_DIR = REPO_ROOT / "artifacts" / "generation_audit_v0_19_60" / "tasks"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "source_pairing_validation_v0_21_4"


def load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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


def load_generation_task(task_dir: Path, task_id: str) -> dict[str, Any]:
    path = task_dir / f"{task_id}.json"
    return load_json(path) if path.exists() else {}


def extract_embedded_model_text(raw_model_text: str) -> str:
    text = str(raw_model_text or "").strip()
    if not text:
        return ""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return ""
    value = payload.get("model_text") if isinstance(payload, dict) else ""
    return str(value or "").strip()


def build_source_pair(row: dict[str, Any], task_row: dict[str, Any]) -> dict[str, Any]:
    raw_model_text = str(task_row.get("model_text") or "")
    embedded_model_text = extract_embedded_model_text(raw_model_text)
    source_model_text = embedded_model_text
    source_model_name = extract_model_name(source_model_text) if source_model_text else ""
    return {
        "family_candidate_id": row.get("family_candidate_id"),
        "source_task_id": row.get("source_task_id"),
        "bucket_id": row.get("bucket_id"),
        "target_model_name": task_row.get("model_name") or "",
        "target_model_text": raw_model_text,
        "target_omc_output_excerpt": task_row.get("omc_output_excerpt") or "",
        "target_recorded_bucket": (task_row.get("classification") or {}).get("bucket_id") or "",
        "source_model_text": source_model_text,
        "source_model_name": source_model_name,
        "source_pairing_method": "embedded_json_model_text" if source_model_text else "none_available_without_repair",
    }


def validate_pair(
    pair: dict[str, Any],
    *,
    run_check: Callable[[str, str], tuple[bool, str]] = run_check_only_omc,
) -> dict[str, Any]:
    source_text = str(pair.get("source_model_text") or "")
    source_name = str(pair.get("source_model_name") or "")
    if source_text and source_name:
        source_check_pass, source_omc_output = run_check(source_text, source_name)
    else:
        source_check_pass, source_omc_output = False, "No source model text available without repair."

    target_bucket = str(pair.get("target_recorded_bucket") or "")
    target_output = str(pair.get("target_omc_output_excerpt") or "")
    target_classification = classify_generation_failure(
        model_text=str(pair.get("target_model_text") or ""),
        model_name=str(pair.get("target_model_name") or ""),
        check_pass=False,
        simulate_pass=False,
        omc_output=target_output,
    )
    target_failure_verified = bool(target_bucket and target_classification.get("bucket_id") == target_bucket)
    source_viability_status = "verified_clean_source" if source_check_pass else "source_not_viable"
    target_failure_status = "verified_target_failure" if target_failure_verified else "target_bucket_mismatch"
    return {
        "family_candidate_id": pair.get("family_candidate_id"),
        "source_task_id": pair.get("source_task_id"),
        "bucket_id": pair.get("bucket_id"),
        "source_pairing_method": pair.get("source_pairing_method"),
        "source_model_name": source_name,
        "source_viability_status": source_viability_status,
        "source_check_pass": bool(source_check_pass),
        "source_omc_excerpt": str(source_omc_output or "")[:1000],
        "target_failure_status": target_failure_status,
        "target_failure_verified": target_failure_verified,
        "target_recorded_bucket": target_bucket,
        "target_reclassified_bucket": target_classification.get("bucket_id"),
        "main_benchmark_status": (
            "main_admissible_source_target_pair"
            if source_check_pass and target_failure_verified
            else "blocked_from_main_benchmark"
        ),
    }


def summarize_validations(rows: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(str(row.get("main_benchmark_status") or "") for row in rows)
    source_counts = Counter(str(row.get("source_viability_status") or "") for row in rows)
    target_counts = Counter(str(row.get("target_failure_status") or "") for row in rows)
    bucket_counts = Counter(str(row.get("bucket_id") or "") for row in rows)
    main_count = status_counts.get("main_admissible_source_target_pair", 0)
    return {
        "version": "v0.21.4",
        "status": "PASS",
        "validated_pair_count": len(rows),
        "main_admissible_count": main_count,
        "blocked_from_main_benchmark_count": status_counts.get("blocked_from_main_benchmark", 0),
        "status_counts": dict(sorted(status_counts.items())),
        "source_viability_counts": dict(sorted(source_counts.items())),
        "target_failure_counts": dict(sorted(target_counts.items())),
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "benchmark_admission_decision": (
            "promote_verified_pairs_only" if main_count else "do_not_promote_to_main_benchmark"
        ),
        "next_action": (
            "rerun_admission_and_distribution_accounting_for_verified_pairs"
            if main_count
            else "manual_clean_source_pairing_required"
        ),
        "conclusion": (
            "some_source_target_pairs_verified"
            if main_count
            else "no_main_admissible_pairs_from_existing_generation_outputs"
        ),
    }


def render_report(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# v0.21.4 Source Pairing Validation",
        "",
        f"- status: `{summary.get('status')}`",
        f"- validated_pair_count: `{summary.get('validated_pair_count')}`",
        f"- main_admissible_count: `{summary.get('main_admissible_count')}`",
        f"- blocked_from_main_benchmark_count: `{summary.get('blocked_from_main_benchmark_count')}`",
        f"- benchmark_admission_decision: `{summary.get('benchmark_admission_decision')}`",
        "",
        "## Source Viability Counts",
    ]
    for key, count in (summary.get("source_viability_counts") or {}).items():
        lines.append(f"- `{key}`: `{count}`")
    lines.extend(["", "## Target Failure Counts"])
    for key, count in (summary.get("target_failure_counts") or {}).items():
        lines.append(f"- `{key}`: `{count}`")
    lines.extend(["", "## Validated Pairs"])
    for row in rows:
        lines.append(
            f"- `{row.get('family_candidate_id')}` `{row.get('bucket_id')}` "
            f"source=`{row.get('source_viability_status')}` "
            f"target=`{row.get('target_failure_status')}`"
        )
    return "\n".join(lines) + "\n"


def write_outputs(out_dir: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "validated_pairs.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "REPORT.md").write_text(render_report(summary, rows), encoding="utf-8")


def run_source_pairing_validation(
    *,
    family_candidate_path: Path = DEFAULT_FAMILY_CANDIDATE_PATH,
    generation_task_dir: Path = DEFAULT_GENERATION_TASK_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
    run_check: Callable[[str, str], tuple[bool, str]] = run_check_only_omc,
) -> dict[str, Any]:
    family_candidates = load_jsonl(family_candidate_path)
    rows: list[dict[str, Any]] = []
    for candidate in family_candidates:
        task_row = load_generation_task(generation_task_dir, str(candidate.get("source_task_id") or ""))
        pair = build_source_pair(candidate, task_row)
        rows.append(validate_pair(pair, run_check=run_check))
    summary = summarize_validations(rows)
    write_outputs(out_dir, rows, summary)
    return summary
