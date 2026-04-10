from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_10_2_candidate_source_admission import build_v102_candidate_source_admission
from gateforge.agent_modelica_v0_10_2_closeout import build_v102_closeout
from gateforge.agent_modelica_v0_10_2_handoff_integrity import build_v102_handoff_integrity
from gateforge.agent_modelica_v0_10_2_pool_delta_and_diversity_report import (
    build_v102_pool_delta_and_diversity_report,
)


def _row(
    task_id: str,
    source_id: str,
    family_id: str,
    *,
    source_origin_class: str = "real_origin",
    real_origin_distance: str = "near",
) -> dict:
    return {
        "task_id": task_id,
        "source_id": source_id,
        "family_id": family_id,
        "workflow_task_template_id": "task",
        "complexity_tier": "medium",
        "real_origin_authenticity_audit": {
            "source_provenance": task_id,
            "source_origin_class": source_origin_class,
            "real_origin_distance": real_origin_distance,
            "workflow_legitimacy_pass": True,
            "real_origin_authenticity_pass": source_origin_class != "workflow_proximal_proxy",
            "real_origin_authenticity_audit_pass": source_origin_class != "workflow_proximal_proxy",
        },
        "anti_proxy_leakage_audit": {
            "proxy_leakage_risk_present": source_origin_class != "real_origin",
            "proxy_leakage_risk_level": "medium" if source_origin_class != "real_origin" else "low",
            "why_this_task_is_or_is_not_just_a_repackaged_workflow_proximal_task": "Fixture row.",
            "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding": source_origin_class == "workflow_proximal_proxy",
            "anti_proxy_leakage_audit_pass": source_origin_class != "workflow_proximal_proxy",
        },
    }


def _baseline_v101_pool_rows() -> list[dict]:
    rows = [
        _row("buildings_1", "open_source_issue_archive_buildings", "control_library_maintenance"),
        _row("buildings_2", "open_source_issue_archive_buildings", "controller_reset_maintenance"),
        _row("msl_1", "open_source_issue_archive_msl", "multibody_constraint_maintenance", real_origin_distance="medium"),
        _row("msl_2", "open_source_issue_archive_msl", "conversion_compatibility_maintenance", real_origin_distance="medium"),
        _row("msl_3", "open_source_issue_archive_msl", "conversion_compatibility_maintenance", real_origin_distance="medium"),
        _row("msl_4", "open_source_issue_archive_msl", "conversion_compatibility_maintenance", real_origin_distance="medium"),
        _row("aixlib_1", "open_source_issue_archive_aixlib", "refrigerant_interface_maintenance", real_origin_distance="medium"),
        _row("aixlib_2", "open_source_issue_archive_aixlib", "refrigerant_validation_maintenance", real_origin_distance="medium"),
        _row("aixlib_3", "open_source_issue_archive_aixlib", "refrigerant_validation_maintenance", real_origin_distance="medium"),
        _row("aixlib_4", "open_source_issue_archive_aixlib", "interface_compatibility_maintenance"),
        _row(
            "semi_1",
            "semi_real_origin_comment_digest",
            "maintenance_regression_followup",
            source_origin_class="semi_real_origin",
            real_origin_distance="medium",
        ),
        _row(
            "semi_2",
            "semi_real_origin_comment_digest",
            "documentation_sync_followup",
            source_origin_class="semi_real_origin",
            real_origin_distance="medium",
        ),
        _row(
            "semi_3",
            "semi_real_origin_comment_digest",
            "review_followup_only",
            source_origin_class="semi_real_origin",
            real_origin_distance="medium",
        ),
    ]
    return rows


def _write_v101_closeout(
    path: Path,
    *,
    version_decision: str = "v0_10_1_real_origin_source_expansion_partial",
    mainline_count: int = 10,
    max_single_source_share_pct: float = 40.0,
) -> None:
    payload = {
        "conclusion": {
            "version_decision": version_decision,
            "real_origin_source_expansion_status": "expansion_partial",
            "post_expansion_mainline_real_origin_candidate_count": mainline_count,
            "candidate_depth_by_source_origin_class": {
                "real_origin": mainline_count,
                "semi_real_origin": 3,
                "workflow_proximal_proxy": 0,
            },
            "max_single_source_share_pct": max_single_source_share_pct,
            "needs_additional_real_origin_sources": True,
            "v0_10_2_handoff_mode": "continue_expanding_real_origin_candidate_pool",
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_v101_pool_delta(path: Path, *, rows: list[dict] | None = None) -> None:
    payload = {
        "post_expansion_candidate_pool": rows if rows is not None else _baseline_v101_pool_rows(),
        "max_single_source_share_pct": 40.0,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class AgentModelicaV102RealOriginSourceExpansionFlowTests(unittest.TestCase):
    def test_handoff_integrity_passes_on_expected_v101_closeout(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v101 = root / "v101" / "summary.json"
            _write_v101_closeout(v101)
            payload = build_v102_handoff_integrity(v101_closeout_path=str(v101), out_dir=str(root / "handoff"))
            self.assertEqual(payload["handoff_integrity_status"], "PASS")
            self.assertEqual(payload["upstream_mainline_real_origin_candidate_count"], 10)

    def test_source_admission_admits_new_real_source_and_rejects_proxy(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            payload = build_v102_candidate_source_admission(out_dir=str(root / "admission"))
            self.assertEqual(payload["real_origin_source_expansion_ledger"]["admitted_real_origin_source_count"], 1)
            rows = {row["source_id"]: row for row in payload["source_admission_decision_table"]}
            self.assertTrue(rows["semi_real_origin_review_digest"]["source_admission_pass"])
            self.assertEqual(rows["semi_real_origin_review_digest"]["mainline_real_origin_candidate_count"], 0)
            self.assertEqual(rows["proxy_repackaged_v10_digest"]["source_rejection_reason"], "source_is_workflow_proximal_proxy")

    def test_pool_delta_marks_default_expansion_as_ready(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v101_closeout = root / "v101_closeout" / "summary.json"
            v101_pool = root / "v101_pool" / "summary.json"
            _write_v101_closeout(v101_closeout)
            _write_v101_pool_delta(v101_pool)
            build_v102_candidate_source_admission(out_dir=str(root / "admission"))
            payload = build_v102_pool_delta_and_diversity_report(
                v101_closeout_path=str(v101_closeout),
                v101_pool_delta_path=str(v101_pool),
                source_admission_path=str(root / "admission" / "summary.json"),
                out_dir=str(root / "pool"),
            )
            self.assertEqual(payload["real_origin_source_expansion_status"], "expansion_ready")
            self.assertEqual(payload["post_expansion_mainline_real_origin_candidate_count"], 12)
            self.assertEqual(payload["max_single_source_share_pct"], 33.3)

    def test_closeout_routes_to_ready_for_default_expansion(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v101_closeout = root / "v101_closeout" / "summary.json"
            v101_pool = root / "v101_pool" / "summary.json"
            _write_v101_closeout(v101_closeout)
            _write_v101_pool_delta(v101_pool)
            payload = build_v102_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                source_admission_path=str(root / "admission" / "summary.json"),
                pool_delta_path=str(root / "pool" / "summary.json"),
                v101_closeout_path=str(v101_closeout),
                v101_pool_delta_path=str(v101_pool),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_10_2_real_origin_source_expansion_ready")
            self.assertEqual(payload["conclusion"]["v0_10_3_handoff_mode"], "freeze_first_real_origin_workflow_substrate")

    def test_closeout_routes_to_partial_when_growth_is_real_but_below_promoted_floor(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v101_closeout = root / "v101_closeout" / "summary.json"
            v101_pool = root / "v101_pool" / "summary.json"
            pool_delta = root / "pool" / "summary.json"
            _write_v101_closeout(v101_closeout)
            _write_v101_pool_delta(v101_pool)
            pool_delta.parent.mkdir(parents=True, exist_ok=True)
            pool_delta.write_text(
                json.dumps(
                    {
                        "real_origin_source_expansion_status": "expansion_partial",
                        "post_expansion_mainline_real_origin_candidate_count": 11,
                        "candidate_depth_by_workflow_family": {
                            "control_library_maintenance": 1,
                            "conversion_compatibility_maintenance": 3,
                            "interface_compatibility_maintenance": 1,
                        },
                        "candidate_depth_by_source_origin_class": {
                            "real_origin": 11,
                            "semi_real_origin": 3,
                            "workflow_proximal_proxy": 0,
                        },
                        "max_single_source_share_pct": 36.4,
                        "needs_additional_real_origin_sources": True,
                    }
                ),
                encoding="utf-8",
            )
            payload = build_v102_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                source_admission_path=str(root / "admission" / "summary.json"),
                pool_delta_path=str(pool_delta),
                v101_closeout_path=str(v101_closeout),
                v101_pool_delta_path=str(v101_pool),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_10_2_real_origin_source_expansion_partial")
            self.assertEqual(payload["conclusion"]["v0_10_3_handoff_mode"], "continue_expanding_real_origin_candidate_pool")

    def test_closeout_returns_invalid_on_bad_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v101_closeout = root / "v101_closeout" / "summary.json"
            v101_pool = root / "v101_pool" / "summary.json"
            _write_v101_closeout(v101_closeout, version_decision="v0_10_1_source_expansion_inputs_invalid")
            _write_v101_pool_delta(v101_pool)
            payload = build_v102_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                source_admission_path=str(root / "admission" / "summary.json"),
                pool_delta_path=str(root / "pool" / "summary.json"),
                v101_closeout_path=str(v101_closeout),
                v101_pool_delta_path=str(v101_pool),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_10_2_source_expansion_inputs_invalid")


if __name__ == "__main__":
    unittest.main()
