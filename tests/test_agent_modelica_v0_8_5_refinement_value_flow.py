from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_8_5_closeout import build_v085_closeout
from gateforge.agent_modelica_v0_8_5_handoff_integrity import build_v085_handoff_integrity
from gateforge.agent_modelica_v0_8_5_refinement_worth_it_summary import (
    build_v085_refinement_worth_it_summary,
)
from gateforge.agent_modelica_v0_8_5_remaining_gap_characterization import (
    build_v085_remaining_gap_characterization,
)


class AgentModelicaV085RefinementValueFlowTests(unittest.TestCase):
    def _write_upstream_chain(self, root: Path) -> tuple[Path, Path, Path]:
        v084 = {
            "conclusion": {
                "version_decision": "v0_8_4_workflow_readiness_partial_but_interpretable",
                "adjudication_route": "workflow_readiness_partial_but_interpretable",
                "adjudication_route_count": 1,
                "legacy_bucket_sidecar_still_interpretable": True,
                "v0_8_5_handoff_mode": "decide_if_one_more_same_logic_refinement_is_worth_it",
            },
            "handoff_integrity": {
                "upstream_execution_source": "gateforge_run_contract_live_path",
            },
            "frozen_baseline_adjudication": {
                "workflow_resolution_rate_pct": 40.0,
                "goal_alignment_rate_pct": 60.0,
            },
        }
        v081 = {
            "handoff_integrity": {
                "checks": {
                    "planner_backend_rule_ok": True,
                    "experience_replay_off_ok": True,
                    "planner_experience_off_ok": True,
                    "max_rounds_one_ok": True,
                }
            },
            "profile_replay_pack": {
                "profile_run_count": 3,
                "per_case_outcome_consistency_rate_pct": 100.0,
            },
        }
        v082 = {
            "supported_threshold_pack": {
                "primary_workflow_metrics": {
                    "workflow_resolution_rate_pct_min": 50.0,
                    "goal_alignment_rate_pct_min": 70.0,
                }
            }
        }
        v084_path = root / "v084.json"
        v081_path = root / "v081.json"
        v082_path = root / "v082.json"
        v084_path.write_text(json.dumps(v084), encoding="utf-8")
        v081_path.write_text(json.dumps(v081), encoding="utf-8")
        v082_path.write_text(json.dumps(v082), encoding="utf-8")
        return v084_path, v081_path, v082_path

    def test_handoff_integrity_passes_on_partial_upstream(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v084_path, _, _ = self._write_upstream_chain(root)
            payload = build_v085_handoff_integrity(
                v084_closeout_path=str(v084_path),
                out_dir=str(root / "integrity"),
            )
            self.assertEqual(payload["status"], "PASS")

    def test_remaining_gap_characterization_marks_not_addressable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v084_path, v081_path, v082_path = self._write_upstream_chain(root)
            payload = build_v085_remaining_gap_characterization(
                v084_closeout_path=str(v084_path),
                v081_closeout_path=str(v081_path),
                v082_threshold_freeze_path=str(v082_path),
                out_dir=str(root / "gap"),
            )
            self.assertEqual(payload["gap_to_supported_workflow_resolution_pct"], 10.0)
            self.assertEqual(payload["gap_to_supported_goal_alignment_pct"], 10.0)
            self.assertFalse(payload["remaining_gap_is_threshold_proximal"])
            self.assertFalse(payload["remaining_gap_is_same_logic_addressable"])
            self.assertEqual(payload["expected_information_gain"], "marginal")

    def test_refinement_summary_marks_not_worth_it(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v084_path, v081_path, v082_path = self._write_upstream_chain(root)
            build_v085_remaining_gap_characterization(
                v084_closeout_path=str(v084_path),
                v081_closeout_path=str(v081_path),
                v082_threshold_freeze_path=str(v082_path),
                out_dir=str(root / "gap"),
            )
            payload = build_v085_refinement_worth_it_summary(
                remaining_gap_characterization_path=str(root / "gap" / "summary.json"),
                out_dir=str(root / "summary"),
            )
            self.assertEqual(payload["expected_information_gain"], "marginal")
            self.assertIn("not justified", payload["why_one_more_same_logic_refinement_is_or_is_not_justified"])

    def test_closeout_reaches_not_worth_it(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v084_path, v081_path, v082_path = self._write_upstream_chain(root)
            payload = build_v085_closeout(
                v084_closeout_path=str(v084_path),
                v081_closeout_path=str(v081_path),
                v082_threshold_freeze_path=str(v082_path),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                remaining_gap_characterization_path=str(root / "gap" / "summary.json"),
                refinement_worth_it_summary_path=str(root / "summary" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                payload["conclusion"]["version_decision"],
                "v0_8_5_same_logic_refinement_not_worth_it",
            )
            self.assertEqual(
                payload["conclusion"]["v0_8_6_handoff_mode"],
                "prepare_v0_8_phase_closeout",
            )

    def test_closeout_returns_invalid_on_bad_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bad_v084 = {
                "conclusion": {
                    "version_decision": "v0_8_4_workflow_readiness_supported",
                    "adjudication_route": "workflow_readiness_supported",
                    "adjudication_route_count": 1,
                    "legacy_bucket_sidecar_still_interpretable": True,
                    "v0_8_5_handoff_mode": "prepare_workflow_phase_closeout_or_promotion",
                },
                "handoff_integrity": {
                    "upstream_execution_source": "gateforge_run_contract_live_path",
                },
            }
            bad_v084_path = root / "bad_v084.json"
            bad_v084_path.write_text(json.dumps(bad_v084), encoding="utf-8")
            _, v081_path, v082_path = self._write_upstream_chain(root)
            payload = build_v085_closeout(
                v084_closeout_path=str(bad_v084_path),
                v081_closeout_path=str(v081_path),
                v082_threshold_freeze_path=str(v082_path),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                remaining_gap_characterization_path=str(root / "gap" / "summary.json"),
                refinement_worth_it_summary_path=str(root / "summary" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                payload["conclusion"]["version_decision"],
                "v0_8_5_handoff_decision_inputs_invalid",
            )


if __name__ == "__main__":
    unittest.main()
