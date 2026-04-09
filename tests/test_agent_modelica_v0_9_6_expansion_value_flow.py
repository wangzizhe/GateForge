from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_9_6_closeout import build_v096_closeout
from gateforge.agent_modelica_v0_9_6_expansion_worth_it_summary import build_v096_expansion_worth_it_summary
from gateforge.agent_modelica_v0_9_6_handoff_integrity import build_v096_handoff_integrity
from gateforge.agent_modelica_v0_9_6_remaining_uncertainty_characterization import (
    build_v096_remaining_uncertainty_characterization,
)


class AgentModelicaV096ExpansionValueFlowTests(unittest.TestCase):
    def _write_upstream_chain(self, root: Path) -> tuple[Path, Path, Path, Path, Path]:
        v091 = {
            "conclusion": {
                "candidate_depth_by_priority_barrier": {
                    "goal_artifact_missing_after_surface_fix": 8,
                    "dispatch_or_policy_limited_unresolved": 8,
                    "workflow_spillover_unresolved": 8,
                }
            }
        }
        v092 = {
            "conclusion": {
                "version_decision": "v0_9_2_first_expanded_authentic_workflow_substrate_ready",
                "priority_barrier_coverage_table": {
                    "goal_artifact_missing_after_surface_fix": 5,
                    "dispatch_or_policy_limited_unresolved": 5,
                    "workflow_spillover_unresolved": 5,
                },
            }
        }
        v093 = {
            "conclusion": {
                "version_decision": "v0_9_3_expanded_workflow_profile_characterized",
                "profile_barrier_unclassified_count": 0,
            }
        }
        v094 = {
            "conclusion": {
                "version_decision": "v0_9_4_expanded_workflow_thresholds_frozen",
                "baseline_classification_under_frozen_pack": "expanded_workflow_readiness_partial_but_interpretable",
            }
        }
        v095 = {
            "conclusion": {
                "version_decision": "v0_9_5_expanded_workflow_readiness_partial_but_interpretable",
                "final_adjudication_label": "expanded_workflow_readiness_partial_but_interpretable",
                "adjudication_route_count": 1,
                "execution_posture_semantics_preserved": True,
                "v0_9_6_handoff_mode": "decide_whether_more_authentic_expansion_is_still_worth_it",
            }
        }
        paths = []
        for name, payload in [("v091.json", v091), ("v092.json", v092), ("v093.json", v093), ("v094.json", v094), ("v095.json", v095)]:
            path = root / name
            path.write_text(json.dumps(payload), encoding="utf-8")
            paths.append(path)
        return tuple(paths)

    def test_handoff_integrity_passes_on_partial_upstream(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v091_path, v092_path, v093_path, v094_path, v095_path = self._write_upstream_chain(root)
            payload = build_v096_handoff_integrity(
                v095_closeout_path=str(v095_path),
                v094_closeout_path=str(v094_path),
                v093_closeout_path=str(v093_path),
                v092_closeout_path=str(v092_path),
                out_dir=str(root / "integrity"),
            )
            self.assertEqual(payload["status"], "PASS")

    def test_remaining_uncertainty_characterization_marks_not_addressable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v091_path, v092_path, v093_path, v094_path, v095_path = self._write_upstream_chain(root)
            payload = build_v096_remaining_uncertainty_characterization(
                v095_closeout_path=str(v095_path),
                v094_closeout_path=str(v094_path),
                v093_closeout_path=str(v093_path),
                v092_closeout_path=str(v092_path),
                v091_closeout_path=str(v091_path),
                out_dir=str(root / "uncertainty"),
            )
            self.assertFalse(payload["remaining_uncertainty_is_depth_limited"])
            self.assertFalse(payload["remaining_uncertainty_is_authentic_expansion_addressable"])
            self.assertEqual(payload["expected_information_gain"], "marginal")

    def test_expansion_summary_marks_not_worth_it(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v091_path, v092_path, v093_path, v094_path, v095_path = self._write_upstream_chain(root)
            build_v096_remaining_uncertainty_characterization(
                v095_closeout_path=str(v095_path),
                v094_closeout_path=str(v094_path),
                v093_closeout_path=str(v093_path),
                v092_closeout_path=str(v092_path),
                v091_closeout_path=str(v091_path),
                out_dir=str(root / "uncertainty"),
            )
            payload = build_v096_expansion_worth_it_summary(
                remaining_uncertainty_characterization_path=str(root / "uncertainty" / "summary.json"),
                out_dir=str(root / "summary"),
            )
            self.assertEqual(payload["expected_information_gain"], "marginal")
            self.assertIn("not justified", payload["why_one_more_authentic_expansion_is_or_is_not_justified"])

    def test_closeout_reaches_not_worth_it(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v091_path, v092_path, v093_path, v094_path, v095_path = self._write_upstream_chain(root)
            payload = build_v096_closeout(
                v095_closeout_path=str(v095_path),
                v094_closeout_path=str(v094_path),
                v093_closeout_path=str(v093_path),
                v092_closeout_path=str(v092_path),
                v091_closeout_path=str(v091_path),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                remaining_uncertainty_characterization_path=str(root / "uncertainty" / "summary.json"),
                expansion_worth_it_summary_path=str(root / "summary" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_9_6_more_authentic_expansion_not_worth_it")
            self.assertEqual(payload["conclusion"]["v0_9_7_handoff_mode"], "prepare_v0_9_phase_synthesis")

    def test_justified_path_is_executable_with_depth_limited_synthetic_input(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v091_path, v092_path, v093_path, v094_path, v095_path = self._write_upstream_chain(root)
            v091 = json.loads(v091_path.read_text())
            v092 = json.loads(v092_path.read_text())
            v091["conclusion"]["candidate_depth_by_priority_barrier"] = {
                "goal_artifact_missing_after_surface_fix": 5,
                "dispatch_or_policy_limited_unresolved": 5,
                "workflow_spillover_unresolved": 5,
            }
            v092["conclusion"]["priority_barrier_coverage_table"] = {
                "goal_artifact_missing_after_surface_fix": 4,
                "dispatch_or_policy_limited_unresolved": 5,
                "workflow_spillover_unresolved": 5,
            }
            v091_path.write_text(json.dumps(v091), encoding="utf-8")
            v092_path.write_text(json.dumps(v092), encoding="utf-8")
            build_v096_remaining_uncertainty_characterization(
                v095_closeout_path=str(v095_path),
                v094_closeout_path=str(v094_path),
                v093_closeout_path=str(v093_path),
                v092_closeout_path=str(v092_path),
                v091_closeout_path=str(v091_path),
                out_dir=str(root / "uncertainty"),
            )
            build_v096_expansion_worth_it_summary(
                remaining_uncertainty_characterization_path=str(root / "uncertainty" / "summary.json"),
                out_dir=str(root / "summary"),
            )
            payload = build_v096_closeout(
                v095_closeout_path=str(v095_path),
                v094_closeout_path=str(v094_path),
                v093_closeout_path=str(v093_path),
                v092_closeout_path=str(v092_path),
                v091_closeout_path=str(v091_path),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                remaining_uncertainty_characterization_path=str(root / "uncertainty" / "summary.json"),
                expansion_worth_it_summary_path=str(root / "summary" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_9_6_one_more_authentic_expansion_justified")

    def test_closeout_returns_invalid_on_bad_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v091_path, v092_path, v093_path, v094_path, _ = self._write_upstream_chain(root)
            bad_v095 = {
                "conclusion": {
                    "version_decision": "v0_9_5_expanded_workflow_readiness_supported",
                    "final_adjudication_label": "expanded_workflow_readiness_supported",
                    "adjudication_route_count": 1,
                    "execution_posture_semantics_preserved": True,
                    "v0_9_6_handoff_mode": "evaluate_whether_v0_9_phase_stop_condition_is_near",
                }
            }
            bad_v095_path = root / "bad_v095.json"
            bad_v095_path.write_text(json.dumps(bad_v095), encoding="utf-8")
            payload = build_v096_closeout(
                v095_closeout_path=str(bad_v095_path),
                v094_closeout_path=str(v094_path),
                v093_closeout_path=str(v093_path),
                v092_closeout_path=str(v092_path),
                v091_closeout_path=str(v091_path),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                remaining_uncertainty_characterization_path=str(root / "uncertainty" / "summary.json"),
                expansion_worth_it_summary_path=str(root / "summary" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_9_6_handoff_decision_inputs_invalid")


if __name__ == "__main__":
    unittest.main()
