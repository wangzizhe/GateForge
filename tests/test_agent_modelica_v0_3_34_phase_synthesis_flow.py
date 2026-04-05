from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_34_closeout import build_v0334_closeout
from gateforge.agent_modelica_v0_3_34_family_ledger import build_v0334_family_ledger
from gateforge.agent_modelica_v0_3_34_real_distribution_synthesis import build_v0334_real_distribution_synthesis
from gateforge.agent_modelica_v0_3_34_stop_condition_audit import build_v0334_stop_condition_audit
from gateforge.agent_modelica_v0_3_34_v0_4_handoff import build_v0334_v0_4_handoff


class AgentModelicaV0334PhaseSynthesisFlowTests(unittest.TestCase):
    def _write_closeouts(self, root: Path) -> None:
        (root / "v0322").mkdir(parents=True, exist_ok=True)
        (root / "v0328").mkdir(parents=True, exist_ok=True)
        (root / "v0331").mkdir(parents=True, exist_ok=True)
        (root / "v0333").mkdir(parents=True, exist_ok=True)
        (root / "v0317_closeout").mkdir(parents=True, exist_ok=True)
        (root / "v0317_generation").mkdir(parents=True, exist_ok=True)
        (root / "v0317_one_step").mkdir(parents=True, exist_ok=True)
        (root / "v0317_distribution").mkdir(parents=True, exist_ok=True)

        (root / "v0322" / "summary.json").write_text(
            json.dumps({"conclusion": {"version_decision": "stage2_api_discovery_coverage_ready"}}),
            encoding="utf-8",
        )
        (root / "v0328" / "summary.json").write_text(
            json.dumps(
                {
                    "conclusion": {
                        "version_decision": "stage2_neighbor_component_local_interface_discovery_coverage_ready",
                        "authority_confidence": "supported",
                    }
                }
            ),
            encoding="utf-8",
        )
        (root / "v0331" / "summary.json").write_text(
            json.dumps(
                {
                    "conclusion": {
                        "version_decision": "stage2_medium_redeclare_discovery_coverage_partially_ready",
                        "authority_confidence": "supported",
                    }
                }
            ),
            encoding="utf-8",
        )
        (root / "v0333" / "summary.json").write_text(
            json.dumps(
                {
                    "conclusion": {
                        "version_decision": "stage2_medium_redeclare_pipe_slice_coverage_ready",
                        "third_family_recomposition_status": "full_widened_authority_ready",
                        "pipe_slice_authority_confidence": "supported",
                    }
                }
            ),
            encoding="utf-8",
        )
        (root / "v0317_closeout" / "summary.json").write_text(
            json.dumps({"conclusion": {"version_decision": "distribution_alignment_not_supported"}}),
            encoding="utf-8",
        )
        (root / "v0317_generation" / "summary.json").write_text(
            json.dumps(
                {
                    "final_task_count": 30,
                    "tier_summary": {
                        "simple": {"first_failure_stage_distribution": {"stage_0_none": 6, "stage_2_structural_balance_reference": 4}},
                        "medium": {"first_failure_stage_distribution": {"stage_2_structural_balance_reference": 10}},
                        "complex": {"first_failure_stage_distribution": {"stage_2_structural_balance_reference": 10}},
                    },
                }
            ),
            encoding="utf-8",
        )
        (root / "v0317_one_step" / "summary.json").write_text(
            json.dumps({"task_count": 30, "second_residual_stage_distribution": {"stage_0_none": 6, "stage_2_structural_balance_reference": 24}}),
            encoding="utf-8",
        )
        (root / "v0317_distribution" / "summary.json").write_text(
            json.dumps({"version_decision": "distribution_alignment_not_supported", "synthetic_family_key_count": 2}),
            encoding="utf-8",
        )

    def test_phase_synthesis_reaches_prepare_v0_4_with_insufficient_real_overlap_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_closeouts(root)
            build_v0334_family_ledger(
                v0322_closeout_path=str(root / "v0322" / "summary.json"),
                v0328_closeout_path=str(root / "v0328" / "summary.json"),
                v0331_closeout_path=str(root / "v0331" / "summary.json"),
                v0333_closeout_path=str(root / "v0333" / "summary.json"),
                out_dir=str(root / "ledger"),
            )
            build_v0334_stop_condition_audit(
                family_ledger_path=str(root / "ledger" / "summary.json"),
                generation_census_path=str(root / "v0317_generation" / "summary.json"),
                one_step_repair_path=str(root / "v0317_one_step" / "summary.json"),
                out_dir=str(root / "audit"),
            )
            synthesis = build_v0334_real_distribution_synthesis(
                family_ledger_path=str(root / "ledger" / "summary.json"),
                v0317_closeout_path=str(root / "v0317_closeout" / "summary.json"),
                v0317_distribution_analysis_path=str(root / "v0317_distribution" / "summary.json"),
                out_dir=str(root / "real"),
            )
            self.assertEqual(synthesis.get("material_overlap_supported"), "insufficient_evidence")
            build_v0334_v0_4_handoff(
                stop_audit_path=str(root / "audit" / "summary.json"),
                real_distribution_synthesis_path=str(root / "real" / "summary.json"),
                out_dir=str(root / "handoff"),
            )
            payload = build_v0334_closeout(
                family_ledger_path=str(root / "ledger" / "summary.json"),
                stop_audit_path=str(root / "audit" / "summary.json"),
                real_distribution_synthesis_path=str(root / "real" / "summary.json"),
                v0_4_handoff_path=str(root / "handoff" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_3_phase_complete_prepare_v0_4")
            self.assertEqual((payload.get("conclusion") or {}).get("real_distribution_authority_status"), "deferred_to_v0_4_back_check")

    def test_phase_synthesis_stays_in_v0_3_when_neighbor_anchor_is_not_supported(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_closeouts(root)
            (root / "v0328" / "summary.json").write_text(
                json.dumps(
                    {
                        "conclusion": {
                            "version_decision": "stage2_neighbor_component_local_interface_discovery_coverage_partially_ready",
                            "authority_confidence": "directional_only",
                        }
                    }
                ),
                encoding="utf-8",
            )
            build_v0334_family_ledger(
                v0322_closeout_path=str(root / "v0322" / "summary.json"),
                v0328_closeout_path=str(root / "v0328" / "summary.json"),
                v0331_closeout_path=str(root / "v0331" / "summary.json"),
                v0333_closeout_path=str(root / "v0333" / "summary.json"),
                out_dir=str(root / "ledger"),
            )
            build_v0334_stop_condition_audit(
                family_ledger_path=str(root / "ledger" / "summary.json"),
                generation_census_path=str(root / "v0317_generation" / "summary.json"),
                one_step_repair_path=str(root / "v0317_one_step" / "summary.json"),
                out_dir=str(root / "audit"),
            )
            build_v0334_real_distribution_synthesis(
                family_ledger_path=str(root / "ledger" / "summary.json"),
                v0317_closeout_path=str(root / "v0317_closeout" / "summary.json"),
                v0317_distribution_analysis_path=str(root / "v0317_distribution" / "summary.json"),
                out_dir=str(root / "real"),
            )
            build_v0334_v0_4_handoff(
                stop_audit_path=str(root / "audit" / "summary.json"),
                real_distribution_synthesis_path=str(root / "real" / "summary.json"),
                out_dir=str(root / "handoff"),
            )
            payload = build_v0334_closeout(
                family_ledger_path=str(root / "ledger" / "summary.json"),
                stop_audit_path=str(root / "audit" / "summary.json"),
                real_distribution_synthesis_path=str(root / "real" / "summary.json"),
                v0_4_handoff_path=str(root / "handoff" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_3_phase_not_yet_complete")


if __name__ == "__main__":
    unittest.main()
