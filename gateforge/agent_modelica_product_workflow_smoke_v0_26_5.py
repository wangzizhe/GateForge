from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUTS = {
    "observation_contract": REPO_ROOT / "artifacts" / "observation_contract_v0_26_1" / "summary.json",
    "provider_profile_matrix": REPO_ROOT / "artifacts" / "provider_profile_matrix_v0_26_2" / "summary.json",
    "run_mode_matrix": REPO_ROOT / "artifacts" / "run_mode_matrix_v0_26_3" / "summary.json",
    "harness_regression_ab": REPO_ROOT / "artifacts" / "harness_regression_ab_v0_26_4" / "summary.json",
    "golden_smoke_pack": REPO_ROOT / "artifacts" / "golden_smoke_pack_v0_24_4" / "summary.json",
    "replay_harness": REPO_ROOT / "artifacts" / "replay_harness_v0_24_5" / "summary.json",
}
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "product_workflow_smoke_v0_26_5"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def build_product_workflow_smoke(
    *,
    input_paths: dict[str, Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    paths = input_paths or DEFAULT_INPUTS
    loaded = {name: load_json(path) for name, path in paths.items()}
    missing_inputs = [name for name, payload in loaded.items() if not payload]
    non_pass_inputs = [name for name, payload in loaded.items() if payload and payload.get("status") != "PASS"]
    run_modes = loaded.get("run_mode_matrix", {}).get("run_modes", {})
    smoke_mode = run_modes.get("smoke", {}) if isinstance(run_modes, dict) else {}
    workflow_stages = [
        {
            "stage": "input_contract",
            "source": "observation_contract",
            "status": loaded.get("observation_contract", {}).get("status", "MISSING"),
        },
        {
            "stage": "provider_profile",
            "source": "provider_profile_matrix",
            "status": loaded.get("provider_profile_matrix", {}).get("status", "MISSING"),
        },
        {
            "stage": "run_mode",
            "source": "run_mode_matrix",
            "status": loaded.get("run_mode_matrix", {}).get("status", "MISSING"),
        },
        {
            "stage": "trajectory_artifact",
            "source": "golden_smoke_pack",
            "status": loaded.get("golden_smoke_pack", {}).get("status", "MISSING"),
        },
        {
            "stage": "replay_artifact",
            "source": "replay_harness",
            "status": loaded.get("replay_harness", {}).get("status", "MISSING"),
        },
        {
            "stage": "metric_regression_guard",
            "source": "harness_regression_ab",
            "status": loaded.get("harness_regression_ab", {}).get("status", "MISSING"),
        },
    ]
    smoke_policy_clean = (
        smoke_mode.get("purpose") == "transport_and_contract_sanity"
        and smoke_mode.get("may_report_pass_rate") is False
    )
    ready = not missing_inputs and not non_pass_inputs and smoke_policy_clean
    summary = {
        "version": "v0.26.5",
        "status": "PASS" if ready else "REVIEW",
        "analysis_scope": "product_workflow_smoke",
        "input_statuses": {name: payload.get("status", "MISSING") for name, payload in loaded.items()},
        "missing_inputs": missing_inputs,
        "non_pass_inputs": non_pass_inputs,
        "workflow_stages": workflow_stages,
        "smoke_policy": {
            "run_mode": "smoke",
            "purpose": smoke_mode.get("purpose", ""),
            "may_report_pass_rate": smoke_mode.get("may_report_pass_rate"),
            "capability_metric_reported": False,
        },
        "artifact_closure": {
            "observation_contract_present": bool(loaded.get("observation_contract")),
            "provider_profile_matrix_present": bool(loaded.get("provider_profile_matrix")),
            "run_mode_matrix_present": bool(loaded.get("run_mode_matrix")),
            "trajectory_artifact_present": bool(loaded.get("golden_smoke_pack")),
            "replay_artifact_present": bool(loaded.get("replay_harness")),
            "harness_regression_guard_present": bool(loaded.get("harness_regression_ab")),
        },
        "discipline": {
            "llm_calls_added": False,
            "pass_rate_reported": False,
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "llm_capability_gain_claimed": False,
        },
        "decision": (
            "product_workflow_smoke_chain_closed"
            if ready
            else "product_workflow_smoke_needs_review"
        ),
        "next_focus": "v0.26.6_architecture_reintegration_synthesis",
    }
    write_outputs(out_dir=out_dir, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
