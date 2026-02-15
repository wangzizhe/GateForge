import json
import os
import subprocess
import unittest
from pathlib import Path


class DemoScriptTests(unittest.TestCase):
    def test_demo_all_script_writes_bundle_summary(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_all.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

        summary_json = Path("artifacts/demo_all_summary.json")
        summary_md = Path("artifacts/demo_all_summary.md")
        self.assertTrue(summary_json.exists())
        self.assertTrue(summary_md.exists())

        payload = json.loads(summary_json.read_text(encoding="utf-8"))
        self.assertEqual(payload.get("bundle_status"), "PASS")
        self.assertEqual(payload.get("proposal_flow_status"), "PASS")
        self.assertEqual(payload.get("checker_demo_status"), "FAIL")
        self.assertIsInstance(payload.get("proposal_fail_reasons_count"), int)
        self.assertIsInstance(payload.get("checker_reasons_count"), int)
        self.assertIsInstance(payload.get("checker_findings_count"), int)

        result_flags = payload.get("result_flags", {})
        self.assertEqual(result_flags.get("proposal_flow"), "PASS")
        self.assertEqual(result_flags.get("checker_demo_expected_fail"), "PASS")
        self.assertEqual(result_flags.get("steady_demo_expected_nonpass"), "PASS")
        self.assertEqual(result_flags.get("behavior_demo_expected_nonpass"), "PASS")
        self.assertIn(payload.get("steady_demo_decision"), {"NEEDS_REVIEW", "FAIL"})
        self.assertIn(payload.get("behavior_demo_decision"), {"NEEDS_REVIEW", "FAIL"})
        checksums = payload.get("checksums", {})
        self.assertIsInstance(checksums, dict)
        artifacts = payload.get("artifacts", [])
        for artifact in artifacts:
            self.assertIn(artifact, checksums)
            self.assertEqual(len(checksums[artifact]), 64)

    def test_demo_autopilot_dry_run_script_writes_review_template(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_autopilot_dry_run.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

        out_json = Path("artifacts/autopilot/autopilot_dry_run_demo.json")
        out_md = Path("artifacts/autopilot/autopilot_dry_run_demo.md")
        self.assertTrue(out_json.exists())
        self.assertTrue(out_md.exists())

        payload = json.loads(out_json.read_text(encoding="utf-8"))
        self.assertEqual(payload.get("status"), "PLANNED")
        self.assertEqual(payload.get("planned_risk_level"), "high")
        checks = payload.get("planned_required_human_checks", [])
        self.assertTrue(checks)
        self.assertTrue(any("rollback" in c.lower() for c in checks))

    def test_demo_autopilot_dry_run_script_accepts_policy_profile(self) -> None:
        env = dict(os.environ)
        env["POLICY_PROFILE"] = "industrial_strict_v0"
        proc = subprocess.run(
            ["bash", "scripts/demo_autopilot_dry_run.sh"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(Path("artifacts/autopilot/autopilot_dry_run_demo.json").read_text(encoding="utf-8"))
        self.assertTrue(str(payload.get("planned_run", {}).get("policy", "")).endswith("industrial_strict_v0.json"))

    def test_demo_all_script_accepts_policy_profile(self) -> None:
        env = dict(os.environ)
        env["POLICY_PROFILE"] = "industrial_strict_v0"
        proc = subprocess.run(
            ["bash", "scripts/demo_all.sh"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(Path("artifacts/demo_all_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(payload.get("policy_profile"), "industrial_strict_v0")

    def test_demo_steady_state_checker_script_expected_fail(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_steady_state_checker.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

        reg_payload = json.loads(Path("artifacts/steady_state_demo_regression.json").read_text(encoding="utf-8"))
        summary_path = Path("artifacts/steady_state_demo_summary.md")

        self.assertEqual(reg_payload.get("decision"), "NEEDS_REVIEW")
        self.assertIn("steady_state_regression_detected", reg_payload.get("reasons", []))
        self.assertTrue(summary_path.exists())

    def test_demo_behavior_metrics_checker_script_expected_nonpass(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_behavior_metrics_checker.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        reg_payload = json.loads(Path("artifacts/behavior_metrics_demo/regression.json").read_text(encoding="utf-8"))
        summary_payload = json.loads(Path("artifacts/behavior_metrics_demo/summary.json").read_text(encoding="utf-8"))
        self.assertEqual(reg_payload.get("decision"), "NEEDS_REVIEW")
        self.assertIn("overshoot_regression_detected", reg_payload.get("reasons", []))
        self.assertIn("settling_time_regression_detected", reg_payload.get("reasons", []))
        self.assertIn("steady_state_regression_detected", reg_payload.get("reasons", []))
        self.assertEqual(summary_payload.get("bundle_status"), "PASS")

    def test_demo_ci_matrix_script_writes_summary(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_ci_matrix.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

        out_json = Path("artifacts/ci_matrix_summary.json")
        out_md = Path("artifacts/ci_matrix_summary.md")
        self.assertTrue(out_json.exists())
        self.assertTrue(out_md.exists())

        payload = json.loads(out_json.read_text(encoding="utf-8"))
        self.assertEqual(payload.get("matrix_status"), "PASS")
        self.assertEqual(payload.get("policy_profile"), "default")
        self.assertGreaterEqual(payload.get("selected_count", 0), 1)
        self.assertIsInstance(payload.get("job_exit_codes"), dict)
        self.assertIn("behavior_metrics_demo", payload.get("selected", {}))
        self.assertIn("repair_loop", payload.get("selected", {}))
        self.assertIn("repair_loop_safety_guard", payload.get("selected", {}))
        self.assertIn("planner_guardrails", payload.get("selected", {}))
        self.assertIn("repair_batch_demo", payload.get("selected", {}))
        self.assertIn("repair_batch_compare_demo", payload.get("selected", {}))
        self.assertIn("repair_pack_from_tasks_demo", payload.get("selected", {}))
        self.assertIn("repair_tasks_demo", payload.get("selected", {}))
        self.assertIn("repair_orchestrate_demo", payload.get("selected", {}))
        self.assertIn("repair_orchestrate_compare_demo", payload.get("selected", {}))
        self.assertIn("governance_snapshot_demo", payload.get("selected", {}))
        self.assertIn("governance_snapshot_orchestrate_demo", payload.get("selected", {}))
        self.assertIn("governance_snapshot_trend_demo", payload.get("selected", {}))
        self.assertIn("governance_history_demo", payload.get("selected", {}))
        self.assertIn("planner_output_validate_demo", payload.get("selected", {}))
        self.assertIn("governance_promote_demo", payload.get("selected", {}))
        self.assertIn("governance_promote_compare_demo", payload.get("selected", {}))
        self.assertIn("governance_promote_apply_demo", payload.get("selected", {}))
        self.assertIn("agent_invariant_guard_demo", payload.get("selected", {}))
        self.assertIn("invariant_repair_loop_demo", payload.get("selected", {}))
        self.assertIsInstance(payload.get("planner_guardrail_rule_ids"), list)
        self.assertIn("change_plan_confidence_min_below_threshold", payload.get("planner_guardrail_rule_ids", []))

    def test_demo_agent_change_loop_script(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_agent_change_loop.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(Path("artifacts/agent_change_loop/summary.json").read_text(encoding="utf-8"))
        self.assertEqual(payload.get("bundle_status"), "PASS")
        self.assertEqual(payload.get("low_risk_status"), "PASS")
        self.assertEqual(payload.get("high_risk_status"), "NEEDS_REVIEW")

    def test_demo_invariant_repair_loop_script(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_invariant_repair_loop.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(Path("artifacts/invariant_repair_loop_demo/demo_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(payload.get("bundle_status"), "PASS")
        self.assertTrue(payload.get("plan_detected"))
        self.assertTrue(payload.get("loop_applied"))
        self.assertIn(payload.get("after_status"), {"PASS", "NEEDS_REVIEW"})

    def test_demo_planner_confidence_gates_script(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_planner_confidence_gates.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(Path("artifacts/planner_confidence_demo/summary.json").read_text(encoding="utf-8"))
        self.assertEqual(payload.get("bundle_status"), "PASS")
        self.assertEqual(payload.get("high_confidence", {}).get("status"), "PASS")
        self.assertEqual(payload.get("mid_confidence", {}).get("status"), "NEEDS_REVIEW")
        self.assertIn(payload.get("low_confidence", {}).get("status"), {"FAIL", "UNKNOWN"})

    def test_demo_planner_guardrails_script(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_planner_guardrails.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(Path("artifacts/planner_guardrails_demo/summary.json").read_text(encoding="utf-8"))
        self.assertEqual(payload.get("bundle_status"), "PASS")
        self.assertEqual(payload.get("pass_case", {}).get("status"), "PASS")
        self.assertEqual(payload.get("low_confidence_case", {}).get("status"), "PASS")
        self.assertEqual(payload.get("whitelist_case", {}).get("status"), "PASS")
        self.assertIn("change_plan_confidence_min_below_threshold", payload.get("rule_ids", {}).get("all", []))
        self.assertIn("change_plan_file_not_whitelisted", payload.get("rule_ids", {}).get("all", []))

    def test_demo_planner_output_validate_script(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_planner_output_validate.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(Path("artifacts/planner_output_validate_demo/summary.json").read_text(encoding="utf-8"))
        self.assertEqual(payload.get("bundle_status"), "PASS")
        self.assertEqual(payload.get("pass_case_status"), "PASS")
        self.assertEqual(payload.get("fail_case_status"), "FAIL")

    def test_demo_review_resolution_script(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_review_resolution.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(Path("artifacts/review_demo/summary.json").read_text(encoding="utf-8"))
        self.assertEqual(payload.get("bundle_status"), "PASS")
        self.assertEqual(payload.get("source_status"), "NEEDS_REVIEW")
        self.assertEqual(payload.get("approve_final_status"), "PASS")
        self.assertEqual(payload.get("reject_final_status"), "FAIL")

    def test_demo_review_ledger_script(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_review_ledger.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(Path("artifacts/review_ledger_demo/ledger_summary.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(payload.get("total_records", 0), 2)
        status = payload.get("status_counts", {})
        self.assertGreaterEqual(status.get("PASS", 0), 1)
        self.assertGreaterEqual(status.get("FAIL", 0), 1)

    def test_demo_review_ledger_export_script(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_review_ledger_export.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        fail_payload = json.loads(Path("artifacts/review_export_demo/fail_records.json").read_text(encoding="utf-8"))
        proposal_payload = json.loads(
            Path("artifacts/review_export_demo/proposal_records.json").read_text(encoding="utf-8")
        )
        self.assertGreaterEqual(fail_payload.get("total_records", 0), 1)
        self.assertGreaterEqual(proposal_payload.get("total_records", 0), 1)

    def test_demo_review_kpis_script(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_review_kpis.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(Path("artifacts/review_kpi_demo/kpi_summary.json").read_text(encoding="utf-8"))
        self.assertIn("kpis", payload)
        self.assertIn("approval_rate", payload["kpis"])
        self.assertIn("sla_breach_rate", payload["kpis"])

    def test_demo_repair_loop_script(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_repair_loop.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(Path("artifacts/repair_loop/demo_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(payload.get("bundle_status"), "PASS")
        self.assertEqual(payload.get("after_status"), "PASS")
        self.assertEqual(payload.get("delta"), "improved")
        self.assertFalse(payload.get("safety_guard_triggered"))

    def test_demo_repair_loop_safety_guard_script(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_repair_loop_safety_guard.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(Path("artifacts/repair_loop_safety_demo/demo_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(payload.get("bundle_status"), "PASS")
        self.assertEqual(payload.get("after_status"), "FAIL")
        self.assertTrue(payload.get("safety_guard_triggered"))

    def test_demo_repair_batch_script(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_repair_batch.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(Path("artifacts/repair_batch_demo/demo_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(payload.get("bundle_status"), "PASS")
        self.assertEqual(payload.get("total_cases"), 2)
        self.assertGreaterEqual(payload.get("pass_count", 0), 1)
        self.assertGreaterEqual(payload.get("fail_count", 0), 1)

    def test_demo_repair_batch_compare_script(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_repair_batch_compare.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(Path("artifacts/repair_batch_compare_demo/demo_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(payload.get("bundle_status"), "PASS")
        compare = payload.get("compare", {})
        self.assertEqual(compare.get("from_policy_profile"), "default")
        self.assertEqual(compare.get("to_policy_profile"), "industrial_strict_v0")
        self.assertEqual(compare.get("total_compared_cases"), 2)

    def test_demo_repair_tasks_script(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_repair_tasks.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(Path("artifacts/repair_tasks_demo/demo_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(payload.get("bundle_status"), "PASS")
        self.assertEqual(payload.get("policy_decision"), "FAIL")
        self.assertGreater(payload.get("task_count", 0), 0)
        self.assertGreater(payload.get("p0_count", 0), 0)

    def test_demo_repair_pack_from_tasks_script(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_repair_pack_from_tasks.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(Path("artifacts/repair_pack_demo/demo_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(payload.get("bundle_status"), "PASS")
        self.assertGreater(payload.get("case_count", 0), 0)

    def test_demo_repair_orchestrate_script(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_repair_orchestrate.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(Path("artifacts/repair_orchestrate_demo/demo_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(payload.get("bundle_status"), "PASS")

    def test_demo_repair_orchestrate_compare_script(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_repair_orchestrate_compare.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(Path("artifacts/repair_orchestrate_compare_demo/demo_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(payload.get("bundle_status"), "PASS")
        self.assertIn(payload.get("compare_relation"), {"upgraded", "unchanged", "downgraded"})
        self.assertIn(payload.get("recommended_profile"), {"default", "industrial_strict"})

    def test_demo_governance_snapshot_script(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_governance_snapshot.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(Path("artifacts/governance_snapshot_demo/summary.json").read_text(encoding="utf-8"))
        self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
        self.assertIn("kpis", payload)

    def test_demo_governance_snapshot_from_orchestrate_compare_script(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_governance_snapshot_from_orchestrate_compare.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(
            Path("artifacts/governance_snapshot_orchestrate_demo/demo_summary.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload.get("bundle_status"), "PASS")
        self.assertIn(payload.get("strategy_compare_relation"), {"upgraded", "unchanged", "downgraded"})
        self.assertIn(payload.get("recommended_profile"), {"default", "industrial_strict"})

    def test_demo_governance_snapshot_trend_script(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_governance_snapshot_trend.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(Path("artifacts/governance_snapshot_trend_demo/summary.json").read_text(encoding="utf-8"))
        trend = payload.get("trend", {})
        self.assertTrue(trend)
        self.assertIn("status_transition", trend)
        self.assertIn("kpi_delta", trend)

    def test_demo_governance_promote_script(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_governance_promote.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(Path("artifacts/governance_promote_demo/summary.json").read_text(encoding="utf-8"))
        self.assertEqual(payload.get("bundle_status"), "PASS")
        self.assertIn(payload.get("default_decision"), {"PASS", "NEEDS_REVIEW"})
        self.assertEqual(payload.get("industrial_decision"), "FAIL")
        self.assertEqual(payload.get("override_decision"), "PASS")
        self.assertEqual(payload.get("mismatch_default_decision"), "NEEDS_REVIEW")
        self.assertEqual(payload.get("mismatch_industrial_decision"), "FAIL")
        self.assertTrue(payload.get("override_applied"))

    def test_demo_governance_promote_compare_script(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_governance_promote_compare.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(Path("artifacts/governance_promote_compare_demo/demo_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(payload.get("bundle_status"), "PASS")
        self.assertIn(payload.get("best_profile"), {"default", "industrial_strict"})
        self.assertIn(payload.get("best_decision"), {"PASS", "NEEDS_REVIEW", "FAIL"})
        self.assertIsInstance(payload.get("best_total_score"), int)
        self.assertIn(payload.get("best_reason"), {"highest_total_score", "recommended_profile_preferred_within_top_total_score"})
        self.assertIsInstance(payload.get("best_score_breakdown"), dict)
        self.assertIsInstance(payload.get("ranking_top_2"), list)
        self.assertIsInstance(payload.get("top_score_margin"), int)
        self.assertIsInstance(payload.get("min_top_score_margin"), int)
        self.assertIn(payload.get("override_best_profile"), {"default", "industrial_strict"})
        self.assertIn(payload.get("override_best_decision"), {"PASS", "NEEDS_REVIEW", "FAIL"})

    def test_demo_governance_promote_apply_script(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_governance_promote_apply.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(Path("artifacts/governance_promote_apply_demo/summary.json").read_text(encoding="utf-8"))
        self.assertEqual(payload.get("bundle_status"), "PASS")
        self.assertEqual(payload.get("pass_status"), "PASS")
        self.assertEqual(payload.get("missing_ticket_status"), "FAIL")
        self.assertEqual(payload.get("with_ticket_status"), "NEEDS_REVIEW")
        self.assertEqual(payload.get("with_ticket_id"), "REV-42")
        self.assertEqual(payload.get("audit_row_count"), 3)

    def test_demo_agent_invariant_guard_script(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_agent_invariant_guard.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(Path("artifacts/agent_invariant_guard_demo/summary.json").read_text(encoding="utf-8"))
        self.assertEqual(payload.get("bundle_status"), "PASS")
        self.assertEqual(payload.get("pass_decision"), "PASS")
        self.assertEqual(payload.get("medium_decision"), "NEEDS_REVIEW")
        self.assertEqual(payload.get("high_decision"), "FAIL")

    def test_demo_governance_history_script(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_governance_history.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(Path("artifacts/governance_history_demo/summary.json").read_text(encoding="utf-8"))
        self.assertEqual(payload.get("total_records"), 3)
        self.assertEqual(payload.get("window_size"), 3)
        self.assertEqual(payload.get("latest_status"), "FAIL")
        self.assertIn("consecutive_worsening_detected", payload.get("alerts", []))


if __name__ == "__main__":
    unittest.main()
