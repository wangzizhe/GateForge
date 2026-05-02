from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_hard_candidate_intake_v0_37_1 import (
    build_candidate_intake_summary,
    infer_family,
    task_to_registry_seed,
)
from gateforge.agent_modelica_hard_family_balance_v0_37_3 import build_family_balance_summary
from gateforge.agent_modelica_hard_family_expansion_v0_37_4 import (
    build_arrayed_connector_flow_expansion_summary,
)
from gateforge.agent_modelica_hard_family_expansion_v0_37_7 import (
    build_replaceable_partial_expansion_summary,
)
from gateforge.agent_modelica_hard_family_expansion_v0_37_10 import (
    build_reusable_contract_expansion_summary,
)
from gateforge.agent_modelica_hard_family_registry_v0_37_0 import (
    REQUIRED_SEED_FIELDS,
    build_registry_summary,
    validate_registry_seed,
)
from gateforge.agent_modelica_hard_pool_closeout_v0_37_12 import build_hard_pool_closeout
from gateforge.agent_modelica_hard_pool_evidence_reconcile_v0_37_13 import (
    build_evidence_reconcile_summary,
    reconcile_seed_evidence,
)
from gateforge.agent_modelica_hard_pool_gate_v0_37_2 import (
    build_hard_pool_gate_summary,
    evaluate_seed_gate,
)
from gateforge.agent_modelica_hard_pool_leakage_triage_v0_37_14 import (
    build_leakage_triage_summary,
    triage_seed_leakage,
)
from gateforge.agent_modelica_hard_pool_repeatability_gate_v0_37_15 import (
    build_repeatability_gate_summary,
    evaluate_repeatability,
)
from gateforge.agent_modelica_known_hard_artifact_miner_v0_37_1 import (
    mine_known_hard_from_artifacts,
    mine_known_hard_from_results_jsonl,
    mine_known_hard_from_summary,
)


def _task(case_id: str = "sem_19_arrayed_shared_probe_bus") -> dict:
    return {
        "case_id": case_id,
        "task_type": "repair",
        "title": "Repair arrayed connector bus contract",
        "difficulty": "complex",
        "source_backed": True,
        "benchmark_focus": "model_check_structural",
        "description": "A reusable probe abstraction was migrated into an arrayed connector bus. Repair the model.",
        "constraints": ["Keep the model name unchanged.", "Preserve the reusable probe abstraction."],
        "initial_model": "model X\n  connector Pin\n    Real v;\n    flow Real i;\n  end Pin;\nend X;\n",
        "verification": {"check_model": True, "simulate": {"stop_time": 0.1, "intervals": 100}},
    }


def _seed(**updates: object) -> dict:
    seed = task_to_registry_seed(
        _task(),
        known_hard_for=["provider / model / base / 32k / v0.35.32"],
    )
    seed.update(
        {
            "blind_lint_status": "PASS",
            "admission_status": "admitted",
            "repeatability_status": "repeatable",
            "evidence_role": "formal_experiment",
            "registry_status": "repeatable_candidate",
        }
    )
    seed.update(updates)
    return seed


class HardFamilyRegistryV0370Tests(unittest.TestCase):
    def test_registry_seed_requires_known_hard_for_field(self) -> None:
        seed = _seed()
        self.assertEqual(validate_registry_seed(seed), [])
        self.assertIn("known_hard_for", REQUIRED_SEED_FIELDS)

    def test_registry_rejects_missing_known_hard_for(self) -> None:
        seed = _seed()
        del seed["known_hard_for"]
        self.assertIn("missing_required:known_hard_for", validate_registry_seed(seed))

    def test_registry_summary_counts_families_and_known_hard(self) -> None:
        summary = build_registry_summary([_seed()])
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["known_hard_seed_count"], 1)


class HardCandidateIntakeV0371Tests(unittest.TestCase):
    def test_infer_family_detects_arrayed_connector_flow(self) -> None:
        self.assertEqual(infer_family(_task()), "arrayed_connector_flow")

    def test_task_to_seed_carries_known_hard_for(self) -> None:
        seed = task_to_registry_seed(_task(), known_hard_for=["known hard config"])
        self.assertEqual(seed["known_hard_for"], ["known hard config"])
        self.assertEqual(validate_registry_seed(seed), [])

    def test_intake_summary_uses_known_hard_map(self) -> None:
        summary, seeds = build_candidate_intake_summary(
            [_task()],
            known_hard_by_case={"sem_19_arrayed_shared_probe_bus": ["provider / model / base / 32k"]},
        )
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["known_hard_seed_count"], 1)
        self.assertEqual(seeds[0]["known_hard_for"], ["provider / model / base / 32k"])


class KnownHardArtifactMinerV0371Tests(unittest.TestCase):
    def test_mines_stable_fail_cases_from_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "summary.json"
            path.write_text(
                json.dumps(
                    {
                        "version": "v0.fixture",
                        "provider_backend": "auto",
                        "tool_profile": "base",
                        "cases": [
                            {"case_id": "sem_19", "base_verdict": "FAILED", "structural_verdict": "FAILED"},
                            {"case_id": "sem_21", "base_verdict": "PASS", "structural_verdict": "PASS"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            mapping = mine_known_hard_from_summary(path)
        self.assertIn("sem_19", mapping)
        self.assertNotIn("sem_21", mapping)

    def test_mines_zero_pass_case_ids_without_provider_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "summary.json"
            path.write_text(
                json.dumps(
                    {
                        "version": "v0.fixture",
                        "case_count": 2,
                        "case_ids": ["a", "b"],
                        "pass_count": 0,
                        "provider_error_count": 0,
                        "load_error_count": 0,
                    }
                ),
                encoding="utf-8",
            )
            mapping = mine_known_hard_from_artifacts([path])
        self.assertEqual(sorted(mapping), ["a", "b"])

    def test_mines_failed_rows_from_results_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "case_id": "sem_22",
                        "provider": "provider",
                        "tool_profile": "base",
                        "final_verdict": "FAILED",
                        "provider_error": "",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            mapping = mine_known_hard_from_results_jsonl(path, fallback_summary={"version": "v0.fixture"})
        self.assertIn("sem_22", mapping)
        self.assertIn("provider", mapping["sem_22"][0])


class HardPoolGateV0372Tests(unittest.TestCase):
    def test_gate_accepts_blind_admitted_repeatable_seed(self) -> None:
        result = evaluate_seed_gate(_seed())
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["formal_benchmark_eligible"])

    def test_gate_rejects_leaky_prompt(self) -> None:
        result = evaluate_seed_gate(_seed(visible_task_description="The correct fix is to add one equation."))
        self.assertEqual(result["status"], "REVIEW")
        self.assertIn("prompt_leakage", result["blockers"])

    def test_gate_summary_counts_known_hard_seed(self) -> None:
        summary = build_hard_pool_gate_summary([_seed()])
        self.assertEqual(summary["formal_benchmark_eligible_count"], 1)
        self.assertEqual(summary["known_hard_seed_count"], 1)

    def test_gate_accepts_admitted_via_live_failure(self) -> None:
        result = evaluate_seed_gate(_seed(admission_status="admitted_via_live_failure"))
        self.assertEqual(result["status"], "PASS")


class HardFamilyBalanceV0373Tests(unittest.TestCase):
    def test_balance_reports_multiple_family_coverage(self) -> None:
        summary = build_family_balance_summary(
            [
                _seed(case_id="a", family="arrayed_connector_flow"),
                _seed(case_id="b", family="replaceable_partial_contract"),
            ],
            min_family_count=1,
        )
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(len(summary["eligible_family_counts"]), 2)

    def test_balance_reviews_single_dominant_family(self) -> None:
        summary = build_family_balance_summary([_seed(case_id="a"), _seed(case_id="b")])
        self.assertEqual(summary["status"], "REVIEW")


class HardPoolEvidenceReconcileV03713Tests(unittest.TestCase):
    def test_known_hard_seed_becomes_admitted_via_live_failure(self) -> None:
        seed = task_to_registry_seed(_task(), known_hard_for=["provider / model / base / 32k"])
        reconciled = reconcile_seed_evidence(seed)
        self.assertEqual(reconciled["admission_status"], "admitted_via_live_failure")
        self.assertEqual(reconciled["repeatability_status"], "repeatability_pending")
        self.assertEqual(reconciled["registry_status"], "admitted")

    def test_two_known_hard_entries_record_repeatability_evidence(self) -> None:
        seed = task_to_registry_seed(_task(), known_hard_for=["a", "b"])
        reconciled = reconcile_seed_evidence(seed)
        self.assertEqual(reconciled["repeatability_status"], "repeatability_evidence_present")

    def test_reconcile_summary_counts_known_hard(self) -> None:
        summary, seeds = build_evidence_reconcile_summary([task_to_registry_seed(_task(), known_hard_for=["a"])])
        self.assertEqual(summary["known_hard_seed_count"], 1)
        self.assertEqual(seeds[0]["admission_status"], "admitted_via_live_failure")


class HardPoolLeakageTriageV03714Tests(unittest.TestCase):
    def test_triage_keeps_blind_seed(self) -> None:
        result = triage_seed_leakage(_seed())
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["recommended_action"], "keep")

    def test_triage_flags_leaky_seed(self) -> None:
        result = triage_seed_leakage(_seed(visible_task_description="Fix by adding the missing equation."))
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["recommended_action"], "rewrite_prompt_or_reject")

    def test_triage_summary_lists_leaking_cases(self) -> None:
        summary = build_leakage_triage_summary(
            [_seed(case_id="ok"), _seed(case_id="bad", visible_task_description="The root cause is a missing equation.")]
        )
        self.assertEqual(summary["status"], "REVIEW")
        self.assertEqual(summary["leaking_case_ids"], ["bad"])


class HardPoolRepeatabilityGateV03715Tests(unittest.TestCase):
    def test_repeatability_passes_same_profile_repeated_evidence(self) -> None:
        result = evaluate_repeatability(
            _seed(
                known_hard_for=[
                    "provider / model / base / 32k / run1",
                    "provider / model / base / 32k / run2",
                ]
            )
        )
        self.assertEqual(result["repeatability_status"], "repeatable_known_hard")
        self.assertTrue(result["formal_repeatability_passed"])

    def test_cross_profile_evidence_is_not_formal_repeatability(self) -> None:
        result = evaluate_repeatability(
            _seed(
                known_hard_for=[
                    "provider / model / base / 32k / run1",
                    "provider / model / structural / 32k / run2",
                ]
            )
        )
        self.assertEqual(result["repeatability_status"], "cross_profile_hard_evidence")
        self.assertFalse(result["formal_repeatability_passed"])

    def test_repeatability_summary_updates_seed_status(self) -> None:
        summary, seeds = build_repeatability_gate_summary(
            [
                _seed(
                    registry_status="admitted",
                    known_hard_for=[
                        "provider / model / base / 32k / run1",
                        "provider / model / base / 32k / run2",
                    ],
                )
            ]
        )
        self.assertEqual(summary["repeatability_pass_count"], 1)
        self.assertEqual(seeds[0]["repeatability_status"], "repeatable")
        self.assertEqual(seeds[0]["registry_status"], "repeatable_candidate")


class HardFamilyExpansionV037xTests(unittest.TestCase):
    def test_arrayed_expansion_selects_sem_cases(self) -> None:
        summary = build_arrayed_connector_flow_expansion_summary([_seed()])
        self.assertEqual(summary["status"], "PASS")
        self.assertIn("sem_19_arrayed_shared_probe_bus", summary["case_ids"])

    def test_replaceable_expansion_selects_partial_cases(self) -> None:
        summary = build_replaceable_partial_expansion_summary(
            [_seed(case_id="repl_01_probe_flow_missing", visible_task_description="Repair partial constrainedby contract.")]
        )
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["candidate_count"], 1)

    def test_reusable_contract_expansion_selects_adapter_cases(self) -> None:
        summary = build_reusable_contract_expansion_summary(
            [_seed(case_id="adapter_01", visible_task_description="Repair reusable adapter monitor contract.")]
        )
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["candidate_count"], 1)


class HardPoolCloseoutV03712Tests(unittest.TestCase):
    def test_closeout_exposes_v038_ready_case_ids(self) -> None:
        seed = _seed()
        summary = build_hard_pool_closeout(
            [seed],
            {"status": "PASS"},
            [{"version": "v0.37.4", "status": "PASS"}],
        )
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["v0_38_ready_case_ids"], ["sem_19_arrayed_shared_probe_bus"])


if __name__ == "__main__":
    unittest.main()
