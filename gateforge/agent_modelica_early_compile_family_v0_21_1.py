from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PLAN_PATH = REPO_ROOT / "artifacts" / "distribution_alignment_plan_v0_21_0" / "summary.json"
DEFAULT_CANDIDATE_PATH = REPO_ROOT / "artifacts" / "mutation_candidate_distill_v0_19_61" / "candidates.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "early_compile_family_v0_21_1"

TARGET_BUCKETS = {"ET01", "ET02", "ET03"}

FAMILY_SPEC_BY_BUCKET = {
    "ET01": {
        "family_id": "generation_parse_load_failure",
        "mutation_goal": "represent parser or load failures seen in real generated Modelica",
        "source_requirement": "clean standalone model with matching workflow intent",
        "target_requirement": "mutated target fails before semantic repair with parser or load evidence",
    },
    "ET02": {
        "family_id": "missing_component_or_library_reference",
        "mutation_goal": "represent missing class, component, or library reference failures",
        "source_requirement": "clean model using a valid component or library reference",
        "target_requirement": "mutated target fails with missing class or component lookup evidence",
    },
    "ET03": {
        "family_id": "undeclared_identifier_from_generation",
        "mutation_goal": "represent generated references to identifiers that are not declared",
        "source_requirement": "clean model with a comparable declared identifier site",
        "target_requirement": "mutated target fails with undeclared identifier evidence",
    },
}


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


def build_family_candidate(row: dict[str, Any]) -> dict[str, Any] | None:
    bucket_id = str(row.get("bucket_id") or "")
    if bucket_id not in TARGET_BUCKETS:
        return None
    family_spec = FAMILY_SPEC_BY_BUCKET[bucket_id]
    source_task_id = str(row.get("source_task_id") or "")
    candidate_id = str(row.get("candidate_id") or "")
    return {
        "family_candidate_id": f"v0211_{candidate_id}",
        "source_candidate_id": candidate_id,
        "source_task_id": source_task_id,
        "bucket_id": bucket_id,
        "domain": str(row.get("domain") or ""),
        "difficulty": str(row.get("difficulty") or ""),
        "family_id": family_spec["family_id"],
        "mutation_goal": family_spec["mutation_goal"],
        "source_requirement": family_spec["source_requirement"],
        "target_requirement": family_spec["target_requirement"],
        "observed_failure_excerpt": str(row.get("observed_failure_excerpt") or "")[:1000],
        "real_failure_linked": bool(source_task_id and row.get("observed_failure_excerpt")),
        "workflow_proximal_evidence": bool(row.get("domain") and row.get("difficulty")),
        "source_viability_status": "pending_clean_source_pairing",
        "target_failure_status": "pending_omc_validation",
        "benchmark_admission_status": "isolated_family_candidate_only",
    }


def build_family_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        candidate = build_family_candidate(row)
        if not candidate:
            continue
        candidate_id = str(candidate.get("family_candidate_id") or "")
        if candidate_id in seen:
            continue
        seen.add(candidate_id)
        candidates.append(candidate)
    return candidates


def summarize_family_candidates(
    *,
    plan_summary: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    by_bucket = Counter(str(row.get("bucket_id") or "") for row in candidates)
    ready_for_audit = [
        row for row in candidates if row.get("real_failure_linked") and row.get("workflow_proximal_evidence")
    ]
    missing_buckets = sorted(TARGET_BUCKETS - set(by_bucket))
    status = "PASS" if not missing_buckets and len(ready_for_audit) == len(candidates) and candidates else "REVIEW"
    return {
        "version": "v0.21.1",
        "status": status,
        "source_plan_status": plan_summary.get("status"),
        "family_candidate_count": len(candidates),
        "ready_for_admission_audit_count": len(ready_for_audit),
        "candidate_count_by_bucket": dict(sorted(by_bucket.items())),
        "missing_target_buckets": missing_buckets,
        "benchmark_admission_status": "isolated_family_candidate_only",
        "source_viability_status": "pending_clean_source_pairing",
        "target_failure_status": "pending_omc_validation",
        "next_version": "v0.21.2",
        "next_action": "workflow_proximal_admission_audit",
        "conclusion": (
            "early_compile_family_candidates_ready_for_audit"
            if status == "PASS"
            else "early_compile_family_candidates_need_review"
        ),
    }


def render_report(summary: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
    lines = [
        "# v0.21.1 Early Compile Family Candidates",
        "",
        f"- status: `{summary.get('status')}`",
        f"- family_candidate_count: `{summary.get('family_candidate_count')}`",
        f"- ready_for_admission_audit_count: `{summary.get('ready_for_admission_audit_count')}`",
        f"- benchmark_admission_status: `{summary.get('benchmark_admission_status')}`",
        "",
        "## Candidate Counts By Bucket",
    ]
    for bucket_id, count in (summary.get("candidate_count_by_bucket") or {}).items():
        lines.append(f"- `{bucket_id}`: `{count}`")
    lines.extend(["", "## Candidates"])
    for row in candidates:
        lines.append(
            f"- `{row.get('family_candidate_id')}` `{row.get('bucket_id')}` "
            f"`{row.get('family_id')}`"
        )
    return "\n".join(lines) + "\n"


def write_outputs(out_dir: Path, candidates: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "family_candidates.jsonl").open("w", encoding="utf-8") as fh:
        for candidate in candidates:
            fh.write(json.dumps(candidate, sort_keys=True) + "\n")
    (out_dir / "REPORT.md").write_text(render_report(summary, candidates), encoding="utf-8")


def run_early_compile_family_builder(
    *,
    plan_path: Path = DEFAULT_PLAN_PATH,
    candidate_path: Path = DEFAULT_CANDIDATE_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    plan_summary = load_json(plan_path)
    source_candidates = load_jsonl(candidate_path)
    candidates = build_family_candidates(source_candidates)
    summary = summarize_family_candidates(plan_summary=plan_summary, candidates=candidates)
    write_outputs(out_dir, candidates, summary)
    return summary
