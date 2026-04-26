from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from gateforge.agent_modelica_substrate_seed_import_v0_25_0 import load_jsonl


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_IMPORTED_SEEDS_PATH = REPO_ROOT / "artifacts" / "substrate_seed_import_v0_25_0" / "substrate_seed_import.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "substrate_admission_v0_25_1"
ADMISSIBLE_IMPORT_STATUSES = {
    "promoted_family_prototype",
    "seed_only",
    "hard_negative",
}


def evaluate_admission(row: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if not row.get("source_model") or row.get("source_model") == "unknown":
        reasons.append("missing_source_model")
    if not row.get("artifact_references"):
        reasons.append("missing_artifact_references")
    if not str(row.get("omc_admission_status") or "").startswith("admitted"):
        reasons.append("not_omc_admitted")
    if not row.get("repeatability_class") or row.get("repeatability_class") == "unknown":
        reasons.append("not_repeatability_classified")
    if bool(row.get("routing_allowed")):
        reasons.append("routing_or_hint_dependency")
    if row.get("import_status") not in ADMISSIBLE_IMPORT_STATUSES:
        reasons.append("research_status_not_substrate_admissible")

    admitted = not reasons
    return {
        "seed_id": str(row.get("seed_id") or ""),
        "candidate_id": str(row.get("candidate_id") or row.get("seed_id") or ""),
        "mutation_family": str(row.get("mutation_family") or "unknown"),
        "source_backed": "missing_source_model" not in reasons,
        "workflow_proximal": True,
        "omc_admitted": "not_omc_admitted" not in reasons,
        "repeatability_classified": "not_repeatability_classified" not in reasons,
        "no_deterministic_hint_dependency": "routing_or_hint_dependency" not in reasons,
        "import_status": str(row.get("import_status") or "unknown"),
        "admission_status": "admitted" if admitted else "research_pool",
        "blocking_reasons": reasons,
    }


def build_substrate_admission(
    *,
    imported_seeds_path: Path = DEFAULT_IMPORTED_SEEDS_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    imported_rows = load_jsonl(imported_seeds_path)
    admission_rows = [evaluate_admission(row) for row in imported_rows]
    status_counts = Counter(row["admission_status"] for row in admission_rows)
    reason_counts = Counter(reason for row in admission_rows for reason in row["blocking_reasons"])
    missing_inputs = [] if imported_rows else ["imported_seeds"]
    status = "PASS" if admission_rows and not missing_inputs and status_counts.get("admitted", 0) else "REVIEW"
    summary = {
        "version": "v0.25.1",
        "status": status,
        "analysis_scope": "substrate_admission_gate",
        "seed_count": len(admission_rows),
        "missing_inputs": missing_inputs,
        "admission_status_counts": dict(sorted(status_counts.items())),
        "blocking_reason_counts": dict(sorted(reason_counts.items())),
        "admission_rules": [
            "source_backed",
            "workflow_proximal",
            "omc_admitted",
            "repeatability_classified",
            "no_deterministic_hint_dependency",
        ],
        "discipline": {
            "executor_changes": "none",
            "deterministic_repair_added": False,
            "hard_negative_can_be_admitted": True,
        },
        "conclusion": (
            "substrate_admission_gate_ready_for_split_freeze"
            if status == "PASS"
            else "substrate_admission_gate_needs_review"
        ),
    }
    write_outputs(out_dir=out_dir, admission_rows=admission_rows, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, admission_rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "substrate_admission.jsonl").open("w", encoding="utf-8") as fh:
        for row in admission_rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
