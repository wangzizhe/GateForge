from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GENERATION_SUMMARY_PATH = REPO_ROOT / "artifacts" / "generation_audit_v0_19_60" / "summary.json"
DEFAULT_CANDIDATE_PATH = REPO_ROOT / "artifacts" / "mutation_candidate_distill_v0_19_61" / "candidates.jsonl"
DEFAULT_TAXONOMY_SUMMARY_PATH = REPO_ROOT / "artifacts" / "generation_taxonomy_v0_19_59" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "distribution_alignment_plan_v0_21_0"

TARGET_BUCKETS = ("ET01", "ET02", "ET03")

FAMILY_PLAN_BY_BUCKET = {
    "ET01": {
        "candidate_family": "generation_parse_load_failure",
        "admission_focus": "source_viable_target_parse_or_load_failure",
    },
    "ET02": {
        "candidate_family": "missing_component_or_library_reference",
        "admission_focus": "source_viable_target_missing_reference_failure",
    },
    "ET03": {
        "candidate_family": "undeclared_identifier_from_generation",
        "admission_focus": "source_viable_target_unbound_identifier_failure",
    },
}

ADMISSION_RULES = {
    "source_viability_required": "clean source model must check before mutation",
    "target_failure_required": "mutated target must fail in the intended taxonomy bucket",
    "workflow_proximal_required": "task must remain a plausible natural-language Modelica workflow",
    "anti_fake_workflow_required": "bucket coverage must not define the task by itself",
    "isolation_first_required": "new families enter isolated pool before main benchmark",
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


def normalize_distribution(raw: dict[str, Any]) -> dict[str, float]:
    return {
        str(bucket_id): float(value)
        for bucket_id, value in (raw or {}).items()
        if str(bucket_id) and float(value) > 0
    }


def total_variation_distance(p_dist: dict[str, float], q_dist: dict[str, float]) -> float:
    buckets = set(p_dist) | set(q_dist)
    return 0.5 * sum(abs(float(p_dist.get(bucket, 0.0)) - float(q_dist.get(bucket, 0.0))) for bucket in buckets)


def candidate_counts_by_bucket(candidates: list[dict[str, Any]]) -> dict[str, int]:
    counter = Counter(str(row.get("bucket_id") or "") for row in candidates)
    return {bucket_id: counter[bucket_id] for bucket_id in sorted(counter) if bucket_id}


def build_gap_plan(
    *,
    p_dist: dict[str, float],
    q_dist: dict[str, float],
    candidate_counts: dict[str, int],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bucket_id in TARGET_BUCKETS:
        p_value = float(p_dist.get(bucket_id, 0.0))
        q_value = float(q_dist.get(bucket_id, 0.0))
        gap_mass = max(0.0, p_value - q_value)
        family_plan = FAMILY_PLAN_BY_BUCKET[bucket_id]
        rows.append(
            {
                "bucket_id": bucket_id,
                "generation_distribution_mass": round(p_value, 6),
                "mutation_distribution_mass": round(q_value, 6),
                "gap_mass": round(gap_mass, 6),
                "isolated_candidate_count": int(candidate_counts.get(bucket_id, 0)),
                "candidate_family": family_plan["candidate_family"],
                "admission_focus": family_plan["admission_focus"],
                "priority": "high" if gap_mass > 0 and candidate_counts.get(bucket_id, 0) > 0 else "review",
                "next_action": "build_isolated_family_pack",
            }
        )
    return sorted(rows, key=lambda row: (-float(row["gap_mass"]), str(row["bucket_id"])))


def build_alignment_plan(
    *,
    generation_summary: dict[str, Any],
    taxonomy_summary: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    p_dist = normalize_distribution(generation_summary.get("generation_failure_distribution_p") or {})
    q_dist = normalize_distribution(
        generation_summary.get("mutation_distribution_q") or taxonomy_summary.get("bucket_counts") or {}
    )
    if q_dist and any(value > 1.0 for value in q_dist.values()):
        total = sum(q_dist.values())
        q_dist = {bucket_id: value / total for bucket_id, value in q_dist.items()}
    candidate_counts = candidate_counts_by_bucket(candidates)
    gap_plan = build_gap_plan(p_dist=p_dist, q_dist=q_dist, candidate_counts=candidate_counts)
    target_candidate_count = sum(candidate_counts.get(bucket_id, 0) for bucket_id in TARGET_BUCKETS)
    target_gap_mass = round(sum(float(row["gap_mass"]) for row in gap_plan), 6)
    current_distance = round(total_variation_distance(p_dist, q_dist), 6)
    missing_targets = [
        row["bucket_id"]
        for row in gap_plan
        if int(row["isolated_candidate_count"]) == 0 or float(row["gap_mass"]) <= 0
    ]
    status = "PASS" if target_candidate_count > 0 and not missing_targets else "REVIEW"
    return {
        "version": "v0.21.0",
        "status": status,
        "current_distribution_distance": current_distance,
        "target_gap_mass": target_gap_mass,
        "target_buckets": list(TARGET_BUCKETS),
        "target_isolated_candidate_count": target_candidate_count,
        "candidate_counts_by_bucket": candidate_counts,
        "gap_plan": gap_plan,
        "admission_rules": dict(ADMISSION_RULES),
        "missing_or_unready_target_buckets": missing_targets,
        "next_version": "v0.21.1",
        "next_action": "build_early_compile_failure_family_candidates",
        "default_benchmark_admission": "isolated_pool_only",
        "conclusion": (
            "generation_distribution_alignment_plan_ready"
            if status == "PASS"
            else "generation_distribution_alignment_plan_needs_review"
        ),
    }


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# v0.21.0 Distribution Alignment Plan",
        "",
        f"- status: `{summary.get('status')}`",
        f"- current_distribution_distance: `{summary.get('current_distribution_distance')}`",
        f"- target_gap_mass: `{summary.get('target_gap_mass')}`",
        f"- target_isolated_candidate_count: `{summary.get('target_isolated_candidate_count')}`",
        f"- default_benchmark_admission: `{summary.get('default_benchmark_admission')}`",
        "",
        "## Gap Plan",
    ]
    for row in summary.get("gap_plan") or []:
        lines.append(
            f"- `{row.get('bucket_id')}` gap=`{row.get('gap_mass')}` "
            f"candidates=`{row.get('isolated_candidate_count')}` "
            f"family=`{row.get('candidate_family')}` priority=`{row.get('priority')}`"
        )
    lines.extend(["", "## Admission Rules"])
    for key, value in (summary.get("admission_rules") or {}).items():
        lines.append(f"- `{key}`: {value}")
    return "\n".join(lines) + "\n"


def write_outputs(out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "REPORT.md").write_text(render_report(summary), encoding="utf-8")


def run_distribution_alignment_plan(
    *,
    generation_summary_path: Path = DEFAULT_GENERATION_SUMMARY_PATH,
    taxonomy_summary_path: Path = DEFAULT_TAXONOMY_SUMMARY_PATH,
    candidate_path: Path = DEFAULT_CANDIDATE_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    generation_summary = load_json(generation_summary_path)
    taxonomy_summary = load_json(taxonomy_summary_path)
    candidates = load_jsonl(candidate_path)
    summary = build_alignment_plan(
        generation_summary=generation_summary,
        taxonomy_summary=taxonomy_summary,
        candidates=candidates,
    )
    write_outputs(out_dir, summary)
    return summary
