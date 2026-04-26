from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST_PATHS = [
    REPO_ROOT / "artifacts" / "unified_repeatability_runner_v0_24_1" / "manifest.json",
]
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "budget_policy_v0_24_3"
POLICY_VERSION = "budget_policy_v1"
DEFAULT_POLICIES = {
    "smoke": {
        "repeat_count": 1,
        "max_rounds": 4,
        "timeout_sec": 180,
        "seed_limit": 2,
        "intended_use": "ci_safe_shape_validation",
    },
    "family": {
        "repeat_count": 2,
        "max_rounds": 8,
        "timeout_sec": 420,
        "seed_limit": None,
        "intended_use": "family_repeatability_gate",
    },
    "full_local_private": {
        "repeat_count": 2,
        "max_rounds": 8,
        "timeout_sec": 420,
        "seed_limit": None,
        "intended_use": "local_private_full_substrate_run",
    },
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def budget_policy_definition() -> dict[str, Any]:
    return {
        "policy_version": POLICY_VERSION,
        "policies": DEFAULT_POLICIES,
        "comparison_rule": "arms_are_comparable_only_when_repeat_count_max_rounds_timeout_and_seed_selection_match",
        "policy_change_rule": "budget_changes_require_dedicated_version_and_must_not_be_reported_as_llm_gain",
    }


def validate_budget_policy(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for name, row in policy.get("policies", {}).items():
        if int(row.get("repeat_count") or 0) <= 0:
            errors.append(f"{name}:repeat_count_must_be_positive")
        if int(row.get("max_rounds") or 0) <= 0:
            errors.append(f"{name}:max_rounds_must_be_positive")
        if int(row.get("timeout_sec") or 0) <= 0:
            errors.append(f"{name}:timeout_sec_must_be_positive")
    return errors


def validate_manifest_budget(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    budget = manifest.get("budget_metadata")
    if not isinstance(budget, dict):
        return ["missing_budget_metadata"]
    for field in ("repeat_count", "max_rounds", "timeout_sec", "live_execution"):
        if field not in budget:
            errors.append(f"missing_budget_metadata:{field}")
    return errors


def build_budget_policy_report(
    *,
    manifest_paths: list[Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    paths = manifest_paths or DEFAULT_MANIFEST_PATHS
    policy = budget_policy_definition()
    policy_errors = validate_budget_policy(policy)
    manifest_rows: list[dict[str, Any]] = []
    for path in paths:
        manifest = load_json(path)
        path_text = str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path)
        errors = ["missing_manifest"] if not manifest else validate_manifest_budget(manifest)
        manifest_rows.append(
            {
                "manifest_path": path_text,
                "run_version": str(manifest.get("run_version") or "UNKNOWN"),
                "budget_metadata": manifest.get("budget_metadata") if isinstance(manifest.get("budget_metadata"), dict) else {},
                "validation_errors": errors,
            }
        )
    validation_error_count = len(policy_errors) + sum(len(row["validation_errors"]) for row in manifest_rows)
    status = "PASS" if not validation_error_count else "REVIEW"
    summary = {
        "version": "v0.24.3",
        "status": status,
        "analysis_scope": "budget_timeout_policy_freeze",
        "policy_version": POLICY_VERSION,
        "policy_errors": policy_errors,
        "manifest_count": len(manifest_rows),
        "validation_error_count": validation_error_count,
        "policy_modes": sorted(DEFAULT_POLICIES),
        "decision_policy": "budget_changes_must_not_be_reported_as_llm_capability_gain",
        "discipline": {
            "executor_changes": "none",
            "deterministic_repair_added": False,
            "comparison_requires_same_budget": True,
            "manifest_budget_required": True,
        },
        "conclusion": (
            "budget_timeout_policy_ready_for_golden_smoke_pack"
            if status == "PASS"
            else "budget_timeout_policy_needs_review"
        ),
    }
    write_outputs(out_dir=out_dir, policy=policy, manifest_rows=manifest_rows, summary=summary)
    return summary


def write_outputs(
    *,
    out_dir: Path,
    policy: dict[str, Any],
    manifest_rows: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "budget_policy.json").write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "manifest_budget_audit.jsonl").open("w", encoding="utf-8") as fh:
        for row in manifest_rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
