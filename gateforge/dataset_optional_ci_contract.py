from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Dataset Optional CI Contract",
        "",
        f"- status: `{payload.get('status')}`",
        f"- required_summary_count: `{payload.get('required_summary_count')}`",
        f"- pass_count: `{payload.get('pass_count')}`",
        f"- fail_count: `{payload.get('fail_count')}`",
        "",
        "## Checks",
        "",
    ]
    for check in payload.get("checks", []):
        lines.append(
            f"- `{check.get('name')}` status=`{check.get('status')}` path=`{check.get('path')}` missing_keys=`{','.join(check.get('missing_keys') or []) or 'none'}`"
        )
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _validate_required_summary(root: Path, name: str, rel_path: str, required_keys: list[str]) -> dict:
    path = root / rel_path
    if not path.exists():
        return {
            "name": name,
            "path": str(path),
            "status": "FAIL",
            "reason": "missing_file",
            "missing_keys": required_keys,
        }
    payload = _load_json(path)
    missing = [k for k in required_keys if k not in payload]
    return {
        "name": name,
        "path": str(path),
        "status": "PASS" if not missing else "FAIL",
        "reason": "ok" if not missing else "missing_required_keys",
        "missing_keys": missing,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate dataset optional CI artifact contract")
    parser.add_argument("--artifacts-root", default="artifacts")
    parser.add_argument("--out", default="artifacts/dataset_optional_ci_contract/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    root = Path(args.artifacts_root)
    required = [
        ("dataset_pipeline_demo", "dataset_pipeline_demo/summary.json", ["bundle_status", "result_flags"]),
        (
            "dataset_artifacts_pipeline_demo",
            "dataset_artifacts_pipeline_demo/summary.json",
            ["bundle_status", "quality_gate_status"],
        ),
        ("dataset_history_demo", "dataset_history_demo/summary.json", ["bundle_status"]),
        ("dataset_governance_demo", "dataset_governance_demo/summary.json", ["bundle_status"]),
        ("dataset_policy_lifecycle_demo", "dataset_policy_lifecycle_demo/summary.json", ["bundle_status"]),
        ("dataset_governance_history_demo", "dataset_governance_history_demo/summary.json", ["bundle_status"]),
        ("dataset_strategy_autotune_demo", "dataset_strategy_autotune_demo/summary.json", ["bundle_status"]),
        ("dataset_strategy_autotune_apply_demo", "dataset_strategy_autotune_apply_demo/summary.json", ["bundle_status"]),
        (
            "dataset_strategy_autotune_apply_history_demo",
            "dataset_strategy_autotune_apply_history_demo/summary.json",
            ["bundle_status"],
        ),
        (
            "dataset_governance_snapshot_demo",
            "dataset_governance_snapshot_demo/demo_summary.json",
            [
                "bundle_status",
                "promotion_effectiveness_history_trend_status",
                "failure_taxonomy_coverage_status",
                "failure_taxonomy_missing_model_scales_count",
                "failure_distribution_benchmark_status",
                "failure_distribution_drift_score",
                "model_scale_ladder_status",
                "model_scale_large_ready",
                "failure_policy_patch_advisor_status",
                "failure_policy_patch_suggested_action",
                "modelica_library_provenance_guard_status",
                "modelica_library_provenance_completeness_pct",
                "large_model_benchmark_pack_status",
                "large_model_benchmark_pack_readiness_score",
                "mutation_campaign_tracker_status",
                "mutation_campaign_completion_ratio_pct",
                "moat_public_scoreboard_status",
                "moat_public_score",
                "real_model_license_compliance_status",
                "real_model_license_compliance_unknown_license_ratio_pct",
                "modelica_mutation_recipe_library_status",
                "modelica_mutation_recipe_total",
                "real_model_failure_yield_status",
                "real_model_failure_yield_per_accepted_model",
                "real_model_intake_backlog_status",
                "real_model_intake_backlog_p0_count",
                "modelica_moat_readiness_gate_status",
                "modelica_moat_readiness_score",
                "real_model_supply_health_status",
                "real_model_supply_health_score",
                "mutation_recipe_execution_audit_status",
                "mutation_recipe_execution_coverage_pct",
                "modelica_release_candidate_gate_status",
                "modelica_release_candidate_score",
            ],
        ),
        (
            "dataset_governance_snapshot_trend_demo",
            "dataset_governance_snapshot_trend_demo/demo_summary.json",
            [
                "bundle_status",
                "status_transition",
                "promotion_effectiveness_history_trend_transition",
                "failure_taxonomy_coverage_status_transition",
                "failure_distribution_benchmark_status_transition",
                "model_scale_ladder_status_transition",
                "failure_policy_patch_advisor_status_transition",
                "modelica_library_provenance_guard_status_transition",
                "large_model_benchmark_pack_status_transition",
                "mutation_campaign_tracker_status_transition",
                "moat_public_scoreboard_status_transition",
                "real_model_license_compliance_status_transition",
                "modelica_mutation_recipe_library_status_transition",
                "real_model_failure_yield_status_transition",
                "real_model_intake_backlog_status_transition",
                "modelica_moat_readiness_gate_status_transition",
                "real_model_supply_health_status_transition",
                "mutation_recipe_execution_audit_status_transition",
                "modelica_release_candidate_gate_status_transition",
                "status_delta_alert_count",
                "severity_level",
            ],
        ),
        (
            "dataset_failure_taxonomy_coverage_demo",
            "dataset_failure_taxonomy_coverage_demo/demo_summary.json",
            ["bundle_status", "coverage_status", "missing_model_scales_count"],
        ),
        (
            "dataset_failure_distribution_benchmark_demo",
            "dataset_failure_distribution_benchmark_demo/demo_summary.json",
            ["bundle_status", "benchmark_status", "distribution_drift_score"],
        ),
        (
            "dataset_model_scale_ladder_demo",
            "dataset_model_scale_ladder_demo/demo_summary.json",
            ["bundle_status", "ladder_status", "large_ready"],
        ),
        (
            "dataset_failure_policy_patch_advisor_demo",
            "dataset_failure_policy_patch_advisor_demo/demo_summary.json",
            ["bundle_status", "advisor_status", "suggested_action"],
        ),
        (
            "dataset_blind_spot_backlog_demo",
            "dataset_blind_spot_backlog_demo/demo_summary.json",
            ["bundle_status", "backlog_status", "total_open_tasks"],
        ),
        (
            "dataset_policy_patch_replay_evaluator_demo",
            "dataset_policy_patch_replay_evaluator_demo/demo_summary.json",
            ["bundle_status", "evaluator_status", "recommendation"],
        ),
        (
            "dataset_governance_evidence_pack_demo",
            "dataset_governance_evidence_pack_demo/demo_summary.json",
            [
                "bundle_status",
                "evidence_pack_status",
                "evidence_strength_score",
                "backlog_open_tasks",
                "policy_patch_roi_score",
            ],
        ),
        (
            "dataset_moat_trend_snapshot_demo",
            "dataset_moat_trend_snapshot_demo/demo_summary.json",
            ["bundle_status", "moat_status", "moat_score", "moat_score_delta"],
        ),
        (
            "dataset_backlog_execution_bridge_demo",
            "dataset_backlog_execution_bridge_demo/demo_summary.json",
            ["bundle_status", "bridge_status", "total_execution_tasks"],
        ),
        (
            "dataset_replay_quality_guard_demo",
            "dataset_replay_quality_guard_demo/demo_summary.json",
            ["bundle_status", "guard_status", "confidence_level"],
        ),
        (
            "dataset_promotion_candidate_demo",
            "dataset_promotion_candidate_demo/summary.json",
            ["bundle_status", "decision"],
        ),
        (
            "dataset_promotion_candidate_apply_demo",
            "dataset_promotion_candidate_apply_demo/summary.json",
            ["bundle_status"],
        ),
        (
            "dataset_promotion_candidate_history_demo",
            "dataset_promotion_candidate_history_demo/summary.json",
            ["bundle_status"],
        ),
        (
            "dataset_promotion_candidate_apply_history_demo",
            "dataset_promotion_candidate_apply_history_demo/summary.json",
            ["bundle_status"],
        ),
        (
            "dataset_promotion_effectiveness_demo",
            "dataset_promotion_effectiveness_demo/summary.json",
            ["bundle_status", "effectiveness_decision"],
        ),
        (
            "dataset_promotion_effectiveness_history_demo",
            "dataset_promotion_effectiveness_history_demo/summary.json",
            ["bundle_status", "trend_status"],
        ),
        (
            "dataset_policy_autotune_history_demo",
            "dataset_policy_autotune_history_demo/summary.json",
            ["bundle_status"],
        ),
        (
            "dataset_modelica_library_provenance_guard_v1_demo",
            "dataset_modelica_library_provenance_guard_v1_demo/demo_summary.json",
            ["bundle_status", "guard_status", "provenance_completeness_pct", "unknown_license_ratio_pct"],
        ),
        (
            "dataset_large_model_benchmark_pack_v1_demo",
            "dataset_large_model_benchmark_pack_v1_demo/demo_summary.json",
            [
                "bundle_status",
                "pack_status",
                "pack_readiness_score",
                "selected_large_models",
                "selected_large_mutations",
            ],
        ),
        (
            "dataset_mutation_campaign_tracker_v1_demo",
            "dataset_mutation_campaign_tracker_v1_demo/demo_summary.json",
            ["bundle_status", "tracker_status", "campaign_phase", "completion_ratio_pct"],
        ),
        (
            "dataset_moat_public_scoreboard_v1_demo",
            "dataset_moat_public_scoreboard_v1_demo/demo_summary.json",
            ["bundle_status", "scoreboard_status", "moat_public_score", "verdict"],
        ),
        (
            "dataset_real_model_license_compliance_gate_v1_demo",
            "dataset_real_model_license_compliance_gate_v1_demo/demo_summary.json",
            ["bundle_status", "license_gate_status"],
        ),
        (
            "dataset_modelica_mutation_recipe_library_v1_demo",
            "dataset_modelica_mutation_recipe_library_v1_demo/demo_summary.json",
            ["bundle_status", "recipe_library_status"],
        ),
        (
            "dataset_real_model_failure_yield_tracker_v1_demo",
            "dataset_real_model_failure_yield_tracker_v1_demo/demo_summary.json",
            ["bundle_status", "yield_tracker_status"],
        ),
        (
            "dataset_real_model_intake_backlog_prioritizer_v1_demo",
            "dataset_real_model_intake_backlog_prioritizer_v1_demo/demo_summary.json",
            ["bundle_status", "backlog_prioritizer_status"],
        ),
        (
            "dataset_modelica_moat_readiness_gate_v1_demo",
            "dataset_modelica_moat_readiness_gate_v1_demo/demo_summary.json",
            ["bundle_status", "moat_gate_status"],
        ),
        (
            "dataset_real_model_supply_health_v1_demo",
            "dataset_real_model_supply_health_v1_demo/demo_summary.json",
            ["bundle_status", "supply_health_status", "supply_health_score"],
        ),
        (
            "dataset_mutation_recipe_execution_audit_v1_demo",
            "dataset_mutation_recipe_execution_audit_v1_demo/demo_summary.json",
            ["bundle_status", "audit_status", "execution_coverage_pct"],
        ),
        (
            "dataset_modelica_release_candidate_gate_v1_demo",
            "dataset_modelica_release_candidate_gate_v1_demo/demo_summary.json",
            ["bundle_status", "release_candidate_status", "candidate_decision"],
        ),
    ]
    checks = [_validate_required_summary(root, name, rel_path, keys) for name, rel_path, keys in required]
    pass_count = len([x for x in checks if x.get("status") == "PASS"])
    fail_count = len(checks) - pass_count
    payload = {
        "status": "PASS" if fail_count == 0 else "FAIL",
        "artifacts_root": str(root),
        "required_summary_count": len(required),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "checks": checks,
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": payload.get("status"), "fail_count": fail_count}))
    if payload["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
