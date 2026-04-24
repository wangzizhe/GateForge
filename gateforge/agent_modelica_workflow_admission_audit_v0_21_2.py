from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FAMILY_CANDIDATE_PATH = (
    REPO_ROOT / "artifacts" / "early_compile_family_v0_21_1" / "family_candidates.jsonl"
)
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "workflow_admission_audit_v0_21_2"


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


def audit_family_candidate(row: dict[str, Any]) -> dict[str, Any]:
    gates = {
        "real_failure_linked": bool(row.get("real_failure_linked")),
        "workflow_proximal": bool(row.get("workflow_proximal_evidence")),
        "anti_fake_workflow": bool(row.get("mutation_goal") and row.get("source_task_id")),
        "source_viability_verified": str(row.get("source_viability_status") or "") == "verified_clean_source",
        "target_failure_verified": str(row.get("target_failure_status") or "") == "verified_target_failure",
        "isolation_first": str(row.get("benchmark_admission_status") or "") == "isolated_family_candidate_only",
    }
    blocking_reasons = [
        name
        for name in ("source_viability_verified", "target_failure_verified")
        if not gates[name]
    ]
    soft_warnings = [
        name
        for name in ("real_failure_linked", "workflow_proximal", "anti_fake_workflow", "isolation_first")
        if not gates[name]
    ]
    main_status = "main_admissible" if all(gates.values()) else "blocked_from_main_benchmark"
    return {
        "family_candidate_id": row.get("family_candidate_id"),
        "bucket_id": row.get("bucket_id"),
        "family_id": row.get("family_id"),
        "gates": gates,
        "blocking_reasons": blocking_reasons,
        "soft_warnings": soft_warnings,
        "main_benchmark_status": main_status,
        "recommended_next_action": (
            "promote_to_main_benchmark"
            if main_status == "main_admissible"
            else "pair_with_clean_source_and_validate_target_failure"
        ),
    }


def summarize_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(str(row.get("main_benchmark_status") or "") for row in rows)
    bucket_counts = Counter(str(row.get("bucket_id") or "") for row in rows)
    blocking_counts: Counter[str] = Counter()
    for row in rows:
        blocking_counts.update(str(reason) for reason in row.get("blocking_reasons") or [])
    main_admissible = status_counts.get("main_admissible", 0)
    blocked = status_counts.get("blocked_from_main_benchmark", 0)
    status = "PASS" if rows and blocked == len(rows) and main_admissible == 0 else "REVIEW"
    return {
        "version": "v0.21.2",
        "status": status,
        "audited_candidate_count": len(rows),
        "main_admissible_count": main_admissible,
        "blocked_from_main_benchmark_count": blocked,
        "status_counts": dict(sorted(status_counts.items())),
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "blocking_reason_counts": dict(sorted(blocking_counts.items())),
        "benchmark_admission_decision": "do_not_promote_to_main_benchmark",
        "next_version": "v0.21.3",
        "next_action": "distribution_reaudit_projection_only",
        "conclusion": (
            "family_candidates_are_workflow_linked_but_not_main_admissible"
            if status == "PASS"
            else "family_candidate_admission_audit_needs_review"
        ),
    }


def render_report(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# v0.21.2 Workflow Admission Audit",
        "",
        f"- status: `{summary.get('status')}`",
        f"- audited_candidate_count: `{summary.get('audited_candidate_count')}`",
        f"- main_admissible_count: `{summary.get('main_admissible_count')}`",
        f"- blocked_from_main_benchmark_count: `{summary.get('blocked_from_main_benchmark_count')}`",
        f"- benchmark_admission_decision: `{summary.get('benchmark_admission_decision')}`",
        "",
        "## Blocking Reasons",
    ]
    for reason, count in (summary.get("blocking_reason_counts") or {}).items():
        lines.append(f"- `{reason}`: `{count}`")
    lines.extend(["", "## Audited Candidates"])
    for row in rows:
        lines.append(
            f"- `{row.get('family_candidate_id')}` `{row.get('bucket_id')}` "
            f"`{row.get('main_benchmark_status')}`"
        )
    return "\n".join(lines) + "\n"


def write_outputs(out_dir: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "audited_candidates.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "REPORT.md").write_text(render_report(summary, rows), encoding="utf-8")


def run_workflow_admission_audit(
    *,
    family_candidate_path: Path = DEFAULT_FAMILY_CANDIDATE_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    candidates = load_jsonl(family_candidate_path)
    audited = [audit_family_candidate(row) for row in candidates]
    summary = summarize_audit(audited)
    write_outputs(out_dir, audited, summary)
    return summary
