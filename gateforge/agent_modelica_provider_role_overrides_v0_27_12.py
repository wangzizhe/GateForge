from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_deepseek_slice_review_v0_27_2 import load_jsonl
from .agent_modelica_generation_taxonomy_v0_19_59 import load_json


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROLE_REGISTRY = REPO_ROOT / "artifacts" / "benchmark_role_registry_v0_27_8" / "family_roles.jsonl"
DEFAULT_CAPABILITY_AUDIT = REPO_ROOT / "artifacts" / "capability_slice_audit_v0_27_11" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "provider_role_overrides_v0_27_12"


def build_provider_role_overrides(
    *,
    role_rows: list[dict[str, Any]],
    capability_audit_summary: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    provider = str(capability_audit_summary.get("provider") or "unknown")
    model_profile = str(capability_audit_summary.get("model_profile") or "unknown")
    run_mode = str(capability_audit_summary.get("run_mode") or "unknown")
    decision = str(capability_audit_summary.get("decision") or "")
    overrides: list[dict[str, Any]] = []
    for row in role_rows:
        family = str(row.get("family") or "")
        role = str(row.get("role") or "")
        effective_role = role
        rationale = "registry_role_preserved"
        if role == "capability_baseline_candidate" and decision == "demote_capability_baseline_for_current_deepseek_harness":
            effective_role = "current_harness_blocked"
            rationale = "current_deepseek_raw_only_capability_slice_failed_with_terminal_stall"
        overrides.append(
            {
                "family": family,
                "registry_role": role,
                "effective_role": effective_role,
                "provider": provider,
                "model_profile": model_profile,
                "run_mode": run_mode,
                "override_rationale": rationale,
                "recommended_use": _recommended_use(effective_role),
            }
        )
    blocked_count = sum(1 for row in overrides if row["effective_role"] == "current_harness_blocked")
    capability_count = sum(1 for row in overrides if row["effective_role"] == "capability_baseline_candidate")
    summary = {
        "version": "v0.27.12",
        "status": "PASS" if overrides else "REVIEW",
        "analysis_scope": "provider_harness_role_overrides",
        "role_registry_artifact": str(DEFAULT_ROLE_REGISTRY.relative_to(REPO_ROOT)),
        "capability_audit_artifact": str(DEFAULT_CAPABILITY_AUDIT.relative_to(REPO_ROOT)),
        "provider": provider,
        "model_profile": model_profile,
        "run_mode": run_mode,
        "family_count": len(overrides),
        "current_harness_blocked_count": blocked_count,
        "remaining_capability_baseline_candidate_count": capability_count,
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "comparative_claim_made": False,
            "llm_capability_gain_claimed": False,
        },
        "decision": (
            "no_current_deepseek_capability_baseline_available"
            if blocked_count > 0 and capability_count == 0
            else "provider_role_overrides_ready"
        ),
        "next_focus": "stop_live_expansion_until_new_capability_baseline_candidate_exists",
    }
    return overrides, summary


def _recommended_use(effective_role: str) -> str:
    if effective_role == "current_harness_blocked":
        return "do_not_use_for_current_provider_pass_rate"
    if effective_role == "capability_baseline_candidate":
        return "eligible_for_current_provider_capability_slice"
    if effective_role == "hard_negative":
        return "hard_negative_suite_only"
    if effective_role == "diagnostic":
        return "diagnostic_suite_only"
    return "exploratory_only"


def run_provider_role_overrides(
    *,
    role_registry_path: Path = DEFAULT_ROLE_REGISTRY,
    capability_audit_path: Path = DEFAULT_CAPABILITY_AUDIT,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    overrides, summary = build_provider_role_overrides(
        role_rows=load_jsonl(role_registry_path),
        capability_audit_summary=load_json(capability_audit_path) if capability_audit_path.exists() else {},
    )
    write_outputs(out_dir=out_dir, overrides=overrides, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, overrides: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "provider_role_overrides.jsonl").open("w", encoding="utf-8") as fh:
        for row in overrides:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
