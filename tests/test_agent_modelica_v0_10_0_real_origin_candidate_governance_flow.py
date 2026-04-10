from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_10_0_candidate_validator import evaluate_candidate_row
from gateforge.agent_modelica_v0_10_0_closeout import build_v1000_closeout
from gateforge.agent_modelica_v0_10_0_depth_probe import build_v1000_depth_probe
from gateforge.agent_modelica_v0_10_0_governance_pack import build_seed_candidate_rows, build_v1000_governance_pack
from gateforge.agent_modelica_v0_10_0_handoff_integrity import build_v1000_handoff_integrity


def _write_v097_closeout(
    path: Path,
    *,
    version_decision: str = "v0_9_phase_nearly_complete_with_explicit_caveat",
) -> None:
    payload = {
        "conclusion": {
            "version_decision": version_decision,
            "phase_status": "nearly_complete",
            "phase_stop_condition_status": "met",
            "explicit_caveat_label": "expanded_workflow_readiness_remains_partial_rather_than_supported_even_after_authenticity_constrained_barrier_aware_expansion",
            "next_primary_phase_question": "real_origin_workflow_readiness_evaluation",
            "do_not_continue_v0_9_same_authentic_expansion_by_default": True,
            "next_phase_handoff_mode": "start_next_phase_with_explicit_v0_9_caveat",
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class AgentModelicaV1000RealOriginCandidateGovernanceFlowTests(unittest.TestCase):
    def test_handoff_integrity_passes_on_expected_v097_closeout(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v097 = root / "v097" / "summary.json"
            _write_v097_closeout(v097)
            payload = build_v1000_handoff_integrity(v097_closeout_path=str(v097), out_dir=str(root / "handoff"))
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_workflow_proximal_proxy_candidate_is_rejected(self) -> None:
        candidate = {
            "task_id": "proxy_case",
            "source_id": "proxy_source",
            "family_id": "proxy_family",
            "workflow_task_template_id": "proxy_task",
            "complexity_tier": "medium",
            "real_origin_authenticity_audit": {
                "source_provenance": "proxy_source",
                "source_origin_class": "workflow_proximal_proxy",
                "real_origin_distance": "far",
                "workflow_legitimacy_pass": True,
                "real_origin_authenticity_pass": False,
                "real_origin_authenticity_audit_pass": False,
            },
            "anti_proxy_leakage_audit": {
                "proxy_leakage_risk_present": True,
                "proxy_leakage_risk_level": "high",
                "why_this_task_is_or_is_not_just_a_repackaged_workflow_proximal_task": "Known proxy carry-over.",
                "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding": True,
                "anti_proxy_leakage_audit_pass": False,
            },
        }
        result = evaluate_candidate_row(candidate)
        self.assertFalse(result["admitted"])
        self.assertIn("reject_workflow_proximal_proxy_class", result["rejection_reasons"])

    def test_real_origin_with_far_distance_is_rejected(self) -> None:
        candidate = {
            "task_id": "contradictory_case",
            "source_id": "source",
            "family_id": "family",
            "workflow_task_template_id": "task",
            "complexity_tier": "medium",
            "real_origin_authenticity_audit": {
                "source_provenance": "source",
                "source_origin_class": "real_origin",
                "real_origin_distance": "far",
                "workflow_legitimacy_pass": True,
                "real_origin_authenticity_pass": True,
                "real_origin_authenticity_audit_pass": False,
            },
            "anti_proxy_leakage_audit": {
                "proxy_leakage_risk_present": True,
                "proxy_leakage_risk_level": "medium",
                "why_this_task_is_or_is_not_just_a_repackaged_workflow_proximal_task": "Still too extractive.",
                "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding": False,
                "anti_proxy_leakage_audit_pass": True,
            },
        }
        result = evaluate_candidate_row(candidate)
        self.assertFalse(result["admitted"])
        self.assertIn("reject_internal_origin_distance_contradiction", result["rejection_reasons"])

    def test_semi_real_origin_candidate_is_admitted_but_not_counted_mainline(self) -> None:
        candidate = {
            "task_id": "semi_real_case",
            "source_id": "semi_source",
            "family_id": "family",
            "workflow_task_template_id": "task",
            "complexity_tier": "medium",
            "real_origin_authenticity_audit": {
                "source_provenance": "semi_source",
                "source_origin_class": "semi_real_origin",
                "real_origin_distance": "medium",
                "workflow_legitimacy_pass": True,
                "real_origin_authenticity_pass": True,
                "real_origin_authenticity_audit_pass": True,
            },
            "anti_proxy_leakage_audit": {
                "proxy_leakage_risk_present": True,
                "proxy_leakage_risk_level": "medium",
                "why_this_task_is_or_is_not_just_a_repackaged_workflow_proximal_task": "Semi-real source remains admissible only as a side bucket.",
                "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding": False,
                "anti_proxy_leakage_audit_pass": True,
            },
        }
        result = evaluate_candidate_row(candidate)
        self.assertTrue(result["admitted"])
        self.assertFalse(result["mainline_counted"])

    def test_governance_pack_builds_seed_pool(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            payload = build_v1000_governance_pack(out_dir=str(root / "governance"))
            self.assertEqual(payload["real_origin_candidate_pool_total_count"], len(build_seed_candidate_rows()))

    def test_depth_probe_marks_default_real_origin_pool_as_partial(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build_v1000_governance_pack(out_dir=str(root / "governance"))
            probe = build_v1000_depth_probe(
                governance_pack_path=str(root / "governance" / "summary.json"),
                out_dir=str(root / "probe"),
            )
            self.assertEqual(probe["real_origin_candidate_governance_status"], "governance_partial")
            self.assertEqual(probe["mainline_real_origin_candidate_count"], 6)
            self.assertTrue(probe["needs_additional_real_origin_sources"])

    def test_closeout_routes_to_partial_for_default_real_origin_pool(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v097 = root / "v097" / "summary.json"
            _write_v097_closeout(v097)
            payload = build_v1000_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                governance_pack_path=str(root / "governance" / "summary.json"),
                depth_probe_path=str(root / "probe" / "summary.json"),
                v097_closeout_path=str(v097),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_10_0_real_origin_candidate_governance_partial")
            self.assertEqual(
                payload["conclusion"]["v0_10_1_handoff_mode"],
                "expand_real_origin_candidate_pool_before_substrate_freeze",
            )

    def test_closeout_routes_to_ready_when_promoted_floor_is_met(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v097 = root / "v097" / "summary.json"
            _write_v097_closeout(v097)
            governance_path = root / "governance" / "summary.json"
            rows = []
            for idx in range(12):
                source_id = ["s1", "s2", "s3"][idx % 3]
                family_id = ["f1", "f2", "f3"][idx % 3]
                rows.append(
                    {
                        "task_id": f"t{idx}",
                        "source_id": source_id,
                        "family_id": family_id,
                        "workflow_task_template_id": "task",
                        "complexity_tier": "medium",
                        "real_origin_authenticity_audit": {
                            "source_provenance": source_id,
                            "source_origin_class": "real_origin",
                            "real_origin_distance": "near",
                            "workflow_legitimacy_pass": True,
                            "real_origin_authenticity_pass": True,
                            "real_origin_authenticity_audit_pass": True,
                        },
                        "anti_proxy_leakage_audit": {
                            "proxy_leakage_risk_present": False,
                            "proxy_leakage_risk_level": "low",
                            "why_this_task_is_or_is_not_just_a_repackaged_workflow_proximal_task": "Direct source.",
                            "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding": False,
                            "anti_proxy_leakage_audit_pass": True,
                        },
                    }
                )
            governance_path.parent.mkdir(parents=True, exist_ok=True)
            governance_path.write_text(json.dumps({"baseline_candidate_rows": rows}), encoding="utf-8")
            payload = build_v1000_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                governance_pack_path=str(governance_path),
                depth_probe_path=str(root / "probe" / "summary.json"),
                v097_closeout_path=str(v097),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_10_0_real_origin_candidate_governance_ready")
            self.assertEqual(
                payload["conclusion"]["v0_10_1_handoff_mode"],
                "freeze_first_real_origin_workflow_substrate",
            )

    def test_closeout_returns_invalid_on_bad_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v097 = root / "v097" / "summary.json"
            _write_v097_closeout(v097, version_decision="v0_9_phase_not_ready_for_closeout")
            payload = build_v1000_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                governance_pack_path=str(root / "governance" / "summary.json"),
                depth_probe_path=str(root / "probe" / "summary.json"),
                v097_closeout_path=str(v097),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_10_0_handoff_candidate_inputs_invalid")


if __name__ == "__main__":
    unittest.main()
