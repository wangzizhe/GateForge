from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SEED_REGISTRY_PATH = REPO_ROOT / "artifacts" / "seed_registry_v0_23_1" / "seed_registry.jsonl"
DEFAULT_CANDIDATE_REPEATABILITY_PATH = (
    REPO_ROOT / "artifacts" / "repeatability_protocol_v0_24_0" / "candidate_repeatability.jsonl"
)
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "substrate_seed_import_v0_25_0"


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


def classify_import_status(seed: dict[str, Any], repeatability: dict[str, Any]) -> str:
    registry_policy = str(seed.get("registry_policy") or "")
    repeatability_class = str(repeatability.get("repeatability_class") or seed.get("repeatability_class") or "")
    if registry_policy == "benchmark_positive_candidate" and repeatability_class == "stable_true_multi":
        return "promoted_family_prototype"
    if registry_policy == "seed_only_positive_candidate" and repeatability_class == "stable_true_multi":
        return "seed_only"
    if registry_policy == "hard_negative_candidate" or repeatability_class == "stable_dead_end":
        return "hard_negative"
    if registry_policy == "research_unstable_candidate" or repeatability_class == "unstable_true_multi":
        return "research_pool"
    return "rejected_or_review"


def build_import_rows(
    *,
    seeds: list[dict[str, Any]],
    candidate_repeatability: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    repeatability_by_id = {str(row.get("candidate_id") or ""): row for row in candidate_repeatability}
    rows: list[dict[str, Any]] = []
    for seed in sorted(seeds, key=lambda row: str(row.get("seed_id") or row.get("candidate_id") or "")):
        seed_id = str(seed.get("seed_id") or seed.get("candidate_id") or "")
        repeatability = repeatability_by_id.get(seed_id, {})
        import_status = classify_import_status(seed, repeatability)
        rows.append(
            {
                "seed_id": seed_id,
                "candidate_id": seed_id,
                "source_model": str(seed.get("source_model") or "unknown"),
                "mutation_family": str(seed.get("mutation_family") or "unknown"),
                "source_complexity_class": str(seed.get("source_complexity_class") or "unknown"),
                "registry_policy": str(seed.get("registry_policy") or "unknown"),
                "repeatability_class": str(repeatability.get("repeatability_class") or seed.get("repeatability_class") or "unknown"),
                "observation_count": int(repeatability.get("observation_count") or seed.get("observation_count") or 0),
                "artifact_references": list(seed.get("artifact_references") or []),
                "omc_admission_status": str(seed.get("omc_admission_status") or "unknown"),
                "import_status": import_status,
                "import_reason": "status_derived_from_seed_registry_and_repeatability_gate",
                "routing_allowed": False,
            }
        )
    return rows


def build_substrate_seed_import(
    *,
    seed_registry_path: Path = DEFAULT_SEED_REGISTRY_PATH,
    candidate_repeatability_path: Path = DEFAULT_CANDIDATE_REPEATABILITY_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    seeds = load_jsonl(seed_registry_path)
    candidate_repeatability = load_jsonl(candidate_repeatability_path)
    imported_rows = build_import_rows(seeds=seeds, candidate_repeatability=candidate_repeatability)
    status_counts = Counter(row["import_status"] for row in imported_rows)
    missing_inputs = []
    if not seeds:
        missing_inputs.append("seed_registry")
    if not candidate_repeatability:
        missing_inputs.append("candidate_repeatability")
    missing_artifacts = [row["seed_id"] for row in imported_rows if not row["artifact_references"]]
    status = "PASS" if imported_rows and not missing_inputs and not missing_artifacts else "REVIEW"
    summary = {
        "version": "v0.25.0",
        "status": status,
        "analysis_scope": "substrate_seed_import",
        "seed_count": len(imported_rows),
        "missing_inputs": missing_inputs,
        "missing_artifact_reference_count": len(missing_artifacts),
        "import_status_counts": dict(sorted(status_counts.items())),
        "discipline": {
            "executor_changes": "none",
            "deterministic_repair_added": False,
            "status_source": "repeatability_gate_not_manual_preference",
            "routing_allowed": False,
        },
        "conclusion": (
            "v0_22_seed_results_imported_for_substrate_admission"
            if status == "PASS"
            else "substrate_seed_import_needs_review"
        ),
    }
    write_outputs(out_dir=out_dir, imported_rows=imported_rows, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, imported_rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "substrate_seed_import.jsonl").open("w", encoding="utf-8") as fh:
        for row in imported_rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
