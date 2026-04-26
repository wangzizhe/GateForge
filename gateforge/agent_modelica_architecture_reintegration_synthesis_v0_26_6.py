from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUTS = {
    "v0.26.0": REPO_ROOT / "artifacts" / "executor_boundary_audit_v0_26_0" / "summary.json",
    "v0.26.1": REPO_ROOT / "artifacts" / "observation_contract_v0_26_1" / "summary.json",
    "v0.26.2": REPO_ROOT / "artifacts" / "provider_profile_matrix_v0_26_2" / "summary.json",
    "v0.26.3": REPO_ROOT / "artifacts" / "run_mode_matrix_v0_26_3" / "summary.json",
    "v0.26.4": REPO_ROOT / "artifacts" / "harness_regression_ab_v0_26_4" / "summary.json",
    "v0.26.5": REPO_ROOT / "artifacts" / "product_workflow_smoke_v0_26_5" / "summary.json",
}
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "architecture_reintegration_synthesis_v0_26_6"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def build_architecture_reintegration_synthesis(
    *,
    input_paths: dict[str, Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    paths = input_paths or DEFAULT_INPUTS
    loaded = {version: load_json(path) for version, path in paths.items()}
    missing_inputs = [version for version, payload in loaded.items() if not payload]
    non_pass_versions = [
        version for version, payload in loaded.items() if payload and payload.get("status") != "PASS"
    ]
    v0264 = loaded.get("v0.26.4", {})
    v0265 = loaded.get("v0.26.5", {})
    no_capability_metric_shift = not bool(v0264.get("capability_metric_changed"))
    product_smoke_closed = v0265.get("decision") == "product_workflow_smoke_chain_closed"
    ready = not missing_inputs and not non_pass_versions and no_capability_metric_shift and product_smoke_closed
    summary = {
        "version": "v0.26.6",
        "status": "PASS" if ready else "REVIEW",
        "analysis_scope": "architecture_reintegration_synthesis",
        "input_statuses": {version: payload.get("status", "MISSING") for version, payload in loaded.items()},
        "missing_inputs": missing_inputs,
        "non_pass_versions": non_pass_versions,
        "phase_outputs": {
            "executor_boundary_decision": loaded.get("v0.26.0", {}).get("decision", ""),
            "observation_contract_decision": loaded.get("v0.26.1", {}).get("decision", ""),
            "provider_profile_matrix_decision": loaded.get("v0.26.2", {}).get("decision", ""),
            "run_mode_matrix_decision": loaded.get("v0.26.3", {}).get("decision", ""),
            "harness_regression_decision": loaded.get("v0.26.4", {}).get("decision", ""),
            "product_workflow_smoke_decision": loaded.get("v0.26.5", {}).get("decision", ""),
        },
        "phase_gates": {
            "executor_boundary_clean": loaded.get("v0.26.0", {}).get("status") == "PASS",
            "observation_contract_ready": loaded.get("v0.26.1", {}).get("status") == "PASS",
            "provider_profile_matrix_ready": loaded.get("v0.26.2", {}).get("status") == "PASS",
            "run_mode_matrix_ready": loaded.get("v0.26.3", {}).get("status") == "PASS",
            "harness_regression_no_capability_shift": no_capability_metric_shift,
            "product_workflow_smoke_closed": product_smoke_closed,
        },
        "discipline": {
            "executor_changes": "none",
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "llm_capability_gain_claimed": False,
            "public_changelog_update": "defer_until_public_phase_closeout",
        },
        "phase_decision": (
            "v0.26_architecture_reintegration_can_close"
            if ready
            else "v0.26_architecture_reintegration_needs_review"
        ),
        "next_focus": (
            "small_live_baseline_under_frozen_harness"
            if ready
            else "repair_v0_26_harness_gap"
        ),
    }
    write_outputs(out_dir=out_dir, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
