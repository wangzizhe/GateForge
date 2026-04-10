from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_10_3_closeout import build_v103_closeout
from gateforge.agent_modelica_v0_10_3_handoff_integrity import build_v103_handoff_integrity
from gateforge.agent_modelica_v0_10_3_real_origin_substrate_admission import build_v103_real_origin_substrate_admission
from gateforge.agent_modelica_v0_10_3_real_origin_substrate_builder import build_v103_real_origin_substrate_builder


def _row(
    task_id: str,
    source_id: str,
    family_id: str,
    *,
    source_origin_class: str = "real_origin",
    real_origin_distance: str = "near",
    complexity_tier: str = "medium",
) -> dict:
    auth_pass = source_origin_class != "workflow_proximal_proxy" and real_origin_distance != "far"
    anti_proxy_pass = source_origin_class != "workflow_proximal_proxy"
    return {
        "task_id": task_id,
        "source_id": source_id,
        "source_record_id": f"{task_id}_record",
        "family_id": family_id,
        "workflow_task_template_id": "task",
        "complexity_tier": complexity_tier,
        "real_origin_authenticity_audit": {
            "source_provenance": f"{task_id}_prov",
            "source_origin_class": source_origin_class,
            "real_origin_distance": real_origin_distance,
            "workflow_legitimacy_pass": True,
            "real_origin_authenticity_pass": auth_pass,
            "real_origin_authenticity_audit_pass": auth_pass,
        },
        "anti_proxy_leakage_audit": {
            "proxy_leakage_risk_present": source_origin_class != "real_origin",
            "proxy_leakage_risk_level": "medium" if source_origin_class != "real_origin" else "low",
            "why_this_task_is_or_is_not_just_a_repackaged_workflow_proximal_task": "Fixture row.",
            "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding": source_origin_class == "workflow_proximal_proxy",
            "anti_proxy_leakage_audit_pass": anti_proxy_pass,
        },
    }


def _write_v102_closeout(path: Path, *, version_decision: str = "v0_10_2_real_origin_source_expansion_ready") -> None:
    payload = {
        "conclusion": {
            "version_decision": version_decision,
            "real_origin_source_expansion_status": "expansion_ready",
            "post_expansion_mainline_real_origin_candidate_count": 12,
            "candidate_depth_by_source_origin_class": {
                "real_origin": 12,
                "semi_real_origin": 4,
                "workflow_proximal_proxy": 0,
            },
            "max_single_source_share_pct": 33.3,
            "needs_additional_real_origin_sources": False,
            "v0_10_3_handoff_mode": "freeze_first_real_origin_workflow_substrate",
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _ready_pool_rows() -> list[dict]:
    rows = [
        _row("b1", "open_source_issue_archive_buildings", "control_library_maintenance", complexity_tier="complex"),
        _row("b2", "open_source_issue_archive_buildings", "controller_reset_maintenance"),
        _row("m1", "open_source_issue_archive_msl", "multibody_constraint_maintenance", real_origin_distance="medium", complexity_tier="complex"),
        _row("m2", "open_source_issue_archive_msl", "conversion_compatibility_maintenance", real_origin_distance="medium", complexity_tier="simple"),
        _row("m3", "open_source_issue_archive_msl", "conversion_compatibility_maintenance", real_origin_distance="medium", complexity_tier="simple"),
        _row("m4", "open_source_issue_archive_msl", "conversion_compatibility_maintenance", real_origin_distance="medium", complexity_tier="simple"),
        _row("a1", "open_source_issue_archive_aixlib", "refrigerant_interface_maintenance", real_origin_distance="medium", complexity_tier="complex"),
        _row("a2", "open_source_issue_archive_aixlib", "refrigerant_validation_maintenance", real_origin_distance="medium", complexity_tier="complex"),
        _row("a3", "open_source_issue_archive_aixlib", "refrigerant_validation_maintenance", real_origin_distance="medium"),
        _row("a4", "open_source_issue_archive_aixlib", "interface_compatibility_maintenance"),
        _row("i1", "open_source_issue_archive_ibpsa", "media_record_maintenance", real_origin_distance="medium", complexity_tier="complex"),
        _row("i2", "open_source_issue_archive_ibpsa", "fluid_package_compatibility_maintenance"),
        _row("s1", "semi_real_origin_review_digest", "review_followup_only", source_origin_class="semi_real_origin", real_origin_distance="medium"),
        _row("s2", "semi_real_origin_comment_digest", "maintenance_regression_followup", source_origin_class="semi_real_origin", real_origin_distance="medium"),
        _row("s3", "semi_real_origin_comment_digest", "documentation_sync_followup", source_origin_class="semi_real_origin", real_origin_distance="medium"),
        _row("s4", "semi_real_origin_comment_digest", "review_followup_only", source_origin_class="semi_real_origin", real_origin_distance="medium"),
    ]
    return rows


def _write_v102_pool_delta(path: Path, *, rows: list[dict] | None = None) -> None:
    payload = {
        "post_expansion_candidate_pool": rows if rows is not None else _ready_pool_rows(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class AgentModelicaV103RealOriginSubstrateFlowTests(unittest.TestCase):
    def test_handoff_integrity_passes_on_expected_v102_closeout(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v102 = root / "v102" / "summary.json"
            _write_v102_closeout(v102)
            payload = build_v103_handoff_integrity(v102_closeout_path=str(v102), out_dir=str(root / "handoff"))
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_builder_freezes_all_eligible_upstream_mainline_rows(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pool = root / "pool" / "summary.json"
            _write_v102_pool_delta(pool)
            payload = build_v103_real_origin_substrate_builder(v102_pool_delta_path=str(pool), out_dir=str(root / "builder"))
            self.assertEqual(payload["real_origin_substrate_candidate_count"], 12)
            self.assertEqual(payload["excluded_upstream_mainline_row_count"], 4)
            self.assertEqual(payload["source_mix"]["open_source_issue_archive_msl"], 4)

    def test_closeout_routes_to_partial_when_substrate_is_valid_but_composition_is_weaker(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v102 = root / "v102" / "summary.json"
            _write_v102_closeout(v102)
            builder_payload = {
                "real_origin_substrate_candidate_table": [
                    _row("p1", "s1", "fam1"),
                    _row("p2", "s1", "fam2"),
                    _row("p3", "s2", "fam3"),
                ],
                "excluded_upstream_mainline_row_count": 0,
                "source_mix": {"s1": 2, "s2": 1},
                "workflow_family_mix": {"fam1": 1, "fam2": 1, "fam3": 1},
                "complexity_mix": {"medium": 3},
                "max_single_source_share_pct": 66.7,
            }
            builder_path = root / "builder" / "summary.json"
            builder_path.parent.mkdir(parents=True, exist_ok=True)
            builder_path.write_text(json.dumps(builder_payload), encoding="utf-8")
            payload = build_v103_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                real_origin_substrate_builder_path=str(builder_path),
                real_origin_substrate_admission_path=str(root / "admission" / "summary.json"),
                v102_closeout_path=str(v102),
                v102_pool_delta_path=str(root / "unused_pool" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_10_3_first_real_origin_workflow_substrate_partial")

    def test_closeout_returns_invalid_when_proxy_row_appears(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v102 = root / "v102" / "summary.json"
            _write_v102_closeout(v102)
            builder_payload = {
                "real_origin_substrate_candidate_table": [
                    _row("i1", "s1", "fam1"),
                    _row("i2", "proxy", "fam2", source_origin_class="workflow_proximal_proxy", real_origin_distance="far"),
                ],
                "excluded_upstream_mainline_row_count": 0,
                "source_mix": {"s1": 1, "proxy": 1},
                "workflow_family_mix": {"fam1": 1, "fam2": 1},
                "complexity_mix": {"medium": 2},
                "max_single_source_share_pct": 50.0,
            }
            builder_path = root / "builder" / "summary.json"
            builder_path.parent.mkdir(parents=True, exist_ok=True)
            builder_path.write_text(json.dumps(builder_payload), encoding="utf-8")
            payload = build_v103_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                real_origin_substrate_builder_path=str(builder_path),
                real_origin_substrate_admission_path=str(root / "admission" / "summary.json"),
                v102_closeout_path=str(v102),
                v102_pool_delta_path=str(root / "unused_pool" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_10_3_real_origin_substrate_inputs_invalid")


if __name__ == "__main__":
    unittest.main()
