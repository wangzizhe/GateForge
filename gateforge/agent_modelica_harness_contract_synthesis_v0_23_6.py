from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUTS = {
    "v0.23.0": REPO_ROOT / "artifacts" / "harness_inventory_audit_v0_23_0" / "summary.json",
    "v0.23.1": REPO_ROOT / "artifacts" / "seed_registry_v0_23_1" / "summary.json",
    "v0.23.2": REPO_ROOT / "artifacts" / "trajectory_schema_v0_23_2" / "summary.json",
    "v0.23.3": REPO_ROOT / "artifacts" / "oracle_contract_v0_23_3" / "summary.json",
    "v0.23.4": REPO_ROOT / "artifacts" / "runner_artifact_contract_v0_23_4" / "summary.json",
    "v0.23.5": REPO_ROOT / "artifacts" / "contract_validator_v0_23_5" / "summary.json",
}
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "harness_contract_synthesis_v0_23_6"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def build_harness_contract_synthesis(
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

    validator = loaded.get("v0.23.5", {})
    inventory = loaded.get("v0.23.0", {})
    seed_registry = loaded.get("v0.23.1", {})
    trajectories = loaded.get("v0.23.2", {})
    oracle = loaded.get("v0.23.3", {})
    artifact_contract = loaded.get("v0.23.4", {})
    ready = not missing_inputs and not non_pass_versions and int(validator.get("total_validation_error_count") or 0) == 0
    summary = {
        "version": "v0.23.6",
        "status": "PASS" if ready else "REVIEW",
        "analysis_scope": "harness_contract_freeze_synthesis",
        "input_statuses": {version: payload.get("status", "MISSING") for version, payload in loaded.items()},
        "missing_inputs": missing_inputs,
        "non_pass_versions": non_pass_versions,
        "phase_outputs": {
            "inventory_summary_count": (inventory.get("file_inventory") or {}).get("summary_count", 0),
            "seed_count": seed_registry.get("seed_count", 0),
            "trajectory_count": trajectories.get("trajectory_count", 0),
            "oracle_event_count": oracle.get("oracle_event_count", 0),
            "artifact_manifest_count": artifact_contract.get("manifest_count", 0),
            "contract_validation_error_count": validator.get("total_validation_error_count", 0),
        },
        "phase_decision": (
            "v0.23_harness_contract_freeze_can_close"
            if ready
            else "v0.23_harness_contract_freeze_needs_review"
        ),
        "ready_for_v0_24_repeatability_replay": ready,
        "v0_24_entry_conditions": {
            "seed_registry_v1_available": seed_registry.get("status") == "PASS",
            "trajectory_schema_v1_available": trajectories.get("status") == "PASS",
            "oracle_contract_v1_available": oracle.get("status") == "PASS",
            "runner_artifact_contract_v1_available": artifact_contract.get("status") == "PASS",
            "contract_validator_available": validator.get("status") == "PASS",
        },
        "discipline": {
            "executor_changes": "none",
            "deterministic_repair_added": False,
            "metric_interpretation": "harness_readiness_not_llm_capability_gain",
            "public_changelog_update": "defer_until_public_phase_closeout",
        },
        "next_focus": "v0.24_repeatability_and_replay_harness",
        "conclusion": (
            "harness_contract_layer_is_ready_for_repeatability_replay_work"
            if ready
            else "harness_contract_layer_is_not_ready"
        ),
    }
    write_outputs(out_dir=out_dir, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
