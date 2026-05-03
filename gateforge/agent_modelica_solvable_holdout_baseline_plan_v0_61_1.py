from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_json


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SPLIT = REPO_ROOT / "artifacts" / "benchmark_split_rebuild_v0_60_3" / "summary.json"
DEFAULT_BUNDLE = REPO_ROOT / "artifacts" / "benchmark_external_bundle_v0_61_0" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "solvable_holdout_baseline_plan_v0_61_1"


def build_solvable_holdout_baseline_plan(
    *,
    split_summary: dict[str, Any],
    bundle_summary: dict[str, Any],
    version: str = "v0.61.1",
) -> dict[str, Any]:
    split_case_ids = split_summary.get("split_case_ids") if isinstance(split_summary.get("split_case_ids"), dict) else {}
    holdout_case_ids = sorted(str(case_id) for case_id in split_case_ids.get("holdout", []) or [])
    gaps: list[str] = []
    if not holdout_case_ids:
        gaps.append("missing_holdout_cases")
    if bundle_summary.get("status") != "PASS":
        gaps.append("external_bundle_not_ready")
    if int(bundle_summary.get("holdout_task_count") or 0) != len(holdout_case_ids):
        gaps.append("bundle_holdout_count_mismatch")
    return {
        "version": version,
        "analysis_scope": "solvable_holdout_baseline_plan",
        "status": "PASS" if not gaps else "REVIEW",
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "artifact_complete": True,
        "readiness_status": "holdout_baseline_plan_ready" if not gaps else "holdout_baseline_plan_incomplete",
        "holdout_case_count": len(holdout_case_ids),
        "holdout_case_ids": holdout_case_ids,
        "run_contract": {
            "agent": "gateforge",
            "run_mode": "tool_use",
            "tool_profile": "base",
            "provider": "env",
            "model": "env",
            "max_steps": 10,
            "max_token_budget": 32000,
            "provider_errors_excluded_from_capability_failure": True,
            "frontier_cases_excluded": True,
            "near_miss_cases_excluded": True,
        },
        "expected_artifacts": {
            "results_jsonl": "artifacts/solvable_holdout_baseline_v0_61_2/results.jsonl",
            "summary_json": "artifacts/solvable_holdout_baseline_v0_61_2/summary.json",
        },
        "gaps": gaps,
        "next_action": "run_gateforge_base_tool_use_on_solvable_holdout",
    }


def write_solvable_holdout_baseline_plan_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "holdout_case_ids.txt").write_text(
        "\n".join(summary["holdout_case_ids"]) + ("\n" if summary["holdout_case_ids"] else ""),
        encoding="utf-8",
    )


def run_solvable_holdout_baseline_plan(
    *,
    split_path: Path = DEFAULT_SPLIT,
    bundle_path: Path = DEFAULT_BUNDLE,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_solvable_holdout_baseline_plan(
        split_summary=load_json(split_path),
        bundle_summary=load_json(bundle_path),
    )
    write_solvable_holdout_baseline_plan_outputs(out_dir=out_dir, summary=summary)
    return summary
