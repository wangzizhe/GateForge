from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_benchmark_blind_gate_v0_36_4 import lint_benchmark_blindness
from .agent_modelica_hard_family_registry_v0_37_0 import validate_registry_seed


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hard_pool_gate_v0_37_2"

ADMITTED_STATUSES = {"admitted", "admitted_via_live_failure", "pass", "PASS"}
REPEATABLE_STATUSES = {"repeatable", "repeatable_candidate", "pass", "PASS"}


def evaluate_seed_gate(seed: dict[str, Any]) -> dict[str, Any]:
    errors = validate_registry_seed(seed)
    blind = lint_benchmark_blindness(
        {
            "case_id": seed.get("case_id"),
            "description": seed.get("visible_task_description"),
            "constraints": seed.get("visible_constraints") or [],
        }
    )
    source_backed = bool(seed.get("source_backed"))
    model_check_first = bool(seed.get("model_check_first"))
    admitted = str(seed.get("admission_status") or "") in ADMITTED_STATUSES
    repeatable = str(seed.get("repeatability_status") or "") in REPEATABLE_STATUSES
    has_oracle = isinstance(seed.get("hidden_oracle"), dict) and bool(seed.get("hidden_oracle"))
    blockers: list[str] = []
    if errors:
        blockers.append("registry_schema_invalid")
    if blind["status"] != "PASS":
        blockers.append("prompt_leakage")
    if not source_backed:
        blockers.append("not_source_backed")
    if not model_check_first:
        blockers.append("not_model_check_first")
    if not admitted:
        blockers.append("not_admitted")
    if not has_oracle:
        blockers.append("missing_hidden_oracle")
    registry_status = "admitted" if not blockers else "candidate"
    if not blockers and repeatable:
        registry_status = "repeatable_candidate"
    return {
        "case_id": str(seed.get("case_id") or ""),
        "family": str(seed.get("family") or ""),
        "status": "PASS" if not blockers else "REVIEW",
        "registry_status": registry_status,
        "formal_benchmark_eligible": not blockers and repeatable,
        "blockers": blockers,
        "schema_errors": errors,
        "blind_lint_status": blind["status"],
        "blind_lint_hits": blind["hits"],
        "known_hard_for": list(seed.get("known_hard_for") or []),
    }


def build_hard_pool_gate_summary(
    seeds: list[dict[str, Any]],
    *,
    version: str = "v0.37.2",
) -> dict[str, Any]:
    rows = [evaluate_seed_gate(seed) for seed in seeds]
    blocker_counts: dict[str, int] = {}
    for row in rows:
        for blocker in row["blockers"]:
            blocker_counts[blocker] = blocker_counts.get(blocker, 0) + 1
    eligible = [row for row in rows if row["formal_benchmark_eligible"]]
    admitted = [row for row in rows if row["status"] == "PASS"]
    return {
        "version": version,
        "analysis_scope": "hard_pool_gate",
        "status": "PASS" if admitted else "REVIEW",
        "seed_count": len(seeds),
        "admitted_count": len(admitted),
        "formal_benchmark_eligible_count": len(eligible),
        "known_hard_seed_count": sum(1 for row in rows if row["known_hard_for"]),
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "results": rows,
    }


def write_hard_pool_gate_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
