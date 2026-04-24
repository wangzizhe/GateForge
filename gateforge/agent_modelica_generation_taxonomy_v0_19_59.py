from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TAXONOMY_PATH = REPO_ROOT / "assets_private" / "error_taxonomy_v1.md"
DEFAULT_MAPPING_PATH = REPO_ROOT / "assets_private" / "error_taxonomy_mutation_mapping_v1.md"
DEFAULT_NL_TASK_POOL_DIR = REPO_ROOT / "assets_private" / "nl_task_pool_v1"
DEFAULT_OUT_PATH = REPO_ROOT / "artifacts" / "generation_taxonomy_v0_19_59" / "summary.json"

DEFAULT_TRAJECTORY_SOURCES = (
    REPO_ROOT / "artifacts" / "benchmark_trajectory_gf_v1" / "summary.json",
    REPO_ROOT / "artifacts" / "retrieval_trajectory_v0_19_58" / "hot" / "baseline-c5",
    REPO_ROOT / "artifacts" / "retrieval_trajectory_v0_19_58" / "hot" / "retrieval-c5",
    REPO_ROOT / "artifacts" / "retrieval_trajectory_v0_19_58" / "cold" / "baseline-c5",
    REPO_ROOT / "artifacts" / "retrieval_trajectory_v0_19_58" / "cold" / "retrieval-c5",
)


@dataclass(frozen=True)
class TaxonomyBucket:
    bucket_id: str
    name: str
    stage: str
    description: str
    typical_signal: str


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_taxonomy_markdown(path: Path) -> list[TaxonomyBucket]:
    text = path.read_text(encoding="utf-8")
    buckets: list[TaxonomyBucket] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("| ET"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 5:
            continue
        buckets.append(
            TaxonomyBucket(
                bucket_id=cells[0],
                name=cells[1],
                stage=cells[2],
                description=cells[3],
                typical_signal=cells[4],
            )
        )
    return buckets


def load_nl_tasks(pool_dir: Path) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for path in sorted(pool_dir.glob("*.json")):
        payload = load_json(path)
        if isinstance(payload, dict) and isinstance(payload.get("tasks"), list):
            tasks.extend([x for x in payload["tasks"] if isinstance(x, dict)])
        elif isinstance(payload, list):
            tasks.extend([x for x in payload if isinstance(x, dict)])
        elif isinstance(payload, dict):
            tasks.append(payload)
    return tasks


def _flatten_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(f"{key} {_flatten_text(val)}" for key, val in value.items())
    if isinstance(value, list):
        return " ".join(_flatten_text(item) for item in value)
    return str(value or "")


def _case_text(record: dict[str, Any]) -> str:
    selected = {
        "candidate_id": record.get("candidate_id") or record.get("task_id"),
        "benchmark_family": record.get("benchmark_family"),
        "mutation_mechanism": record.get("mutation_mechanism"),
        "failure_type": record.get("failure_type"),
        "observed_error_sequence": record.get("observed_error_sequence"),
        "final_status": record.get("final_status") or record.get("executor_status"),
        "model_name": record.get("model_name"),
        "mode": record.get("mode"),
    }
    return _flatten_text(selected).lower()


def classify_trajectory_record(record: dict[str, Any]) -> str:
    text = _case_text(record)
    if any(token in text for token in ("syntax", "parse_error", "parser error")):
        return "ET01"
    if any(token in text for token in ("class not found", "component not found", "missing class")):
        return "ET02"
    if any(token in text for token in ("array", "dimension", "index")):
        return "ET10"
    if any(token in text for token in ("unit", "type mismatch", "dimension mismatch")):
        return "ET11"
    if any(token in text for token in ("initial", "start value", "initialization")):
        return "ET12"
    if any(token in text for token in ("event", "discrete", "when", "sample")):
        return "ET13"
    if any(token in text for token in ("builtin", "operator", "function whitelist", "noevent", "homotopy")):
        return "ET14"
    if any(token in text for token in ("pp_", "parameter_promotion")) and any(
        token in text for token in ("pv_", "phantom", "compound", "triple")
    ):
        return "ET17"
    if any(token in text for token in ("compound_underdetermined", "pp+pv", "triple", "quad")):
        return "ET17"
    if any(token in text for token in ("phantom", "pv_", "dangling")):
        return "ET05"
    if any(token in text for token in ("parameter_promotion", "pp_", "modifier", "binding")):
        return "ET04"
    if any(token in text for token in ("undeclared", "not found in scope", "variable not found")):
        return "ET03"
    if any(token in text for token in ("underdet", "underdetermined", "missing_ground", "too few equations")):
        return "ET06"
    if any(token in text for token in ("overdet", "overdetermined", "redundant", "too many equations", "kvl", "kcl")):
        return "ET07"
    if any(token in text for token in ("shortcirc", "short_circuit", "connect", "topology")):
        return "ET08"
    if any(token in text for token in ("connector", "causality", "flow/non-flow")):
        return "ET09"
    if any(token in text for token in ("semantic", "time_constant", "physical", "sign", "direction")):
        return "ET15"
    if any(token in text for token in ("simulate_error", "runtime", "numeric", "singular")):
        return "ET16"
    return "UNCLASSIFIED"


def iter_trajectory_records(sources: Iterable[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for source in sources:
        if source.is_dir():
            for path in sorted(source.glob("*.json")):
                if path.name == "summary.json":
                    continue
                payload = load_json(path)
                if isinstance(payload, dict):
                    records.append(payload)
            continue
        if not source.exists():
            continue
        payload = load_json(source)
        if isinstance(payload, dict) and isinstance(payload.get("summaries"), list):
            records.extend([x for x in payload["summaries"] if isinstance(x, dict)])
        elif isinstance(payload, list):
            records.extend([x for x in payload if isinstance(x, dict)])
        elif isinstance(payload, dict):
            records.append(payload)
    return records


def parse_mapping_bucket_ids(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return set(re.findall(r"\|\s*(ET\d{2})\b", text))


def validate_generation_taxonomy(
    *,
    taxonomy_path: Path = DEFAULT_TAXONOMY_PATH,
    nl_task_pool_dir: Path = DEFAULT_NL_TASK_POOL_DIR,
    mapping_path: Path = DEFAULT_MAPPING_PATH,
    trajectory_sources: Iterable[Path] = DEFAULT_TRAJECTORY_SOURCES,
) -> dict[str, Any]:
    buckets = parse_taxonomy_markdown(taxonomy_path)
    bucket_ids = {bucket.bucket_id for bucket in buckets}
    tasks = load_nl_tasks(nl_task_pool_dir)
    domains = {str(task.get("domain") or "").strip() for task in tasks if str(task.get("domain") or "").strip()}
    difficulties = {str(task.get("difficulty") or "").strip() for task in tasks if str(task.get("difficulty") or "").strip()}
    mapping_ids = parse_mapping_bucket_ids(mapping_path)
    records = iter_trajectory_records(trajectory_sources)
    classified = []
    for record in records:
        bucket_id = classify_trajectory_record(record)
        classified.append(
            {
                "case_id": str(record.get("candidate_id") or record.get("task_id") or ""),
                "bucket_id": bucket_id,
            }
        )
    counts = Counter(item["bucket_id"] for item in classified)
    total_records = len(classified)
    unclassified_count = counts.get("UNCLASSIFIED", 0)
    unclassified_rate = 0.0 if total_records == 0 else unclassified_count / total_records
    required_difficulties = {"T1", "T2", "T3", "T4", "T5"}
    checks = {
        "taxonomy_bucket_count_ok": len(buckets) >= 15,
        "mapping_covers_taxonomy_ok": bucket_ids.issubset(mapping_ids),
        "nl_task_count_ok": len(tasks) >= 15,
        "nl_domain_coverage_ok": len(domains) >= 4,
        "nl_difficulty_coverage_ok": required_difficulties.issubset(difficulties),
        "trajectory_sample_count_ok": total_records >= 50,
        "trajectory_classification_coverage_ok": total_records > 0 and unclassified_count == 0,
        "unclassified_rate_ok": unclassified_rate <= 0.20,
    }
    return {
        "version": "v0.19.59",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "taxonomy_bucket_count": len(buckets),
        "taxonomy_bucket_ids": sorted(bucket_ids),
        "mapping_bucket_count": len(mapping_ids),
        "nl_task_count": len(tasks),
        "nl_domain_count": len(domains),
        "nl_domains": sorted(domains),
        "nl_difficulties": sorted(difficulties),
        "trajectory_sample_count": total_records,
        "classified_count": total_records - unclassified_count,
        "unclassified_count": unclassified_count,
        "unclassified_rate": round(unclassified_rate, 4),
        "bucket_counts": dict(sorted(counts.items())),
        "classified_cases": classified,
        "conclusion": (
            "taxonomy_and_nl_pool_frozen"
            if all(checks.values())
            else "taxonomy_or_nl_pool_validation_failed"
        ),
    }


def write_summary(payload: dict[str, Any], out_path: Path = DEFAULT_OUT_PATH) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out_path
