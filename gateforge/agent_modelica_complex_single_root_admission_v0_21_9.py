from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from gateforge.agent_modelica_generation_audit_v0_19_60 import classify_generation_failure
from gateforge.experiment_runner_shared import run_check_only_omc


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_COMPLEX_CANDIDATE_PATH = (
    REPO_ROOT / "artifacts" / "complex_single_root_pack_v0_21_8" / "complex_candidates.jsonl"
)
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "complex_single_root_admission_v0_21_9"


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


def admit_complex_candidate(
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
    bucket_id = str(classification.get("bucket_id") or "")
    target_admitted = bool(not check_pass and bucket_id not in {"", "PASS", "UNCLASSIFIED"})
    return {
        "candidate_id": row.get("candidate_id"),
        "mutation_pattern": row.get("mutation_pattern"),
        "root_cause_shape": row.get("root_cause_shape"),
        "impact_point_count": row.get("impact_point_count"),
        "source_model_path": row.get("source_model_path"),
        "target_model_path": row.get("target_model_path"),
        "target_check_pass": bool(check_pass),
        "target_bucket_id": bucket_id,
        "target_classification_source": classification.get("classification_source"),
        "target_evidence_excerpt": str(classification.get("evidence_excerpt") or omc_output or "")[:1000],
        "target_admission_status": "admitted_complex_target_failure" if target_admitted else "rejected_target_not_classified",
        "repair_eval_discipline": "agent_llm_omc_only_no_deterministic_repair",
    }


def summarize_admission(rows: list[dict[str, Any]]) -> dict[str, Any]:
    admitted = [row for row in rows if row.get("target_admission_status") == "admitted_complex_target_failure"]
    by_pattern = Counter(str(row.get("mutation_pattern") or "") for row in rows)
    admitted_by_pattern = Counter(str(row.get("mutation_pattern") or "") for row in admitted)
    by_bucket = Counter(str(row.get("target_bucket_id") or "") for row in admitted)
    pass_rate = len(admitted) / len(rows) if rows else 0.0
    return {
        "version": "v0.21.9",
        "status": "PASS" if rows and pass_rate >= 0.8 else "REVIEW",
        "candidate_count": len(rows),
        "admitted_count": len(admitted),
        "rejected_count": len(rows) - len(admitted),
        "admission_pass_rate": round(pass_rate, 6),
        "pattern_counts": dict(sorted(by_pattern.items())),
        "admitted_pattern_counts": dict(sorted(admitted_by_pattern.items())),
        "admitted_bucket_counts": dict(sorted(by_bucket.items())),
        "repair_eval_discipline": "agent_llm_omc_only_no_deterministic_repair",
        "next_action": "run_agent_multiturn_screening_on_admitted_complex_targets",
        "conclusion": (
            "complex_single_root_targets_ready_for_multiturn_screening"
            if rows and pass_rate >= 0.8
            else "complex_single_root_targets_need_review"
        ),
    }


def render_report(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# v0.21.9 Complex Single-Root Admission",
        "",
        f"- status: `{summary.get('status')}`",
        f"- candidate_count: `{summary.get('candidate_count')}`",
        f"- admitted_count: `{summary.get('admitted_count')}`",
        f"- admission_pass_rate: `{summary.get('admission_pass_rate')}`",
        "",
        "## Admitted Bucket Counts",
    ]
    for bucket_id, count in (summary.get("admitted_bucket_counts") or {}).items():
        lines.append(f"- `{bucket_id}`: `{count}`")
    lines.extend(["", "## Candidates"])
    for row in rows:
        lines.append(
            f"- `{row.get('candidate_id')}` pattern=`{row.get('mutation_pattern')}` "
            f"bucket=`{row.get('target_bucket_id')}` status=`{row.get('target_admission_status')}`"
        )
    return "\n".join(lines) + "\n"


def write_outputs(out_dir: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "admitted_complex_targets.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "REPORT.md").write_text(render_report(summary, rows), encoding="utf-8")


def run_complex_single_root_admission(
    *,
    complex_candidate_path: Path = DEFAULT_COMPLEX_CANDIDATE_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
    run_check: Callable[[str, str], tuple[bool, str]] = run_check_only_omc,
) -> dict[str, Any]:
    candidates = load_jsonl(complex_candidate_path)
    rows = [admit_complex_candidate(row, run_check=run_check) for row in candidates]
    summary = summarize_admission(rows)
    write_outputs(out_dir, rows, summary)
    return summary
