from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_json


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROTOCOL = REPO_ROOT / "artifacts" / "agent_comparison_protocol_v0_50_0" / "summary.json"
DEFAULT_BASELINE = REPO_ROOT / "artifacts" / "agent_comparison_baseline_summary_v0_50_1" / "summary.json"
DEFAULT_BUNDLE = REPO_ROOT / "artifacts" / "external_agent_task_bundle_v0_50_2" / "summary.json"
DEFAULT_INTAKE = REPO_ROOT / "artifacts" / "external_agent_result_intake_v0_50_3" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_comparison_pilot_closeout_v0_50_5"


def build_agent_comparison_pilot_closeout(
    *,
    protocol: dict[str, Any],
    baseline: dict[str, Any],
    bundle: dict[str, Any],
    intake: dict[str, Any],
    version: str = "v0.50.5",
) -> dict[str, Any]:
    external_results_ready = int(intake.get("result_count") or 0) > 0 and intake.get("status") == "PASS"
    protocol_ready = protocol.get("status") == "PASS" and bundle.get("status") == "PASS"
    return {
        "version": version,
        "analysis_scope": "agent_comparison_pilot_closeout",
        "status": "PASS" if protocol_ready else "REVIEW",
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "pilot_case_ids": list(protocol.get("pilot_case_ids") or []),
        "gateforge_baseline_case_count": int(baseline.get("case_count") or 0),
        "external_bundle_task_count": int(bundle.get("task_count") or 0),
        "external_results_ready": external_results_ready,
        "comparison_result_available": False,
        "decision": "protocol_ready_waiting_for_external_agent_runs",
        "next_action": "run_external_agents_manually_on_pilot_bundle",
        "scope_note": (
            "v0.50 prepares the paired pilot protocol and task bundle. It does not claim external-agent comparison "
            "results until external result intake contains validated runs."
        ),
    }


def run_agent_comparison_pilot_closeout(*, out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    summary = build_agent_comparison_pilot_closeout(
        protocol=load_json(DEFAULT_PROTOCOL),
        baseline=load_json(DEFAULT_BASELINE),
        bundle=load_json(DEFAULT_BUNDLE),
        intake=load_json(DEFAULT_INTAKE),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary
