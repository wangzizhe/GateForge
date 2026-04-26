from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUTS = {
    "v0.25.0": REPO_ROOT / "artifacts" / "substrate_seed_import_v0_25_0" / "summary.json",
    "v0.25.1": REPO_ROOT / "artifacts" / "substrate_admission_v0_25_1" / "summary.json",
    "v0.25.2": REPO_ROOT / "artifacts" / "substrate_split_v0_25_2" / "summary.json",
    "v0.25.3": REPO_ROOT / "artifacts" / "substrate_manifest_v0_25_3" / "summary.json",
    "v0.25.4": REPO_ROOT / "artifacts" / "public_private_boundary_audit_v0_25_4" / "summary.json",
    "v0.25.5": REPO_ROOT / "artifacts" / "substrate_regression_gates_v0_25_5" / "summary.json",
}
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "benchmark_substrate_synthesis_v0_25_6"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def build_benchmark_substrate_synthesis(
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
    split = loaded.get("v0.25.2", {})
    manifest = loaded.get("v0.25.3", {})
    boundary = loaded.get("v0.25.4", {})
    gates = loaded.get("v0.25.5", {})
    split_counts = split.get("split_counts") or {}
    ready = (
        not missing_inputs
        and not non_pass_versions
        and bool(split_counts.get("positive"))
        and bool(split_counts.get("hard_negative"))
        and bool(split_counts.get("holdout"))
        and bool(split_counts.get("smoke"))
        and int(manifest.get("validation_error_count") or 0) == 0
        and int(boundary.get("finding_count") or 0) == 0
        and int(gates.get("failed_gate_count") or 0) == 0
    )
    summary = {
        "version": "v0.25.6",
        "status": "PASS" if ready else "REVIEW",
        "analysis_scope": "benchmark_substrate_synthesis",
        "input_statuses": {version: payload.get("status", "MISSING") for version, payload in loaded.items()},
        "missing_inputs": missing_inputs,
        "non_pass_versions": non_pass_versions,
        "phase_outputs": {
            "import_status_counts": loaded.get("v0.25.0", {}).get("import_status_counts", {}),
            "admission_status_counts": loaded.get("v0.25.1", {}).get("admission_status_counts", {}),
            "split_counts": split_counts,
            "manifest_seed_count": manifest.get("seed_count", 0),
            "boundary_finding_count": boundary.get("finding_count", 0),
            "failed_gate_count": gates.get("failed_gate_count", 0),
        },
        "phase_decision": (
            "v0.25_benchmark_substrate_freeze_can_close"
            if ready
            else "v0.25_benchmark_substrate_freeze_needs_review"
        ),
        "ready_for_v0_26_agent_architecture_reintegration": ready,
        "v0_26_entry_conditions": {
            "substrate_manifest_frozen": manifest.get("status") == "PASS",
            "positive_negative_holdout_smoke_split_available": all(
                bool(split_counts.get(key)) for key in ("positive", "hard_negative", "holdout", "smoke")
            ),
            "public_private_boundary_clean": boundary.get("status") == "PASS",
            "regression_gates_clean": gates.get("status") == "PASS",
        },
        "discipline": {
            "executor_changes": "none",
            "deterministic_repair_added": False,
            "benchmark_is_evaluation_substrate_not_training_set": True,
            "llm_capability_gain_claimed": False,
            "public_changelog_update": "defer_until_public_phase_closeout",
        },
        "next_focus": "v0.26_agent_architecture_reintegration",
        "conclusion": (
            "benchmark_substrate_is_frozen_and_ready_for_agent_architecture_reintegration"
            if ready
            else "benchmark_substrate_freeze_is_not_ready"
        ),
    }
    write_outputs(out_dir=out_dir, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
