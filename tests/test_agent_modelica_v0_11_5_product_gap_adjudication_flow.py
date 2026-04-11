from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_11_5_closeout import build_v115_closeout
from gateforge.agent_modelica_v0_11_5_handoff_integrity import build_v115_handoff_integrity
from gateforge.agent_modelica_v0_11_5_product_gap_adjudication_input_table import (
    build_v115_product_gap_adjudication_input_table,
)
from gateforge.agent_modelica_v0_11_5_first_product_gap_adjudication import (
    build_v115_first_product_gap_adjudication,
)


def _write_v113_closeout(
    path: Path,
    *,
    candidate_dominant_gap_family: str = "residual_core_capability_gap",
) -> None:
    payload = {
        "conclusion": {
            "version_decision": "v0_11_3_first_product_gap_profile_characterized",
            "candidate_dominant_gap_family": candidate_dominant_gap_family,
            "candidate_dominant_gap_family_interpretability": "interpretable",
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_v114_closeout(
    path: Path,
    *,
    version_decision: str = "v0_11_4_first_product_gap_thresholds_frozen",
    baseline_classification: str = "product_gap_partial_but_interpretable",
    anti_tautology_pass: bool = True,
    integer_safe_pass: bool = True,
    execution_posture_semantics_preserved: bool = True,
    handoff_mode: str = "adjudicate_first_product_gap_profile_against_frozen_thresholds",
    workflow_resolution_case_count: int = 3,
    goal_alignment_case_count: int = 5,
    surface_fix_only_case_count: int = 2,
    unresolved_case_count: int = 7,
) -> None:
    payload = {
        "conclusion": {
            "version_decision": version_decision,
            "product_gap_case_count": 12,
            "workflow_resolution_case_count": workflow_resolution_case_count,
            "goal_alignment_case_count": goal_alignment_case_count,
            "surface_fix_only_case_count": surface_fix_only_case_count,
            "unresolved_case_count": unresolved_case_count,
            "baseline_classification_under_frozen_pack": baseline_classification,
            "anti_tautology_pass": anti_tautology_pass,
            "integer_safe_pass": integer_safe_pass,
            "execution_posture_semantics_preserved": execution_posture_semantics_preserved,
            "v0_11_5_handoff_mode": handoff_mode,
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_v114_threshold_pack(
    path: Path,
    *,
    supported_wr: int = 4,
    supported_ga: int = 6,
    partial_wr: int = 3,
    partial_ga: int = 5,
) -> None:
    payload = {
        "supported_thresholds": {
            "workflow_resolution_case_count": supported_wr,
            "goal_alignment_case_count": supported_ga,
        },
        "partial_but_interpretable_thresholds": {
            "workflow_resolution_case_count": partial_wr,
            "goal_alignment_case_count": partial_ga,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class AgentModelicaV115ProductGapAdjudicationFlowTests(unittest.TestCase):
    def test_handoff_integrity_pass_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v114_closeout = root / "v114" / "closeout.json"
            _write_v114_closeout(v114_closeout)
            payload = build_v115_handoff_integrity(
                v114_closeout_path=str(v114_closeout),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_handoff_integrity_invalid_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v114_closeout = root / "v114" / "closeout.json"
            _write_v114_closeout(v114_closeout, handoff_mode="freeze_first_product_gap_thresholds")
            payload = build_v115_handoff_integrity(
                v114_closeout_path=str(v114_closeout),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "FAIL")

    def test_formal_partial_path_on_real_frozen_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v113_closeout = root / "v113" / "closeout.json"
            v114_closeout = root / "v114" / "closeout.json"
            v114_pack = root / "v114" / "pack.json"
            _write_v113_closeout(v113_closeout)
            _write_v114_closeout(v114_closeout)
            _write_v114_threshold_pack(v114_pack)
            payload = build_v115_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                product_gap_adjudication_input_table_path=str(root / "input" / "summary.json"),
                first_product_gap_adjudication_path=str(root / "adjudication" / "summary.json"),
                v114_closeout_path=str(v114_closeout),
                v114_threshold_pack_path=str(v114_pack),
                v113_closeout_path=str(v113_closeout),
                out_dir=str(root / "closeout"),
            )
            conclusion = payload["conclusion"]
            self.assertEqual(
                conclusion["version_decision"],
                "v0_11_5_first_product_gap_profile_partial_but_interpretable",
            )
            self.assertEqual(conclusion["formal_adjudication_label"], "product_gap_partial_but_interpretable")

    def test_supported_path_using_stronger_synthetic_input(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v113_closeout = root / "v113" / "closeout.json"
            v114_closeout = root / "v114" / "closeout.json"
            v114_pack = root / "v114" / "pack.json"
            _write_v113_closeout(v113_closeout, candidate_dominant_gap_family="context_discipline_gap")
            _write_v114_closeout(
                v114_closeout,
                baseline_classification="product_gap_supported",
                workflow_resolution_case_count=4,
                goal_alignment_case_count=6,
                surface_fix_only_case_count=2,
                unresolved_case_count=6,
            )
            _write_v114_threshold_pack(v114_pack)
            build_v115_product_gap_adjudication_input_table(
                v114_closeout_path=str(v114_closeout),
                v114_threshold_pack_path=str(v114_pack),
                v113_closeout_path=str(v113_closeout),
                out_dir=str(root / "input"),
            )
            adjudication = build_v115_first_product_gap_adjudication(
                product_gap_adjudication_input_table_path=str(root / "input" / "summary.json"),
                out_dir=str(root / "adjudication"),
            )
            self.assertEqual(adjudication["final_adjudication_label"], "product_gap_supported")

    def test_fallback_path_using_weaker_synthetic_input(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v113_closeout = root / "v113" / "closeout.json"
            v114_closeout = root / "v114" / "closeout.json"
            v114_pack = root / "v114" / "pack.json"
            _write_v113_closeout(v113_closeout)
            _write_v114_closeout(
                v114_closeout,
                baseline_classification="product_gap_fallback",
                workflow_resolution_case_count=2,
                goal_alignment_case_count=4,
                surface_fix_only_case_count=2,
                unresolved_case_count=8,
            )
            _write_v114_threshold_pack(v114_pack)
            build_v115_product_gap_adjudication_input_table(
                v114_closeout_path=str(v114_closeout),
                v114_threshold_pack_path=str(v114_pack),
                v113_closeout_path=str(v113_closeout),
                out_dir=str(root / "input"),
            )
            adjudication = build_v115_first_product_gap_adjudication(
                product_gap_adjudication_input_table_path=str(root / "input" / "summary.json"),
                out_dir=str(root / "adjudication"),
            )
            self.assertEqual(adjudication["final_adjudication_label"], "product_gap_fallback")

    def test_invalid_when_execution_posture_semantics_break(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v113_closeout = root / "v113" / "closeout.json"
            v114_closeout = root / "v114" / "closeout.json"
            v114_pack = root / "v114" / "pack.json"
            _write_v113_closeout(v113_closeout)
            _write_v114_closeout(v114_closeout, execution_posture_semantics_preserved=False)
            _write_v114_threshold_pack(v114_pack)
            payload = build_v115_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                product_gap_adjudication_input_table_path=str(root / "input" / "summary.json"),
                first_product_gap_adjudication_path=str(root / "adjudication" / "summary.json"),
                v114_closeout_path=str(v114_closeout),
                v114_threshold_pack_path=str(v114_pack),
                v113_closeout_path=str(v113_closeout),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_11_5_product_gap_adjudication_inputs_invalid")

    def test_invalid_path_on_broken_frozen_threshold_handoff_input(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v113_closeout = root / "v113" / "closeout.json"
            v114_closeout = root / "v114" / "closeout.json"
            v114_pack = root / "v114" / "pack.json"
            _write_v113_closeout(v113_closeout)
            _write_v114_closeout(v114_closeout, handoff_mode="freeze_first_product_gap_thresholds")
            _write_v114_threshold_pack(v114_pack)
            payload = build_v115_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                product_gap_adjudication_input_table_path=str(root / "input" / "summary.json"),
                first_product_gap_adjudication_path=str(root / "adjudication" / "summary.json"),
                v114_closeout_path=str(v114_closeout),
                v114_threshold_pack_path=str(v114_pack),
                v113_closeout_path=str(v113_closeout),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_11_5_product_gap_adjudication_inputs_invalid")

    def test_dominant_gap_family_readout_is_pass_through(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v113_closeout = root / "v113" / "closeout.json"
            v114_closeout = root / "v114" / "closeout.json"
            v114_pack = root / "v114" / "pack.json"
            _write_v113_closeout(v113_closeout, candidate_dominant_gap_family="protocol_robustness_gap")
            _write_v114_closeout(v114_closeout)
            _write_v114_threshold_pack(v114_pack)
            input_table = build_v115_product_gap_adjudication_input_table(
                v114_closeout_path=str(v114_closeout),
                v114_threshold_pack_path=str(v114_pack),
                v113_closeout_path=str(v113_closeout),
                out_dir=str(root / "input"),
            )
            self.assertEqual(input_table["dominant_gap_family_readout"], "protocol_robustness_gap")
            adjudication = build_v115_first_product_gap_adjudication(
                product_gap_adjudication_input_table_path=str(root / "input" / "summary.json"),
                out_dir=str(root / "adjudication"),
            )
            self.assertEqual(adjudication["dominant_gap_family_readout"], "protocol_robustness_gap")


if __name__ == "__main__":
    unittest.main()
