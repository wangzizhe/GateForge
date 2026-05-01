from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_benchmark_blind_gate_v0_36_4 import (
    build_benchmark_blind_lint_summary,
    lint_benchmark_blindness,
)
from gateforge.agent_modelica_evidence_role_contract_v0_36_3 import (
    apply_evidence_contract,
    compute_conclusion_allowed,
)
from gateforge.agent_modelica_no_wrapper_repair_audit_v0_36_6 import (
    build_no_wrapper_repair_audit,
)
from gateforge.agent_modelica_provider_stability_gate_v0_36_1 import (
    classify_provider_status,
    summarize_provider_smoke,
)
from gateforge.agent_modelica_readiness_closeout_v0_36_8 import build_readiness_closeout
from gateforge.agent_modelica_readiness_inventory_v0_36_0 import (
    REQUIRED_COMPONENTS,
    build_readiness_inventory,
)
from gateforge.agent_modelica_release_readiness_gate_v0_36_7 import (
    READINESS_CHECKS,
    evaluate_release_readiness,
)
from gateforge.agent_modelica_repair_report_v0_36_5 import build_repair_report
from gateforge.agent_modelica_tool_profile_health_audit_v0_36_2 import (
    build_tool_profile_health_summary,
    estimate_tool_profile_health,
)


class ReadinessInventoryV0360Tests(unittest.TestCase):
    def test_inventory_passes_when_all_components_are_audited(self) -> None:
        summary = build_readiness_inventory(
            [
                {"name": name, "present": True, "audited": True, "gaps": []}
                for name in REQUIRED_COMPONENTS
            ]
        )
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["readiness_status"], "inventory_complete")

    def test_inventory_reports_missing_components(self) -> None:
        summary = build_readiness_inventory([])
        self.assertEqual(summary["status"], "REVIEW")
        self.assertIn("tool_use_runner", summary["missing_components"])


class ProviderStabilityGateV0361Tests(unittest.TestCase):
    def test_stable_provider_allows_conclusion(self) -> None:
        result = classify_provider_status(
            provider="provider",
            model="model",
            tool_profile="base",
            provider_errors=[],
        )
        self.assertEqual(result["provider_status"], "provider_stable")
        self.assertTrue(result["conclusion_allowed"])

    def test_transient_provider_error_blocks_conclusion(self) -> None:
        result = classify_provider_status(
            provider="provider",
            model="model",
            tool_profile="structural",
            provider_errors=["service_unavailable:503"],
        )
        self.assertEqual(result["provider_status"], "provider_unstable")
        self.assertFalse(result["conclusion_allowed"])

    def test_unsupported_tool_use_is_distinct(self) -> None:
        result = classify_provider_status(
            provider="provider",
            model="model",
            tool_profile="structural",
            provider_errors=[],
            tool_use_supported=False,
        )
        self.assertEqual(result["provider_status"], "provider_unsupported_tool_use")

    def test_smoke_summary_blocks_when_any_result_unstable(self) -> None:
        summary = summarize_provider_smoke(
            [
                classify_provider_status(
                    provider="provider",
                    model="model",
                    tool_profile="base",
                    provider_errors=[],
                ),
                classify_provider_status(
                    provider="provider",
                    model="model",
                    tool_profile="structural",
                    provider_errors=["timeout"],
                ),
            ]
        )
        self.assertEqual(summary["status"], "REVIEW")
        self.assertFalse(summary["conclusion_allowed"])


class ToolProfileHealthAuditV0362Tests(unittest.TestCase):
    def test_base_profile_health_is_computed(self) -> None:
        row = estimate_tool_profile_health("base")
        self.assertEqual(row["profile"], "base")
        self.assertGreaterEqual(row["tool_count"], 3)
        self.assertIn("first_request_complexity", row)

    def test_summary_includes_profiles(self) -> None:
        summary = build_tool_profile_health_summary(["base", "structural"])
        self.assertEqual(summary["profile_count"], 2)
        self.assertEqual(summary["analysis_scope"], "tool_profile_health_audit")


class EvidenceRoleContractV0363Tests(unittest.TestCase):
    def test_formal_experiment_with_clean_inputs_allows_conclusion(self) -> None:
        self.assertTrue(
            compute_conclusion_allowed(
                evidence_role="formal_experiment",
                provider_status="provider_stable",
                provider_error_count=0,
                load_error_count=0,
                artifact_complete=True,
            )
        )

    def test_smoke_never_becomes_formal_conclusion(self) -> None:
        summary = apply_evidence_contract(
            {"version": "fixture"},
            evidence_role="smoke",
            provider_status="provider_stable",
            provider_error_count=0,
            load_error_count=0,
            artifact_complete=True,
        )
        self.assertFalse(summary["conclusion_allowed"])

    def test_abandoned_exploration_is_marked_non_conclusive(self) -> None:
        summary = apply_evidence_contract(
            {"version": "fixture"},
            evidence_role="abandoned_exploration",
        )
        self.assertFalse(summary["conclusion_allowed"])


class BenchmarkBlindGateV0364Tests(unittest.TestCase):
    def test_blind_task_passes_lint(self) -> None:
        result = lint_benchmark_blindness(
            {
                "case_id": "blind",
                "description": "Repair the model so it checks and simulates.",
                "constraints": ["Preserve external interface."],
                "hidden_oracle": {"solution": "private"},
            }
        )
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["blind_benchmark_eligible"])

    def test_task_with_answer_leakage_fails_lint(self) -> None:
        result = lint_benchmark_blindness(
            {
                "case_id": "leaky",
                "description": "The root cause is a missing equation.",
            }
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(result["blind_benchmark_eligible"])

    def test_summary_reports_leaking_task_count(self) -> None:
        summary = build_benchmark_blind_lint_summary(
            [
                {"case_id": "ok", "description": "Repair the model."},
                {"case_id": "bad", "description": "The correct fix is to add an equation."},
            ]
        )
        self.assertEqual(summary["status"], "FAIL")
        self.assertEqual(summary["leaking_task_count"], 1)


class RepairReportV0365Tests(unittest.TestCase):
    def test_report_classifies_passed_submission(self) -> None:
        report = build_repair_report(
            {
                "case_id": "case",
                "model_name": "M",
                "provider": "provider",
                "tool_profile": "base",
                "final_verdict": "PASS",
                "submitted": True,
                "step_count": 2,
                "steps": [
                    {"tool_calls": [{"name": "check_model"}]},
                    {"tool_calls": [{"name": "submit_final"}]},
                    {"step": "final_eval", "check_ok": True, "simulate_ok": True},
                ],
            },
            trajectory_path="artifacts/run/results.jsonl",
        )
        self.assertEqual(report["failure_category"], "passed")
        self.assertIn("Final status: PASS", report["report_markdown"])
        self.assertIn("submit_final", report["tool_call_sequence"])

    def test_report_classifies_provider_failure(self) -> None:
        report = build_repair_report(
            {
                "case_id": "case",
                "final_verdict": "FAILED",
                "submitted": False,
                "provider_error": "timeout",
                "steps": [],
            },
            provider_status="provider_unstable",
        )
        self.assertEqual(report["failure_category"], "provider_failure")


class NoWrapperRepairAuditV0366Tests(unittest.TestCase):
    def test_audit_passes_for_transparent_dispatch_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "transparent.py"
            path.write_text(
                "def dispatch_tool(name, arguments):\n"
                "    return run_diagnostic(name, arguments)\n",
                encoding="utf-8",
            )
            summary = build_no_wrapper_repair_audit([path])
        self.assertEqual(summary["status"], "PASS")
        self.assertFalse(summary["wrapper_repair_detected"])

    def test_audit_flags_deterministic_patch_function(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.py"
            path.write_text(
                "def generate_patch(model_text):\n"
                "    return model_text.replace('x', 'y')\n",
                encoding="utf-8",
            )
            summary = build_no_wrapper_repair_audit([path])
        self.assertEqual(summary["status"], "FAIL")
        self.assertTrue(summary["wrapper_repair_detected"])


class ReleaseReadinessGateV0367Tests(unittest.TestCase):
    def test_readiness_passes_when_all_checks_pass(self) -> None:
        summary = evaluate_release_readiness({name: True for name in READINESS_CHECKS})
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["readiness_status"], "readiness_complete")

    def test_readiness_reports_failed_checks(self) -> None:
        checks = {name: True for name in READINESS_CHECKS}
        checks["benchmark_blind"] = False
        summary = evaluate_release_readiness(checks)
        self.assertEqual(summary["status"], "REVIEW")
        self.assertIn("benchmark_blind", summary["failed_checks"])


class ReadinessCloseoutV0368Tests(unittest.TestCase):
    def test_closeout_passes_when_components_pass(self) -> None:
        summary = build_readiness_closeout(
            [
                {"version": "v0.36.1", "status": "PASS"},
                {"version": "v0.36.7", "status": "PASS", "readiness_status": "readiness_complete"},
            ]
        )
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["readiness_status"], "readiness_complete")

    def test_closeout_does_not_hide_open_gaps(self) -> None:
        summary = build_readiness_closeout([{"version": "v0.36.7", "status": "REVIEW"}])
        self.assertEqual(summary["status"], "REVIEW")
        self.assertEqual(summary["readiness_status"], "readiness_incomplete")


if __name__ == "__main__":
    unittest.main()
