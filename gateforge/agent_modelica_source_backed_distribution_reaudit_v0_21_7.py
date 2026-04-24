from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GENERATION_SUMMARY_PATH = REPO_ROOT / "artifacts" / "generation_audit_v0_19_60" / "summary.json"
DEFAULT_TAXONOMY_SUMMARY_PATH = REPO_ROOT / "artifacts" / "generation_taxonomy_v0_19_59" / "summary.json"
DEFAULT_TARGET_ADMISSION_PATH = (
    REPO_ROOT / "artifacts" / "source_backed_target_admission_v0_21_6" / "target_admission.jsonl"
)
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "source_backed_distribution_reaudit_v0_21_7"


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


def admitted_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counter = Counter(
        str(row.get("bucket_id") or "")
        for row in rows
        if row.get("benchmark_admission_status") == "main_admissible_source_target_pair"
    )
    return {bucket: counter[bucket] for bucket in sorted(counter) if bucket}


def build_source_backed_distribution_reaudit(
    *,
    generation_summary: dict[str, Any],
    taxonomy_summary: dict[str, Any],
    target_admission_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    p_dist = {
        str(bucket): float(value)
        for bucket, value in (generation_summary.get("generation_failure_distribution_p") or {}).items()
    }
    base_counts = {
        str(bucket): float(value)
        for bucket, value in (taxonomy_summary.get("bucket_counts") or {}).items()
    }
    added_counts = admitted_counts(target_admission_rows)
    updated_counts = dict(base_counts)
    for bucket, count in added_counts.items():
        updated_counts[bucket] = updated_counts.get(bucket, 0.0) + float(count)
    old_q = normalize_counts(base_counts)
    new_q = normalize_counts(updated_counts)
    old_distance = round(total_variation_distance(p_dist, old_q), 6)
    new_distance = round(total_variation_distance(p_dist, new_q), 6)
    delta = round(new_distance - old_distance, 6)
    status = "PASS" if added_counts and new_distance < old_distance else "REVIEW"
    return {
        "version": "v0.21.7",
        "status": status,
        "generation_distribution_p": p_dist,
        "previous_mutation_distribution_q": old_q,
        "updated_mutation_distribution_q": new_q,
        "previous_distance": old_distance,
        "updated_distance": new_distance,
        "distance_delta": delta,
        "base_mutation_bucket_counts": base_counts,
        "admitted_source_backed_bucket_counts": added_counts,
        "updated_mutation_bucket_counts": updated_counts,
        "main_admissible_count": sum(added_counts.values()),
        "conclusion": (
            "source_backed_distribution_alignment_improved"
            if status == "PASS"
            else "source_backed_distribution_alignment_needs_review"
        ),
        "next_action": "phase_closeout_or_promote_isolated_pack",
    }


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# v0.21.7 Source-Backed Distribution Re-Audit",
        "",
        f"- status: `{summary.get('status')}`",
        f"- previous_distance: `{summary.get('previous_distance')}`",
        f"- updated_distance: `{summary.get('updated_distance')}`",
        f"- distance_delta: `{summary.get('distance_delta')}`",
        f"- main_admissible_count: `{summary.get('main_admissible_count')}`",
        "",
        "## Added Counts",
    ]
    for bucket, count in (summary.get("admitted_source_backed_bucket_counts") or {}).items():
        lines.append(f"- `{bucket}`: `{count}`")
    return "\n".join(lines) + "\n"


def write_outputs(out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "REPORT.md").write_text(render_report(summary), encoding="utf-8")


def run_source_backed_distribution_reaudit(
    *,
    generation_summary_path: Path = DEFAULT_GENERATION_SUMMARY_PATH,
    taxonomy_summary_path: Path = DEFAULT_TAXONOMY_SUMMARY_PATH,
    target_admission_path: Path = DEFAULT_TARGET_ADMISSION_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_source_backed_distribution_reaudit(
        generation_summary=load_json(generation_summary_path),
        taxonomy_summary=load_json(taxonomy_summary_path),
        target_admission_rows=load_jsonl(target_admission_path),
    )
    write_outputs(out_dir, summary)
    return summary
