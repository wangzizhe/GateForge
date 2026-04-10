from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_10_1_candidate_source_admission import build_v101_candidate_source_admission
from gateforge.agent_modelica_v0_10_1_closeout import build_v101_closeout
from gateforge.agent_modelica_v0_10_1_handoff_integrity import build_v101_handoff_integrity
from gateforge.agent_modelica_v0_10_1_pool_delta_and_diversity_report import (
    build_v101_pool_delta_and_diversity_report,
)


def _write_v1000_closeout(
    path: Path,
    *,
    version_decision: str = "v0_10_0_real_origin_candidate_governance_partial",
    mainline_count: int = 6,
    max_single_source_share_pct: float = 66.7,
) -> None:
    payload = {
        "conclusion": {
            "version_decision": version_decision,
            "real_origin_candidate_governance_status": "governance_partial",
            "mainline_real_origin_candidate_count": mainline_count,
            "candidate_depth_by_source_origin_class": {
                "real_origin": mainline_count,
                "semi_real_origin": 1,
                "workflow_proximal_proxy": 0,
            },
            "max_single_source_share_pct": max_single_source_share_pct,
            "needs_additional_real_origin_sources": True,
            "v0_10_1_handoff_mode": "expand_real_origin_candidate_pool_before_substrate_freeze",
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _baseline_v1000_rows() -> list[dict]:
    return [
        {
            "task_id": "baseline_buildings_1",
            "source_id": "open_source_issue_archive_buildings",
            "family_id": "control_library_maintenance",
            "workflow_task_template_id": "task",
            "complexity_tier": "medium",
            "real_origin_authenticity_audit": {
                "source_provenance": "buildings_1",
                "source_origin_class": "real_origin",
                "real_origin_distance": "near",
                "workflow_legitimacy_pass": True,
                "real_origin_authenticity_pass": True,
                "real_origin_authenticity_audit_pass": True,
            },
            "anti_proxy_leakage_audit": {
                "proxy_leakage_risk_present": False,
                "proxy_leakage_risk_level": "low",
                "why_this_task_is_or_is_not_just_a_repackaged_workflow_proximal_task": "Direct issue-linked row.",
                "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding": False,
                "anti_proxy_leakage_audit_pass": True,
            },
        },
        {
            "task_id": "baseline_buildings_2",
            "source_id": "open_source_issue_archive_buildings",
            "family_id": "controller_reset_maintenance",
            "workflow_task_template_id": "task",
            "complexity_tier": "medium",
            "real_origin_authenticity_audit": {
                "source_provenance": "buildings_2",
                "source_origin_class": "real_origin",
                "real_origin_distance": "near",
                "workflow_legitimacy_pass": True,
                "real_origin_authenticity_pass": True,
                "real_origin_authenticity_audit_pass": True,
            },
            "anti_proxy_leakage_audit": {
                "proxy_leakage_risk_present": False,
                "proxy_leakage_risk_level": "low",
                "why_this_task_is_or_is_not_just_a_repackaged_workflow_proximal_task": "Direct issue-linked row.",
                "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding": False,
                "anti_proxy_leakage_audit_pass": True,
            },
        },
        {
            "task_id": "baseline_msl_1",
            "source_id": "open_source_issue_archive_msl",
            "family_id": "multibody_constraint_maintenance",
            "workflow_task_template_id": "task",
            "complexity_tier": "medium",
            "real_origin_authenticity_audit": {
                "source_provenance": "msl_1",
                "source_origin_class": "real_origin",
                "real_origin_distance": "medium",
                "workflow_legitimacy_pass": True,
                "real_origin_authenticity_pass": True,
                "real_origin_authenticity_audit_pass": True,
            },
            "anti_proxy_leakage_audit": {
                "proxy_leakage_risk_present": True,
                "proxy_leakage_risk_level": "medium",
                "why_this_task_is_or_is_not_just_a_repackaged_workflow_proximal_task": "Issue-linked row.",
                "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding": False,
                "anti_proxy_leakage_audit_pass": True,
            },
        },
        {
            "task_id": "baseline_msl_2",
            "source_id": "open_source_issue_archive_msl",
            "family_id": "conversion_compatibility_maintenance",
            "workflow_task_template_id": "task",
            "complexity_tier": "simple",
            "real_origin_authenticity_audit": {
                "source_provenance": "msl_2",
                "source_origin_class": "real_origin",
                "real_origin_distance": "medium",
                "workflow_legitimacy_pass": True,
                "real_origin_authenticity_pass": True,
                "real_origin_authenticity_audit_pass": True,
            },
            "anti_proxy_leakage_audit": {
                "proxy_leakage_risk_present": True,
                "proxy_leakage_risk_level": "medium",
                "why_this_task_is_or_is_not_just_a_repackaged_workflow_proximal_task": "Issue-linked row.",
                "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding": False,
                "anti_proxy_leakage_audit_pass": True,
            },
        },
        {
            "task_id": "baseline_msl_3",
            "source_id": "open_source_issue_archive_msl",
            "family_id": "conversion_compatibility_maintenance",
            "workflow_task_template_id": "task",
            "complexity_tier": "simple",
            "real_origin_authenticity_audit": {
                "source_provenance": "msl_3",
                "source_origin_class": "real_origin",
                "real_origin_distance": "medium",
                "workflow_legitimacy_pass": True,
                "real_origin_authenticity_pass": True,
                "real_origin_authenticity_audit_pass": True,
            },
            "anti_proxy_leakage_audit": {
                "proxy_leakage_risk_present": True,
                "proxy_leakage_risk_level": "medium",
                "why_this_task_is_or_is_not_just_a_repackaged_workflow_proximal_task": "Issue-linked row.",
                "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding": False,
                "anti_proxy_leakage_audit_pass": True,
            },
        },
        {
            "task_id": "baseline_msl_4",
            "source_id": "open_source_issue_archive_msl",
            "family_id": "conversion_compatibility_maintenance",
            "workflow_task_template_id": "task",
            "complexity_tier": "simple",
            "real_origin_authenticity_audit": {
                "source_provenance": "msl_4",
                "source_origin_class": "real_origin",
                "real_origin_distance": "medium",
                "workflow_legitimacy_pass": True,
                "real_origin_authenticity_pass": True,
                "real_origin_authenticity_audit_pass": True,
            },
            "anti_proxy_leakage_audit": {
                "proxy_leakage_risk_present": True,
                "proxy_leakage_risk_level": "medium",
                "why_this_task_is_or_is_not_just_a_repackaged_workflow_proximal_task": "Issue-linked row.",
                "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding": False,
                "anti_proxy_leakage_audit_pass": True,
            },
        },
        {
            "task_id": "baseline_semi",
            "source_id": "semi_real_maintenance_digest",
            "family_id": "maintenance_regression_followup",
            "workflow_task_template_id": "task",
            "complexity_tier": "medium",
            "real_origin_authenticity_audit": {
                "source_provenance": "semi",
                "source_origin_class": "semi_real_origin",
                "real_origin_distance": "medium",
                "workflow_legitimacy_pass": True,
                "real_origin_authenticity_pass": True,
                "real_origin_authenticity_audit_pass": True,
            },
            "anti_proxy_leakage_audit": {
                "proxy_leakage_risk_present": True,
                "proxy_leakage_risk_level": "medium",
                "why_this_task_is_or_is_not_just_a_repackaged_workflow_proximal_task": "Semi-real side bucket row.",
                "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding": False,
                "anti_proxy_leakage_audit_pass": True,
            },
        },
    ]


def _write_v1000_governance_pack(path: Path) -> None:
    payload = {"baseline_candidate_rows": _baseline_v1000_rows()}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class AgentModelicaV101RealOriginSourceExpansionFlowTests(unittest.TestCase):
    def test_handoff_integrity_passes_on_expected_v1000_closeout(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v1000 = root / "v1000" / "summary.json"
            _write_v1000_closeout(v1000)
            payload = build_v101_handoff_integrity(v1000_closeout_path=str(v1000), out_dir=str(root / "handoff"))
            self.assertEqual(payload["handoff_integrity_status"], "PASS")
            self.assertEqual(payload["upstream_mainline_real_origin_candidate_count"], 6)

    def test_source_admission_admits_real_source_and_rejects_proxy(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            payload = build_v101_candidate_source_admission(out_dir=str(root / "admission"))
            self.assertEqual(payload["real_origin_source_expansion_ledger"]["admitted_real_origin_source_count"], 1)
            rejected = {
                row["source_id"]: row["source_rejection_reason"] for row in payload["source_admission_decision_table"]
            }
            self.assertEqual(rejected["proxy_repackaged_v09_digest"], "source_is_workflow_proximal_proxy")

    def test_semi_real_source_is_recorded_but_not_counted_mainline(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            payload = build_v101_candidate_source_admission(out_dir=str(root / "admission"))
            rows = {row["source_id"]: row for row in payload["source_admission_decision_table"]}
            self.assertTrue(rows["semi_real_origin_comment_digest"]["source_admission_pass"])
            self.assertEqual(rows["semi_real_origin_comment_digest"]["mainline_real_origin_candidate_count"], 0)

    def test_pool_delta_marks_default_expansion_as_partial(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v1000 = root / "v1000" / "summary.json"
            governance = root / "governance" / "summary.json"
            _write_v1000_closeout(v1000)
            _write_v1000_governance_pack(governance)
            build_v101_candidate_source_admission(out_dir=str(root / "admission"))
            payload = build_v101_pool_delta_and_diversity_report(
                v1000_closeout_path=str(v1000),
                v1000_governance_pack_path=str(governance),
                source_admission_path=str(root / "admission" / "summary.json"),
                out_dir=str(root / "pool"),
            )
            self.assertEqual(payload["real_origin_source_expansion_status"], "expansion_partial")
            self.assertEqual(payload["post_expansion_mainline_real_origin_candidate_count"], 10)
            self.assertEqual(payload["max_single_source_share_pct"], 40.0)

    def test_closeout_routes_to_partial_for_default_expansion(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v1000 = root / "v1000" / "summary.json"
            governance = root / "governance" / "summary.json"
            _write_v1000_closeout(v1000)
            _write_v1000_governance_pack(governance)
            payload = build_v101_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                source_admission_path=str(root / "admission" / "summary.json"),
                pool_delta_path=str(root / "pool" / "summary.json"),
                v1000_closeout_path=str(v1000),
                v1000_governance_pack_path=str(governance),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_10_1_real_origin_source_expansion_partial")
            self.assertEqual(payload["conclusion"]["v0_10_2_handoff_mode"], "continue_expanding_real_origin_candidate_pool")

    def test_closeout_routes_to_ready_when_promoted_floor_is_met(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v1000 = root / "v1000" / "summary.json"
            governance = root / "governance" / "summary.json"
            admission = root / "admission" / "summary.json"
            _write_v1000_closeout(v1000)
            _write_v1000_governance_pack(governance)
            admission_payload = {
                "candidate_source_intake_table": [
                    {
                        "source_id": "new_real_source",
                        "source_origin_class": "real_origin",
                        "source_admission_pass": True,
                        "mainline_real_origin_candidate_count": 6,
                        "governance_passing_candidate_count": 6,
                        "candidate_rows": [
                            {
                                "task_id": f"new_real_{idx}",
                                "source_id": "new_real_source",
                                "family_id": family,
                                "workflow_task_template_id": "task",
                                "complexity_tier": "medium",
                                "real_origin_authenticity_audit": {
                                    "source_provenance": "new_real_source",
                                    "source_origin_class": "real_origin",
                                    "real_origin_distance": "near",
                                    "workflow_legitimacy_pass": True,
                                    "real_origin_authenticity_pass": True,
                                    "real_origin_authenticity_audit_pass": True,
                                },
                                "anti_proxy_leakage_audit": {
                                    "proxy_leakage_risk_present": False,
                                    "proxy_leakage_risk_level": "low",
                                    "why_this_task_is_or_is_not_just_a_repackaged_workflow_proximal_task": "Direct real-origin source.",
                                    "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding": False,
                                    "anti_proxy_leakage_audit_pass": True,
                                },
                            }
                            for idx, family in enumerate(
                                [
                                    "refrigerant_interface_maintenance",
                                    "refrigerant_validation_maintenance",
                                    "interface_compatibility_maintenance",
                                    "refrigerant_validation_maintenance",
                                    "refrigerant_interface_maintenance",
                                    "interface_compatibility_maintenance",
                                ]
                            )
                        ],
                    }
                ]
            }
            admission.parent.mkdir(parents=True, exist_ok=True)
            admission.write_text(json.dumps(admission_payload), encoding="utf-8")
            payload = build_v101_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                source_admission_path=str(admission),
                pool_delta_path=str(root / "pool" / "summary.json"),
                v1000_closeout_path=str(v1000),
                v1000_governance_pack_path=str(governance),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_10_1_real_origin_source_expansion_ready")
            self.assertEqual(payload["conclusion"]["v0_10_2_handoff_mode"], "freeze_first_real_origin_workflow_substrate")

    def test_closeout_returns_invalid_on_bad_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v1000 = root / "v1000" / "summary.json"
            governance = root / "governance" / "summary.json"
            _write_v1000_closeout(v1000, version_decision="v0_10_0_handoff_candidate_inputs_invalid")
            _write_v1000_governance_pack(governance)
            payload = build_v101_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                source_admission_path=str(root / "admission" / "summary.json"),
                pool_delta_path=str(root / "pool" / "summary.json"),
                v1000_closeout_path=str(v1000),
                v1000_governance_pack_path=str(governance),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_10_1_source_expansion_inputs_invalid")


if __name__ == "__main__":
    unittest.main()
