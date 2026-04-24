from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from gateforge.agent_modelica_generation_audit_v0_19_60 import classify_generation_failure
from gateforge.experiment_runner_shared import run_check_only_omc


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_BACKED_PATH = (
    REPO_ROOT / "artifacts" / "source_backed_family_pack_v0_21_5" / "source_backed_candidates.jsonl"
)
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "source_backed_target_admission_v0_21_6"


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


def validate_target_candidate(
    row: dict[str, Any],
    *,
    run_check: Callable[[str, str], tuple[bool, str]] = run_check_only_omc,
) -> dict[str, Any]:
    target_path = Path(str(row.get("target_model_path") or ""))
    target_text = target_path.read_text(encoding="utf-8")
    model_name = str(row.get("target_model_name") or row.get("source_model_name") or "")
    check_pass, omc_output = run_check(target_text, model_name)
    classification = classify_generation_failure(
        model_text=target_text,
        model_name=model_name,
        check_pass=bool(check_pass),
        simulate_pass=False,
        omc_output=omc_output,
    )
    expected_bucket = str(row.get("bucket_id") or "")
    observed_bucket = str(classification.get("bucket_id") or "")
    target_verified = bool(not check_pass and observed_bucket == expected_bucket)
    return {
        "source_backed_candidate_id": row.get("source_backed_candidate_id"),
        "family_candidate_id": row.get("family_candidate_id"),
        "bucket_id": expected_bucket,
        "source_model_path": row.get("source_model_path"),
        "target_model_path": row.get("target_model_path"),
        "source_viability_status": row.get("source_viability_status"),
        "target_check_pass": bool(check_pass),
        "target_reclassified_bucket": observed_bucket,
        "target_failure_status": "verified_target_failure" if target_verified else "target_validation_failed",
        "target_failure_verified": target_verified,
        "target_omc_excerpt": str(omc_output or "")[:1000],
        "benchmark_admission_status": (
            "main_admissible_source_target_pair"
            if target_verified
            else "blocked_from_main_benchmark"
        ),
    }


def summarize_target_admission(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_status = Counter(str(row.get("benchmark_admission_status") or "") for row in rows)
    by_bucket = Counter(str(row.get("bucket_id") or "") for row in rows)
    verified_by_bucket = Counter(
        str(row.get("bucket_id") or "") for row in rows if row.get("target_failure_verified")
    )
    main_count = by_status.get("main_admissible_source_target_pair", 0)
    return {
        "version": "v0.21.6",
        "status": "PASS" if rows and main_count == len(rows) else "REVIEW",
        "validated_candidate_count": len(rows),
        "main_admissible_count": main_count,
        "blocked_from_main_benchmark_count": by_status.get("blocked_from_main_benchmark", 0),
        "status_counts": dict(sorted(by_status.items())),
        "candidate_count_by_bucket": dict(sorted(by_bucket.items())),
        "verified_count_by_bucket": dict(sorted(verified_by_bucket.items())),
        "benchmark_admission_decision": (
            "promote_verified_source_target_pairs"
            if rows and main_count == len(rows)
            else "promote_verified_pairs_only"
        ),
        "next_action": "distribution_reaudit_with_source_backed_pairs",
        "conclusion": (
            "source_backed_targets_main_admissible"
            if rows and main_count == len(rows)
            else "source_backed_targets_partially_admissible"
        ),
    }


def render_report(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# v0.21.6 Source-Backed Target Admission",
        "",
        f"- status: `{summary.get('status')}`",
        f"- validated_candidate_count: `{summary.get('validated_candidate_count')}`",
        f"- main_admissible_count: `{summary.get('main_admissible_count')}`",
        f"- blocked_from_main_benchmark_count: `{summary.get('blocked_from_main_benchmark_count')}`",
        "",
        "## Verified Counts By Bucket",
    ]
    for bucket_id, count in (summary.get("verified_count_by_bucket") or {}).items():
        lines.append(f"- `{bucket_id}`: `{count}`")
    lines.extend(["", "## Candidates"])
    for row in rows:
        lines.append(
            f"- `{row.get('source_backed_candidate_id')}` expected=`{row.get('bucket_id')}` "
            f"observed=`{row.get('target_reclassified_bucket')}` "
            f"status=`{row.get('benchmark_admission_status')}`"
        )
    return "\n".join(lines) + "\n"


def write_outputs(out_dir: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "target_admission.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "REPORT.md").write_text(render_report(summary, rows), encoding="utf-8")


def run_source_backed_target_admission(
    *,
    source_backed_path: Path = DEFAULT_SOURCE_BACKED_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
    run_check: Callable[[str, str], tuple[bool, str]] = run_check_only_omc,
) -> dict[str, Any]:
    candidates = load_jsonl(source_backed_path)
    rows = [validate_target_candidate(row, run_check=run_check) for row in candidates]
    summary = summarize_target_admission(rows)
    write_outputs(out_dir, rows, summary)
    return summary
