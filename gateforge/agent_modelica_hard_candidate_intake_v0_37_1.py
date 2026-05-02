from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .agent_modelica_hard_family_registry_v0_37_0 import validate_registry_seed


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hard_candidate_intake_v0_37_1"

FAMILY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("arrayed_connector_flow", re.compile(r"(array|bus|probe|adapter|flow|connector)", re.IGNORECASE)),
    ("replaceable_partial_contract", re.compile(r"(replaceable|partial|constrainedby|redeclare)", re.IGNORECASE)),
    ("reusable_contract_adapter", re.compile(r"(reusable|contract|adapter|probe|monitor)", re.IGNORECASE)),
    ("inheritance_redeclare_structure", re.compile(r"(extends|inherit|redeclare)", re.IGNORECASE)),
    ("conditional_parameter_structure", re.compile(r"(conditional|parameter|if|switch)", re.IGNORECASE)),
)


def infer_family(task: dict[str, Any]) -> str:
    text = "\n".join(
        [
            str(task.get("case_id") or ""),
            str(task.get("title") or ""),
            str(task.get("description") or ""),
            "\n".join(str(item) for item in task.get("constraints") or []),
            str(task.get("initial_model") or ""),
        ]
    )
    for family, pattern in FAMILY_PATTERNS:
        if pattern.search(text):
            return family
    return "general_model_check_structural"


def task_to_registry_seed(
    task: dict[str, Any],
    *,
    source_reference: str = "",
    known_hard_for: list[str] | None = None,
) -> dict[str, Any]:
    verification = task.get("verification") if isinstance(task.get("verification"), dict) else {}
    model_check_first = str(task.get("benchmark_focus") or "") == "model_check_structural"
    if not model_check_first:
        model_check_first = bool(verification.get("check_model"))
    description = str(task.get("description") or "")
    constraints = task.get("constraints") if isinstance(task.get("constraints"), list) else []
    visible_description = "\n".join([description, *[str(item) for item in constraints]]).strip()
    hidden_oracle = task.get("hidden_oracle") if isinstance(task.get("hidden_oracle"), dict) else {}
    if not hidden_oracle:
        hidden_oracle = {
            "type": "verification_contract",
            "check_model": bool(verification.get("check_model")),
            "simulate": isinstance(verification.get("simulate"), dict),
            "behavioral": isinstance(verification.get("behavioral"), dict),
        }
    return {
        "case_id": str(task.get("case_id") or ""),
        "family": str(task.get("family") or infer_family(task)),
        "source_reference": source_reference or str(task.get("source_reference") or task.get("case_id") or ""),
        "source_backed": bool(task.get("source_backed")),
        "workflow_intent": str(task.get("workflow_intent") or task.get("title") or task.get("description") or ""),
        "visible_task_description": visible_description,
        "hidden_oracle": hidden_oracle,
        "mutation_intent": str(task.get("mutation_intent") or task.get("title") or ""),
        "expected_failure_mode": str(
            task.get("expected_failure_mode")
            or task.get("benchmark_focus")
            or ("model_check_structural" if model_check_first else "unknown")
        ),
        "model_check_first": bool(model_check_first),
        "blind_lint_status": str(task.get("blind_lint_status") or "not_run"),
        "admission_status": str(task.get("admission_status") or "not_run"),
        "repeatability_status": str(task.get("repeatability_status") or "not_run"),
        "evidence_role": str(task.get("evidence_role") or "debug"),
        "known_hard_for": list(known_hard_for or task.get("known_hard_for") or []),
        "registry_status": str(task.get("registry_status") or "candidate"),
    }


def build_candidate_intake_summary(
    tasks: list[dict[str, Any]],
    *,
    known_hard_by_case: dict[str, list[str]] | None = None,
    version: str = "v0.37.1",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    hard_map = known_hard_by_case or {}
    seeds = [
        task_to_registry_seed(
            task,
            known_hard_for=hard_map.get(str(task.get("case_id") or ""), []),
        )
        for task in tasks
    ]
    validation_errors: dict[str, list[str]] = {}
    family_counts: dict[str, int] = {}
    for seed in seeds:
        case_id = str(seed.get("case_id") or "unknown")
        errors = validate_registry_seed(seed)
        if errors:
            validation_errors[case_id] = errors
        family = str(seed.get("family") or "unknown")
        family_counts[family] = family_counts.get(family, 0) + 1
    summary = {
        "version": version,
        "analysis_scope": "hard_candidate_intake",
        "status": "PASS" if seeds and not validation_errors else "REVIEW",
        "task_count": len(tasks),
        "seed_count": len(seeds),
        "known_hard_seed_count": sum(1 for seed in seeds if seed.get("known_hard_for")),
        "family_counts": dict(sorted(family_counts.items())),
        "validation_error_count": len(validation_errors),
        "validation_errors": validation_errors,
    }
    return summary, seeds


def write_candidate_intake_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
    seeds: list[dict[str, Any]],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "candidate_seeds.jsonl").open("w", encoding="utf-8") as fh:
        for seed in seeds:
            fh.write(json.dumps(seed, sort_keys=True) + "\n")

