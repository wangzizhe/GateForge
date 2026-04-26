from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "run_mode_matrix_v0_26_3"

RUN_MODES: dict[str, dict[str, Any]] = {
    "raw_only": {
        "purpose": "primary_capability_measurement",
        "llm_calls_allowed": True,
        "candidate_count": 1,
        "repeat_count": 1,
        "uses_replay": False,
        "metric_scope": "single_live_agent_behavior",
        "may_report_pass_rate": True,
    },
    "multi_candidate": {
        "purpose": "search_density_probe",
        "llm_calls_allowed": True,
        "candidate_count": "n>=2",
        "repeat_count": 1,
        "uses_replay": False,
        "metric_scope": "candidate_distribution_and_agent_behavior",
        "may_report_pass_rate": True,
    },
    "repeatability": {
        "purpose": "stability_gate",
        "llm_calls_allowed": True,
        "candidate_count": 1,
        "repeat_count": "n>=2",
        "uses_replay": False,
        "metric_scope": "repeatability_under_same_contract",
        "may_report_pass_rate": True,
    },
    "replay": {
        "purpose": "harness_regression_check",
        "llm_calls_allowed": False,
        "candidate_count": 0,
        "repeat_count": 1,
        "uses_replay": True,
        "metric_scope": "artifact_and_metric_recalculation",
        "may_report_pass_rate": False,
    },
    "smoke": {
        "purpose": "transport_and_contract_sanity",
        "llm_calls_allowed": True,
        "candidate_count": 1,
        "repeat_count": 1,
        "uses_replay": False,
        "metric_scope": "integration_health_only",
        "may_report_pass_rate": False,
    },
    "full_private_run": {
        "purpose": "private_phase_closeout",
        "llm_calls_allowed": True,
        "candidate_count": "profile_defined",
        "repeat_count": "profile_defined",
        "uses_replay": False,
        "metric_scope": "phase_closeout_under_private_manifest",
        "may_report_pass_rate": True,
    },
}


def validate_run_mode_matrix(matrix: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    required_modes = {"raw_only", "multi_candidate", "repeatability", "replay", "smoke", "full_private_run"}
    missing = sorted(required_modes - set(matrix.keys()))
    for mode in missing:
        errors.append(f"missing_mode:{mode}")
    for mode, spec in matrix.items():
        for field in (
            "purpose",
            "llm_calls_allowed",
            "candidate_count",
            "repeat_count",
            "uses_replay",
            "metric_scope",
            "may_report_pass_rate",
        ):
            if field not in spec:
                errors.append(f"{mode}:missing:{field}")
        if mode == "replay" and spec.get("llm_calls_allowed") is not False:
            errors.append("replay_must_not_call_llm")
        if mode == "smoke" and spec.get("may_report_pass_rate") is not False:
            errors.append("smoke_must_not_report_pass_rate")
        if mode == "replay" and spec.get("may_report_pass_rate") is not False:
            errors.append("replay_must_not_report_pass_rate")
    return errors


def build_run_mode_matrix(*, out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    validation_errors = validate_run_mode_matrix(RUN_MODES)
    metric_separation = {
        mode: {
            "metric_scope": spec["metric_scope"],
            "may_report_pass_rate": spec["may_report_pass_rate"],
        }
        for mode, spec in RUN_MODES.items()
    }
    summary = {
        "version": "v0.26.3",
        "status": "PASS" if not validation_errors else "REVIEW",
        "analysis_scope": "run_mode_matrix",
        "run_modes": RUN_MODES,
        "validation_errors": validation_errors,
        "metric_separation": metric_separation,
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "llm_capability_gain_claimed": False,
            "smoke_is_not_capability_metric": True,
            "replay_is_not_live_agent_metric": True,
        },
        "decision": (
            "run_mode_matrix_ready_for_harness_regression_ab"
            if not validation_errors
            else "run_mode_matrix_needs_review"
        ),
        "next_focus": "v0.26.4_harness_regression_ab",
    }
    write_outputs(out_dir=out_dir, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "matrix.json").write_text(json.dumps(RUN_MODES, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
