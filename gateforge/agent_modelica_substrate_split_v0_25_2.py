from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from gateforge.agent_modelica_substrate_seed_import_v0_25_0 import load_jsonl


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_IMPORT_PATH = REPO_ROOT / "artifacts" / "substrate_seed_import_v0_25_0" / "substrate_seed_import.jsonl"
DEFAULT_ADMISSION_PATH = REPO_ROOT / "artifacts" / "substrate_admission_v0_25_1" / "substrate_admission.jsonl"
DEFAULT_SMOKE_PATH = REPO_ROOT / "artifacts" / "golden_smoke_pack_v0_24_4" / "seed_registry.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "substrate_split_v0_25_2"


def choose_holdout_ids(imported_rows: list[dict[str, Any]], admitted_ids: set[str]) -> set[str]:
    holdout: set[str] = set()
    families: dict[str, list[dict[str, Any]]] = {}
    for row in imported_rows:
        if row["seed_id"] in admitted_ids and row.get("import_status") == "promoted_family_prototype":
            families.setdefault(str(row.get("mutation_family") or "unknown"), []).append(row)
    for rows in families.values():
        sorted_rows = sorted(rows, key=lambda item: str(item.get("seed_id") or ""))
        if len(sorted_rows) >= 3:
            holdout.add(str(sorted_rows[-1]["seed_id"]))
    return holdout


def assign_split(row: dict[str, Any], *, admitted_ids: set[str], holdout_ids: set[str]) -> str:
    seed_id = str(row.get("seed_id") or "")
    if seed_id not in admitted_ids:
        return "research_pool"
    if seed_id in holdout_ids:
        return "holdout"
    if row.get("import_status") == "hard_negative":
        return "hard_negative"
    if row.get("import_status") in {"promoted_family_prototype", "seed_only"}:
        return "positive"
    return "research_pool"


def build_substrate_split(
    *,
    import_path: Path = DEFAULT_IMPORT_PATH,
    admission_path: Path = DEFAULT_ADMISSION_PATH,
    smoke_path: Path = DEFAULT_SMOKE_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    imported_rows = load_jsonl(import_path)
    admission_rows = load_jsonl(admission_path)
    smoke_rows = load_jsonl(smoke_path)
    admitted_ids = {str(row.get("seed_id") or "") for row in admission_rows if row.get("admission_status") == "admitted"}
    holdout_ids = choose_holdout_ids(imported_rows, admitted_ids)
    split_rows = []
    for row in imported_rows:
        split = assign_split(row, admitted_ids=admitted_ids, holdout_ids=holdout_ids)
        split_rows.append(
            {
                "seed_id": str(row.get("seed_id") or ""),
                "candidate_id": str(row.get("candidate_id") or row.get("seed_id") or ""),
                "mutation_family": str(row.get("mutation_family") or "unknown"),
                "import_status": str(row.get("import_status") or "unknown"),
                "repeatability_class": str(row.get("repeatability_class") or "unknown"),
                "split": split,
                "split_reason": "holdout_by_family" if split == "holdout" else f"derived_from_{row.get('import_status')}",
                "artifact_references": list(row.get("artifact_references") or []),
                "routing_allowed": False,
            }
        )
    for smoke in smoke_rows:
        split_rows.append(
            {
                "seed_id": str(smoke.get("seed_id") or ""),
                "candidate_id": str(smoke.get("candidate_id") or smoke.get("seed_id") or ""),
                "mutation_family": str(smoke.get("mutation_family") or "smoke_family"),
                "import_status": "smoke_fixture",
                "repeatability_class": str(smoke.get("repeatability_class") or "fixture"),
                "split": "smoke",
                "split_reason": "golden_smoke_pack_fixture",
                "artifact_references": ["artifacts/golden_smoke_pack_v0_24_4/seed_registry.jsonl"],
                "routing_allowed": False,
            }
        )
    split_counts = Counter(row["split"] for row in split_rows)
    missing_inputs = []
    if not imported_rows:
        missing_inputs.append("imported_seeds")
    if not admission_rows:
        missing_inputs.append("admission")
    if not smoke_rows:
        missing_inputs.append("smoke_pack")
    status = "PASS" if not missing_inputs and split_counts.get("positive", 0) and split_counts.get("hard_negative", 0) and split_counts.get("smoke", 0) else "REVIEW"
    summary = {
        "version": "v0.25.2",
        "status": status,
        "analysis_scope": "substrate_split",
        "row_count": len(split_rows),
        "missing_inputs": missing_inputs,
        "split_counts": dict(sorted(split_counts.items())),
        "holdout_seed_ids": sorted(holdout_ids),
        "discipline": {
            "executor_changes": "none",
            "deterministic_repair_added": False,
            "hard_negative_preserved": True,
            "smoke_separate_from_full_substrate": True,
            "holdout_not_for_tuning": True,
        },
        "conclusion": (
            "substrate_split_ready_for_manifest_freeze"
            if status == "PASS"
            else "substrate_split_needs_review"
        ),
    }
    write_outputs(out_dir=out_dir, split_rows=split_rows, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, split_rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "substrate_split.jsonl").open("w", encoding="utf-8") as fh:
        for row in split_rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
