from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from gateforge.experiment_runner_shared import ALL_HARD_CASES, REPO_ROOT, load_case_info


DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "search_density_v0_20_0"
DEFAULT_SHADOW_CANDIDATES_PATH = (
    REPO_ROOT / "artifacts" / "mutation_candidate_distill_v0_19_61" / "candidates.jsonl"
)

DEFAULT_BROADENED_SOURCES = [
    {
        "path": REPO_ROOT / "artifacts" / "benchmark_v0_19_4" / "admitted_cases.jsonl",
        "difficulty_hint": "easy",
        "max_cases": 4,
    },
    {
        "path": REPO_ROOT / "artifacts" / "benchmark_v0_19_5" / "admitted_cases.jsonl",
        "difficulty_hint": "easy",
        "max_cases": 4,
    },
    {
        "path": REPO_ROOT / "artifacts" / "underdetermined_mutations_v0_19_12" / "admitted_cases.jsonl",
        "difficulty_hint": "medium",
        "max_cases": 6,
    },
    {
        "path": REPO_ROOT / "artifacts" / "overdetermined_mutations_v0_19_11" / "admitted_cases.jsonl",
        "difficulty_hint": "medium",
        "max_cases": 6,
    },
    {
        "path": REPO_ROOT / "artifacts" / "non_ground_connect_deletion_mutations_v0_19_26" / "admitted_cases.jsonl",
        "difficulty_hint": "medium",
        "max_cases": 5,
    },
    {
        "path": REPO_ROOT / "artifacts" / "component_instance_deletion_mutations_v0_19_27" / "admitted_cases.jsonl",
        "difficulty_hint": "medium",
        "max_cases": 5,
    },
    {
        "path": REPO_ROOT / "artifacts" / "compound_underdetermined_experiment_v0_19_38" / "admitted_cases.jsonl",
        "difficulty_hint": "hard",
        "max_cases": 8,
    },
    {
        "path": REPO_ROOT / "artifacts" / "triple_underdetermined_experiment_v0_19_45_pp_pv_pv" / "admitted_cases.jsonl",
        "difficulty_hint": "hard",
        "max_cases": 8,
    },
]

METRIC_SCHEMA = [
    "clean_pass_rate",
    "correct_candidate_density",
    "coverage_at_n",
    "average_candidate_count",
    "average_candidate_cost",
    "cost_per_pass",
    "omc_ranker_top1_hit_rate",
    "omc_ranker_top3_hit_rate",
    "repeated_no_progress_rate",
    "regression_count_vs_fixed_c5",
]

BASELINE_ARMS = [
    {
        "arm": "raw-single",
        "description": "single candidate with raw OMC feedback",
        "scored": True,
    },
    {
        "arm": "fixed-c5",
        "description": "v0.19.x deployable baseline: multi-candidate sampling plus OMC residual ranker",
        "scored": True,
    },
    {
        "arm": "oracle-existing-best",
        "description": "analysis-only best-known historical result upper bound",
        "scored": False,
    },
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _first_non_empty(row: dict[str, Any], keys: Iterable[str], default: str = "") -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return default


def normalize_case(
    row: dict[str, Any],
    *,
    set_name: str,
    source_path: Path | None = None,
    difficulty_hint: str = "",
    scoring_role: str = "main",
) -> dict[str, Any]:
    candidate_id = _first_non_empty(row, ["candidate_id", "task_id", "source_task_id"])
    return {
        "candidate_id": candidate_id,
        "task_id": _first_non_empty(row, ["task_id", "source_task_id"], candidate_id),
        "set_name": set_name,
        "scoring_role": scoring_role,
        "source_artifact": str(source_path) if source_path else "",
        "difficulty_hint": _first_non_empty(row, ["difficulty_prior", "difficulty"], difficulty_hint),
        "benchmark_family": _first_non_empty(
            row,
            ["benchmark_family", "mutation_family", "mutation_type", "proposed_mutation_family"],
            "unknown",
        ),
        "failure_type": _first_non_empty(row, ["failure_type", "bucket_id"], "unknown"),
        "expected_stage": _first_non_empty(row, ["expected_stage"], "unknown"),
        "model_name": _first_non_empty(row, ["model_name", "source_model_name"], "unknown"),
        "workflow_goal_present": bool(str(row.get("workflow_goal") or "").strip()),
    }


def build_continuity_set(case_ids: Iterable[str] = ALL_HARD_CASES) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate_id in case_ids:
        try:
            case_info = load_case_info(candidate_id)
        except FileNotFoundError:
            case_info = {"candidate_id": candidate_id}
        rows.append(
            normalize_case(
                case_info,
                set_name="continuity",
                difficulty_hint="hard",
                scoring_role="main",
            )
        )
    return rows


def build_broadened_repair_set(
    sources: Iterable[dict[str, Any]] = DEFAULT_BROADENED_SOURCES,
    *,
    target_max_cases: int = 40,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in sources:
        path = Path(source["path"])
        difficulty_hint = str(source.get("difficulty_hint") or "")
        max_cases = int(source.get("max_cases") or 0)
        source_rows = load_jsonl(path)
        for row in source_rows[:max_cases]:
            normalized = normalize_case(
                row,
                set_name="broadened_repair",
                source_path=path,
                difficulty_hint=difficulty_hint,
                scoring_role="main",
            )
            candidate_id = normalized["candidate_id"]
            if not candidate_id or candidate_id in seen:
                continue
            seen.add(candidate_id)
            rows.append(normalized)
            if len(rows) >= target_max_cases:
                return rows
    return rows


def build_shadow_generation_set(path: Path = DEFAULT_SHADOW_CANDIDATES_PATH) -> list[dict[str, Any]]:
    rows = []
    for row in load_jsonl(path):
        normalized = normalize_case(
            row,
            set_name="shadow_generation_derived",
            source_path=path,
            difficulty_hint=str(row.get("difficulty") or ""),
            scoring_role="shadow_only",
        )
        normalized["bucket_id"] = str(row.get("bucket_id") or "")
        normalized["priority_bucket"] = str(row.get("priority_bucket") or "")
        rows.append(normalized)
    return rows


def summarize_substrate(case_sets: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    all_rows = [row for rows in case_sets.values() for row in rows]
    by_set = {name: len(rows) for name, rows in case_sets.items()}
    by_scoring_role = Counter(row["scoring_role"] for row in all_rows)
    by_difficulty = Counter(row["difficulty_hint"] or "unknown" for row in all_rows)
    by_family = Counter(row["benchmark_family"] or "unknown" for row in all_rows)
    main_case_count = sum(1 for row in all_rows if row["scoring_role"] == "main")
    shadow_case_count = sum(1 for row in all_rows if row["scoring_role"] == "shadow_only")
    return {
        "version": "v0.20.0",
        "status": "PASS" if main_case_count >= 20 and shadow_case_count >= 1 else "INCOMPLETE",
        "case_count": len(all_rows),
        "main_case_count": main_case_count,
        "shadow_case_count": shadow_case_count,
        "set_counts": by_set,
        "scoring_role_counts": dict(sorted(by_scoring_role.items())),
        "difficulty_counts": dict(sorted(by_difficulty.items())),
        "top_family_counts": dict(by_family.most_common(12)),
        "baseline_arms": BASELINE_ARMS,
        "metric_schema": METRIC_SCHEMA,
        "promotion_discipline": {
            "continuity_set": "main_scored_alignment_with_v0_19_x",
            "broadened_repair_set": "main_scored_overfit_guard",
            "shadow_generation_derived_set": "shadow_only_not_used_for_v0_20_pass_rate",
        },
        "conclusion": (
            "search_density_v2_substrate_ready"
            if main_case_count >= 20 and shadow_case_count >= 1
            else "search_density_v2_substrate_incomplete"
        ),
    }


def build_search_density_substrate(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    broadened_target_max_cases: int = 40,
) -> dict[str, Any]:
    case_sets = {
        "continuity": build_continuity_set(),
        "broadened_repair": build_broadened_repair_set(target_max_cases=broadened_target_max_cases),
        "shadow_generation_derived": build_shadow_generation_set(),
    }
    substrate = {
        "version": "v0.20.0",
        "case_sets": case_sets,
        "summary": summarize_substrate(case_sets),
    }
    write_search_density_substrate(out_dir=out_dir, substrate=substrate)
    return substrate


def write_search_density_substrate(*, out_dir: Path, substrate: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "substrate.json").write_text(
        json.dumps(substrate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "summary.json").write_text(
        json.dumps(substrate["summary"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
