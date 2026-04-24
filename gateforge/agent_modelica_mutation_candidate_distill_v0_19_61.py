from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_DIR = REPO_ROOT / "artifacts" / "generation_audit_v0_19_60"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "mutation_candidate_distill_v0_19_61"

GAP_BUCKETS = {"ET01", "ET02", "ET03"}

FAMILY_BY_BUCKET = {
    "ET01": "generation_parse_load_failure",
    "ET02": "missing_component_or_library_reference",
    "ET03": "undeclared_identifier_from_generation",
    "ET07": "generation_equation_surplus",
}

OPERATOR_BY_BUCKET = {
    "ET01": "introduce_parse_or_load_breakage_from_real_generation",
    "ET02": "replace_reference_with_missing_component_or_library_path",
    "ET03": "introduce_unbound_identifier_reference",
    "ET07": "add_redundant_generated_equation",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_generation_task_results(input_dir: Path = DEFAULT_INPUT_DIR) -> list[dict[str, Any]]:
    tasks_dir = input_dir / "tasks"
    rows: list[dict[str, Any]] = []
    for path in sorted(tasks_dir.glob("*.json")):
        payload = load_json(path)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _safe_id(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", str(text or "")).strip("_")


def _classification(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("classification")
    return value if isinstance(value, dict) else {}


def _bucket_id(row: dict[str, Any]) -> str:
    return str(_classification(row).get("bucket_id") or "")


def build_mutation_candidate(row: dict[str, Any]) -> dict[str, Any] | None:
    bucket_id = _bucket_id(row)
    if str(row.get("final_status") or "") == "pass" or bucket_id == "PASS":
        return None
    family = FAMILY_BY_BUCKET.get(bucket_id)
    if not family:
        return None
    source_task_id = str(row.get("task_id") or "")
    candidate_id = f"v01961_{_safe_id(bucket_id.lower())}_{_safe_id(source_task_id)}"
    evidence_excerpt = str(_classification(row).get("evidence_excerpt") or row.get("omc_output_excerpt") or "")
    candidate = {
        "candidate_id": candidate_id,
        "source_task_id": source_task_id,
        "bucket_id": bucket_id,
        "domain": str(row.get("domain") or ""),
        "difficulty": str(row.get("difficulty") or ""),
        "source_model_name": str(row.get("model_name") or ""),
        "observed_failure_excerpt": evidence_excerpt[:1000],
        "classification_source": str(_classification(row).get("classification_source") or ""),
        "proposed_mutation_family": family,
        "mutation_operator": OPERATOR_BY_BUCKET.get(bucket_id, "unknown"),
        "priority_bucket": "main_gap_bucket" if bucket_id in GAP_BUCKETS else "covered_existing_bucket",
        "isolation_status": "isolated_candidate_pool_only",
    }
    admission = evaluate_candidate_admission(candidate, row)
    candidate["admission_gates"] = admission["gates"]
    candidate["benchmark_admission_status"] = admission["status"]
    candidate["rejection_reasons"] = admission["rejection_reasons"]
    return candidate


def evaluate_candidate_admission(candidate: dict[str, Any], source_row: dict[str, Any]) -> dict[str, Any]:
    evidence = str(candidate.get("observed_failure_excerpt") or "").strip()
    model_text = str(source_row.get("model_text") or "").strip()
    task_id = str(candidate.get("source_task_id") or "").strip()
    bucket_id = str(candidate.get("bucket_id") or "").strip()
    family = str(candidate.get("proposed_mutation_family") or "").strip()
    final_status = str(source_row.get("final_status") or "")
    gates = {
        "workflow_proximal": bool(task_id and model_text and evidence and final_status == "fail"),
        "anti_fake_workflow": bool(bucket_id in FAMILY_BY_BUCKET and family and len(evidence) >= 12),
        "evidence_linked": bool(
            task_id
            and source_row.get("classification")
            and source_row.get("model_name")
            and evidence
        ),
        "isolation_only": str(candidate.get("isolation_status") or "") == "isolated_candidate_pool_only",
    }
    rejection_reasons = [name for name, passed in gates.items() if not passed]
    return {
        "status": "admitted" if all(gates.values()) else "rejected",
        "gates": gates,
        "rejection_reasons": rejection_reasons,
    }


def build_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        candidate = build_mutation_candidate(row)
        if not candidate:
            continue
        candidate_id = str(candidate.get("candidate_id") or "")
        if candidate_id in seen:
            continue
        seen.add(candidate_id)
        candidates.append(candidate)
    return candidates


def build_distill_summary(candidates: list[dict[str, Any]], source_rows: list[dict[str, Any]]) -> dict[str, Any]:
    admitted = [row for row in candidates if row.get("benchmark_admission_status") == "admitted"]
    rejected = [row for row in candidates if row.get("benchmark_admission_status") != "admitted"]
    by_bucket = Counter(str(row.get("bucket_id") or "") for row in candidates)
    admitted_by_bucket = Counter(str(row.get("bucket_id") or "") for row in admitted)
    gap_candidates = [row for row in candidates if row.get("priority_bucket") == "main_gap_bucket"]
    pass_rate = len(admitted) / len(candidates) if candidates else 0.0
    return {
        "version": "v0.19.61",
        "status": "PASS" if pass_rate >= 0.60 and len(admitted) >= 3 else "FAIL",
        "source_generation_task_count": len(source_rows),
        "source_failure_count": sum(1 for row in source_rows if str(row.get("final_status") or "") == "fail"),
        "candidate_count": len(candidates),
        "admitted_count": len(admitted),
        "rejected_count": len(rejected),
        "admission_pass_rate": round(pass_rate, 6),
        "candidate_count_by_bucket": dict(sorted(by_bucket.items())),
        "admitted_count_by_bucket": dict(sorted(admitted_by_bucket.items())),
        "main_gap_candidate_count": len(gap_candidates),
        "isolation_status": "isolated_pool_not_main_benchmark",
        "admitted_candidate_ids": [str(row.get("candidate_id") or "") for row in admitted],
        "rejected_candidate_ids": [str(row.get("candidate_id") or "") for row in rejected],
        "conclusion": (
            "mutation_candidate_pool_admitted"
            if pass_rate >= 0.60 and len(admitted) >= 3
            else "mutation_candidate_pool_needs_review"
        ),
    }


def render_report(summary: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
    lines = [
        "# v0.19.61 Mutation Candidate Distill",
        "",
        f"- status: `{summary.get('status')}`",
        f"- source_generation_task_count: `{summary.get('source_generation_task_count')}`",
        f"- source_failure_count: `{summary.get('source_failure_count')}`",
        f"- candidate_count: `{summary.get('candidate_count')}`",
        f"- admitted_count: `{summary.get('admitted_count')}`",
        f"- admission_pass_rate: `{summary.get('admission_pass_rate')}`",
        f"- isolation_status: `{summary.get('isolation_status')}`",
        "",
        "## Candidate Counts By Bucket",
    ]
    for bucket_id, count in (summary.get("candidate_count_by_bucket") or {}).items():
        lines.append(f"- `{bucket_id}`: `{count}`")
    lines.extend(["", "## Admitted Candidates"])
    for candidate in candidates:
        if candidate.get("benchmark_admission_status") != "admitted":
            continue
        lines.append(
            f"- `{candidate.get('candidate_id')}` `{candidate.get('bucket_id')}` "
            f"`{candidate.get('proposed_mutation_family')}`"
        )
    return "\n".join(lines) + "\n"


def write_outputs(out_dir: Path, candidates: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "candidates.jsonl").open("w", encoding="utf-8") as fh:
        for candidate in candidates:
            fh.write(json.dumps(candidate, sort_keys=True) + "\n")
    (out_dir / "REPORT.md").write_text(render_report(summary, candidates), encoding="utf-8")


def run_mutation_candidate_distill(
    *,
    input_dir: Path = DEFAULT_INPUT_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    source_rows = load_generation_task_results(input_dir)
    candidates = build_candidates(source_rows)
    summary = build_distill_summary(candidates, source_rows)
    write_outputs(out_dir, candidates, summary)
    return summary

