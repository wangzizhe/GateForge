from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_23_closeout import build_v0323_closeout
from gateforge.agent_modelica_v0_3_23_common import apply_interface_first_fix, classify_dry_run_output
from gateforge.agent_modelica_v0_3_23_patch_contract import build_v0323_patch_contract
from gateforge.agent_modelica_v0_3_23_target_manifest import build_v0323_target_manifest


class AgentModelicaV0323InterfaceAlignmentFlowTests(unittest.TestCase):
    def test_interface_patch_replaces_expected_endpoint(self) -> None:
        patched, audit = apply_interface_first_fix(
            current_text="connect(feedback.input1, controller.u);",
            patch_type="replace_local_port_symbol",
            wrong_symbol="feedback.input1",
            candidate_key="feedback.input1",
        )
        self.assertTrue(audit.get("applied"))
        self.assertEqual(audit.get("selected_candidate"), "feedback.u1")
        self.assertIn("feedback.u1", patched)

    def test_dry_run_classifier_marks_target_bucket_on_undefined_symbol(self) -> None:
        payload = classify_dry_run_output(
            output='Error: Variable heaterGain.inputSignal not found in scope ApiAlignMediumThermalControl.',
            return_code=0,
        )
        self.assertTrue(payload.get("target_bucket_hit"))
        self.assertEqual(payload.get("dominant_stage_subtype"), "stage_2_structural_balance_reference")
        self.assertEqual(payload.get("error_subtype"), "undefined_symbol")

    def test_target_manifest_and_contract_freeze_local_interface_family(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = build_v0323_target_manifest(out_dir=str(root / "manifest"), use_fixture_only=True)
            contract = build_v0323_patch_contract(out_dir=str(root / "contract"))
            summary = manifest.get("summary") or {}
            self.assertEqual(summary.get("status"), "PASS")
            self.assertGreaterEqual(int(summary.get("active_single_task_count") or 0), 2)
            self.assertGreaterEqual(int(summary.get("frozen_source_pattern_count") or 0), 4)
            self.assertEqual(contract.get("max_patch_count_per_round"), 1)

    def test_closeout_promotes_ready_with_fixture_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build_v0323_target_manifest(out_dir=str(root / "manifest"), use_fixture_only=True)
            build_v0323_patch_contract(out_dir=str(root / "contract"))
            (root / "first_fix").mkdir(parents=True, exist_ok=True)
            (root / "dual").mkdir(parents=True, exist_ok=True)
            (root / "first_fix" / "summary.json").write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "target_first_failure_hit_rate_pct": 100.0,
                        "patch_applied_rate_pct": 100.0,
                        "focal_patch_hit_rate_pct": 100.0,
                        "signature_advance_rate_pct": 100.0,
                        "drift_to_compile_failure_unknown_rate_pct": 0.0,
                        "signature_advance_not_fired_reason_counts": {},
                    }
                ),
                encoding="utf-8",
            )
            (root / "dual" / "summary.json").write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "same_cluster_second_residual_rate_pct": 80.0,
                        "second_residual_local_interface_retained_count": 4,
                        "full_dual_resolution_count": 4,
                    }
                ),
                encoding="utf-8",
            )
            closeout = build_v0323_closeout(
                manifest_path=str(root / "manifest" / "summary.json"),
                patch_contract_path=str(root / "contract" / "summary.json"),
                first_fix_path=str(root / "first_fix" / "summary.json"),
                dual_recheck_path=str(root / "dual" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((closeout.get("conclusion") or {}).get("version_decision"), "stage2_local_interface_alignment_ready")


if __name__ == "__main__":
    unittest.main()
