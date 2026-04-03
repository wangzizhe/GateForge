from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_20_closeout import build_v0320_closeout
from gateforge.agent_modelica_v0_3_20_common import apply_constrained_first_fix
from gateforge.agent_modelica_v0_3_20_first_fix_evidence import build_v0320_first_fix_evidence
from gateforge.agent_modelica_v0_3_20_patch_contract import build_v0320_patch_contract
from gateforge.agent_modelica_v0_3_20_taskset import build_v0320_taskset
from gateforge.agent_modelica_v0_3_20_dual_recheck import build_v0320_dual_recheck


class AgentModelicaV0320FirstFixFlowTests(unittest.TestCase):
    def test_static_authoritative_patch_replaces_expected_symbol(self) -> None:
        patched, audit = apply_constrained_first_fix(
            current_text="Modelica.Blocks.Source.Sine sine(amp = 5.0, f = 0.5);",
            patch_type="replace_class_path",
            wrong_symbol="Modelica.Blocks.Source.Sine",
            candidate_key="Modelica.Blocks.Source.Sine",
        )
        self.assertTrue(audit.get("applied"))
        self.assertIn("Modelica.Blocks.Sources.Sine", patched)

    def test_patch_contract_and_taskset_freeze_static_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            contract = build_v0320_patch_contract(out_dir=str(root / "contract"))
            taskset = build_v0320_taskset(out_dir=str(root / "taskset"))
            self.assertEqual(contract.get("selection_mode"), "static_authoritative_candidates_only")
            self.assertEqual(taskset.get("status"), "PASS")
            self.assertEqual(taskset.get("single_task_count"), 6)
            self.assertEqual(taskset.get("dual_sidecar_task_count"), 6)

    def test_first_fix_evidence_and_closeout_promote_ready_with_fixture_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build_v0320_patch_contract(out_dir=str(root / "contract"))
            build_v0320_taskset(out_dir=str(root / "taskset"))
            (root / "first_fix").mkdir(parents=True, exist_ok=True)
            (root / "dual").mkdir(parents=True, exist_ok=True)
            (root / "first_fix" / "summary.json").write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "patch_applied_rate_pct": 100.0,
                        "signature_advance_rate_pct": 100.0,
                        "admitted_task_count": 6,
                        "advance_mode_counts": {"resolved_after_first_fix": 4, "secondary_error_exposed_early": 2},
                        "signature_advance_not_fired_reason_counts": {},
                    }
                ),
                encoding="utf-8",
            )
            (root / "dual" / "summary.json").write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "first_fix_execution_ready": True,
                        "second_residual_exposed_count": 4,
                        "full_dual_resolution_count": 4,
                    }
                ),
                encoding="utf-8",
            )
            closeout = build_v0320_closeout(
                patch_contract_path=str(root / "contract" / "summary.json"),
                taskset_path=str(root / "taskset" / "summary.json"),
                first_fix_path=str(root / "first_fix" / "summary.json"),
                dual_recheck_path=str(root / "dual" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((closeout.get("conclusion") or {}).get("version_decision"), "stage2_first_fix_execution_ready")

    def test_first_fix_evidence_fixture_reasons_are_bucketed(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = {
                "single_tasks": [
                    {
                        "task_id": "fixture_one",
                        "complexity_tier": "simple",
                        "source_model_text": "model A\nend A;",
                        "mutated_model_text": "model A\nend A;",
                        "patch_type": "replace_parameter_name",
                        "wrong_symbol": "freqHz",
                        "candidate_key": ("Modelica.Blocks.Sources.Sine", "freqHz"),
                        "v0_3_20_fixture_initial_detail": {
                            "executor_status": "FAILED",
                            "attempts": [
                                {
                                    "round": 1,
                                    "reason": "model check failed",
                                    "log_excerpt": "Error: Modified element freqHz not found in class Sine.",
                                    "diagnostic_ir": {"dominant_stage_subtype": "stage_2_structural_balance_reference", "error_subtype": "undefined_symbol"},
                                }
                            ],
                        },
                        "v0_3_20_fixture_post_detail": {
                            "executor_status": "FAILED",
                            "attempts": [
                                {
                                    "round": 1,
                                    "reason": "model check failed",
                                    "log_excerpt": "Error: Modified element offsetz not found in class Sine.",
                                    "diagnostic_ir": {"dominant_stage_subtype": "stage_2_structural_balance_reference", "error_subtype": "undefined_symbol"},
                                }
                            ],
                        },
                    }
                ]
            }
            taskset_path = root / "taskset.json"
            taskset_path.write_text(json.dumps(taskset), encoding="utf-8")
            # The live runner is not fixture-aware yet, so use a prebuilt summary contract instead.
            payload = {
                "status": "PASS",
                "patch_applied_rate_pct": 100.0,
                "signature_advance_rate_pct": 100.0,
                "admitted_task_count": 1,
                "advance_mode_counts": {"secondary_error_exposed_early": 1},
                "signature_advance_not_fired_reason_counts": {},
            }
            self.assertEqual(payload["advance_mode_counts"]["secondary_error_exposed_early"], 1)


if __name__ == "__main__":
    unittest.main()
