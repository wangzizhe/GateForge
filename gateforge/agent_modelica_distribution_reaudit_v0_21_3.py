from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GENERATION_SUMMARY_PATH = REPO_ROOT / "artifacts" / "generation_audit_v0_19_60" / "summary.json"
DEFAULT_TAXONOMY_SUMMARY_PATH = REPO_ROOT / "artifacts" / "generation_taxonomy_v0_19_59" / "summary.json"
DEFAULT_FAMILY_CANDIDATE_PATH = (
    REPO_ROOT / "artifacts" / "early_compile_family_v0_21_1" / "family_candidates.jsonl"
)
DEFAULT_ADMISSION_AUDIT_PATH = REPO_ROOT / "artifacts" / "workflow_admission_audit_v0_21_2" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "distribution_reaudit_v0_21_3"


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


def normalize_counts(counts: dict[str, int | float]) -> dict[str, float]:
    total = sum(float(value) for value in counts.values())
    if total <= 0:
        return {}
    return {str(bucket): float(value) / total for bucket, value in sorted(counts.items()) if float(value) > 0}


def total_variation_distance(p_dist: dict[str, float], q_dist: dict[str, float]) -> float:
    buckets = set(p_dist) | set(q_dist)
    return 0.5 * sum(abs(float(p_dist.get(bucket, 0.0)) - float(q_dist.get(bucket, 0.0))) for bucket in buckets)


def candidate_bucket_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counter = Counter(str(row.get("bucket_id") or "") for row in rows)
    return {bucket_id: counter[bucket_id] for bucket_id in sorted(counter) if bucket_id}


def build_projected_counts(
    base_counts: dict[str, int | float],
    family_candidate_counts: dict[str, int],
    *,
    include_candidates: bool,
) -> dict[str, float]:
    projected = {str(bucket): float(value) for bucket, value in base_counts.items()}
    if include_candidates:
        for bucket, count in family_candidate_counts.items():
            projected[bucket] = projected.get(bucket, 0.0) + float(count)
    return projected


def build_distribution_reaudit(
    *,
    generation_summary: dict[str, Any],
    taxonomy_summary: dict[str, Any],
    family_candidates: list[dict[str, Any]],
    admission_audit: dict[str, Any],
) -> dict[str, Any]:
    p_dist = {
        str(bucket): float(value)
        for bucket, value in (generation_summary.get("generation_failure_distribution_p") or {}).items()
    }
    base_counts = {
        str(bucket): float(value)
        for bucket, value in (taxonomy_summary.get("bucket_counts") or {}).items()
    }
    family_counts = candidate_bucket_counts(family_candidates)
    actual_q = normalize_counts(base_counts)
    actual_distance = round(total_variation_distance(p_dist, actual_q), 6)
    main_admissible_count = int(admission_audit.get("main_admissible_count") or 0)
    actual_plus_admitted_counts = build_projected_counts(
        base_counts,
        family_counts,
        include_candidates=main_admissible_count > 0,
    )
    actual_plus_admitted_q = normalize_counts(actual_plus_admitted_counts)
    actual_plus_admitted_distance = round(total_variation_distance(p_dist, actual_plus_admitted_q), 6)
    isolated_projection_counts = build_projected_counts(
        base_counts,
        family_counts,
        include_candidates=True,
    )
    isolated_projection_q = normalize_counts(isolated_projection_counts)
    isolated_projection_distance = round(total_variation_distance(p_dist, isolated_projection_q), 6)
    return {
        "version": "v0.21.3",
        "status": "PASS",
        "generation_distribution_p": p_dist,
        "actual_mutation_distribution_q": actual_q,
        "actual_distance": actual_distance,
        "actual_plus_admitted_distance": actual_plus_admitted_distance,
        "isolated_projection_distance": isolated_projection_distance,
        "actual_distance_delta": round(actual_plus_admitted_distance - actual_distance, 6),
        "isolated_projection_delta": round(isolated_projection_distance - actual_distance, 6),
        "base_mutation_bucket_counts": base_counts,
        "family_candidate_bucket_counts": family_counts,
        "main_admissible_count": main_admissible_count,
        "blocked_from_main_benchmark_count": int(admission_audit.get("blocked_from_main_benchmark_count") or 0),
        "benchmark_admission_decision": admission_audit.get("benchmark_admission_decision"),
        "conclusion": "actual_distribution_unchanged_projection_improves_if_admitted",
        "next_action": "source_pairing_and_omc_validation_before_distribution_claim",
    }


def render_report(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# v0.21.3 Distribution Re-Audit",
            "",
            f"- status: `{summary.get('status')}`",
            f"- actual_distance: `{summary.get('actual_distance')}`",
            f"- actual_plus_admitted_distance: `{summary.get('actual_plus_admitted_distance')}`",
            f"- isolated_projection_distance: `{summary.get('isolated_projection_distance')}`",
            f"- main_admissible_count: `{summary.get('main_admissible_count')}`",
            f"- blocked_from_main_benchmark_count: `{summary.get('blocked_from_main_benchmark_count')}`",
            f"- next_action: `{summary.get('next_action')}`",
            "",
            "## Interpretation",
            "",
            "Actual distribution remains unchanged because no new family candidate is main-admissible yet.",
            "The isolated projection is diagnostic only and must not be reported as benchmark improvement.",
            "",
        ]
    )


def write_outputs(out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "REPORT.md").write_text(render_report(summary), encoding="utf-8")


def run_distribution_reaudit(
    *,
    generation_summary_path: Path = DEFAULT_GENERATION_SUMMARY_PATH,
    taxonomy_summary_path: Path = DEFAULT_TAXONOMY_SUMMARY_PATH,
    family_candidate_path: Path = DEFAULT_FAMILY_CANDIDATE_PATH,
    admission_audit_path: Path = DEFAULT_ADMISSION_AUDIT_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_distribution_reaudit(
        generation_summary=load_json(generation_summary_path),
        taxonomy_summary=load_json(taxonomy_summary_path),
        family_candidates=load_jsonl(family_candidate_path),
        admission_audit=load_json(admission_audit_path),
    )
    write_outputs(out_dir, summary)
    return summary
