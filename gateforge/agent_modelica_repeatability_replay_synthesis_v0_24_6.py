from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUTS = {
    "v0.24.0": REPO_ROOT / "artifacts" / "repeatability_protocol_v0_24_0" / "summary.json",
    "v0.24.1": REPO_ROOT / "artifacts" / "unified_repeatability_runner_v0_24_1" / "summary.json",
    "v0.24.2": REPO_ROOT / "artifacts" / "provider_noise_classifier_v0_24_2" / "summary.json",
    "v0.24.3": REPO_ROOT / "artifacts" / "budget_policy_v0_24_3" / "summary.json",
    "v0.24.4": REPO_ROOT / "artifacts" / "golden_smoke_pack_v0_24_4" / "summary.json",
    "v0.24.5": REPO_ROOT / "artifacts" / "replay_harness_v0_24_5" / "summary.json",
}
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "repeatability_replay_synthesis_v0_24_6"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def build_repeatability_replay_synthesis(
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
    replay = loaded.get("v0.24.5", {})
    smoke = loaded.get("v0.24.4", {})
    budget = loaded.get("v0.24.3", {})
    ready = (
        not missing_inputs
        and not non_pass_versions
        and int(replay.get("candidate_diff_count") or 0) == 0
        and int(replay.get("family_diff_count") or 0) == 0
        and int(smoke.get("validation_error_count") or 0) == 0
        and int(budget.get("validation_error_count") or 0) == 0
    )
    summary = {
        "version": "v0.24.6",
        "status": "PASS" if ready else "REVIEW",
        "analysis_scope": "repeatability_replay_harness_synthesis",
        "input_statuses": {version: payload.get("status", "MISSING") for version, payload in loaded.items()},
        "missing_inputs": missing_inputs,
        "non_pass_versions": non_pass_versions,
        "phase_outputs": {
            "candidate_count": loaded.get("v0.24.0", {}).get("candidate_count", 0),
            "family_count": loaded.get("v0.24.0", {}).get("family_count", 0),
            "provider_noise_count": loaded.get("v0.24.2", {}).get("provider_noise_count", 0),
            "infra_noise_count": loaded.get("v0.24.2", {}).get("infra_noise_count", 0),
            "budget_validation_error_count": budget.get("validation_error_count", 0),
            "smoke_validation_error_count": smoke.get("validation_error_count", 0),
            "replay_candidate_diff_count": replay.get("candidate_diff_count", 0),
            "replay_family_diff_count": replay.get("family_diff_count", 0),
        },
        "phase_decision": (
            "v0.24_repeatability_replay_harness_can_close"
            if ready
            else "v0.24_repeatability_replay_harness_needs_review"
        ),
        "ready_for_v0_25_benchmark_substrate_freeze": ready,
        "v0_25_entry_conditions": {
            "repeatability_protocol_available": loaded.get("v0.24.0", {}).get("status") == "PASS",
            "unified_repeatability_runner_available": loaded.get("v0.24.1", {}).get("status") == "PASS",
            "provider_noise_classifier_available": loaded.get("v0.24.2", {}).get("status") == "PASS",
            "budget_policy_available": budget.get("status") == "PASS",
            "golden_smoke_pack_available": smoke.get("status") == "PASS",
            "replay_harness_available": replay.get("status") == "PASS",
        },
        "discipline": {
            "executor_changes": "none",
            "deterministic_repair_added": False,
            "llm_capability_gain_claimed": False,
            "public_changelog_update": "defer_until_public_phase_closeout",
        },
        "next_focus": "v0.25_benchmark_substrate_freeze",
        "conclusion": (
            "repeatability_and_replay_layer_is_ready_for_benchmark_substrate_freeze"
            if ready
            else "repeatability_and_replay_layer_is_not_ready"
        ),
    }
    write_outputs(out_dir=out_dir, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
