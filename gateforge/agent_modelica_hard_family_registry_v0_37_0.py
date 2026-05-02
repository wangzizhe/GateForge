from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hard_family_registry_v0_37_0"

REGISTRY_SCHEMA_VERSION = "gateforge_hard_family_registry_v1"

ALLOWED_REGISTRY_STATUSES = {
    "candidate",
    "admitted",
    "repeatable_candidate",
    "formal_benchmark_seed",
    "rejected",
}

REQUIRED_SEED_FIELDS = (
    "case_id",
    "family",
    "source_reference",
    "source_backed",
    "workflow_intent",
    "visible_task_description",
    "hidden_oracle",
    "mutation_intent",
    "expected_failure_mode",
    "model_check_first",
    "blind_lint_status",
    "admission_status",
    "repeatability_status",
    "evidence_role",
    "known_hard_for",
    "registry_status",
)

CASE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def validate_registry_seed(seed: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_SEED_FIELDS:
        if field not in seed:
            errors.append(f"missing_required:{field}")
    if errors:
        return errors

    case_id = str(seed.get("case_id") or "")
    if not CASE_ID_PATTERN.match(case_id):
        errors.append(f"invalid_case_id:{case_id}")
    if not str(seed.get("family") or "").strip():
        errors.append("family_empty")
    if not isinstance(seed.get("source_backed"), bool):
        errors.append("source_backed_must_be_bool")
    if not str(seed.get("workflow_intent") or "").strip():
        errors.append("workflow_intent_empty")
    if not str(seed.get("visible_task_description") or "").strip():
        errors.append("visible_task_description_empty")
    if not isinstance(seed.get("hidden_oracle"), dict):
        errors.append("hidden_oracle_must_be_dict")
    if not isinstance(seed.get("model_check_first"), bool):
        errors.append("model_check_first_must_be_bool")
    if not isinstance(seed.get("known_hard_for"), list):
        errors.append("known_hard_for_must_be_list")
    else:
        for item in seed.get("known_hard_for") or []:
            if not str(item).strip():
                errors.append("known_hard_for_contains_empty_item")
                break
    status = str(seed.get("registry_status") or "")
    if status not in ALLOWED_REGISTRY_STATUSES:
        errors.append(f"invalid_registry_status:{status}")
    return errors


def build_registry_summary(
    seeds: list[dict[str, Any]],
    *,
    version: str = "v0.37.0",
) -> dict[str, Any]:
    validation_errors: dict[str, list[str]] = {}
    family_counts: dict[str, int] = {}
    known_hard_count = 0
    for seed in seeds:
        case_id = str(seed.get("case_id") or "unknown")
        errors = validate_registry_seed(seed)
        if errors:
            validation_errors[case_id] = errors
        family = str(seed.get("family") or "unknown")
        family_counts[family] = family_counts.get(family, 0) + 1
        if seed.get("known_hard_for"):
            known_hard_count += 1
    return {
        "version": version,
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "analysis_scope": "hard_family_registry",
        "status": "PASS" if seeds and not validation_errors else "REVIEW",
        "seed_count": len(seeds),
        "known_hard_seed_count": known_hard_count,
        "family_counts": dict(sorted(family_counts.items())),
        "validation_error_count": len(validation_errors),
        "validation_errors": validation_errors,
        "allowed_registry_statuses": sorted(ALLOWED_REGISTRY_STATUSES),
        "required_seed_fields": list(REQUIRED_SEED_FIELDS),
    }


def write_registry_outputs(
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
    with (out_dir / "registry.jsonl").open("w", encoding="utf-8") as fh:
        for seed in seeds:
            fh.write(json.dumps(seed, sort_keys=True) + "\n")


def run_hard_family_registry(
    *,
    seeds: list[dict[str, Any]],
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_registry_summary(seeds)
    write_registry_outputs(out_dir=out_dir, summary=summary, seeds=seeds)
    return summary

