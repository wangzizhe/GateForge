from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_24_closeout import build_v0324_closeout
from gateforge.agent_modelica_v0_3_24_common import apply_interface_discovery_first_fix, build_surface_index_payload
from gateforge.agent_modelica_v0_3_24_patch_contract import build_v0324_patch_contract
from gateforge.agent_modelica_v0_3_24_taskset import build_v0324_taskset


class AgentModelicaV0324InterfaceDiscoveryFlowTests(unittest.TestCase):
    def test_surface_index_builds_local_interface_candidate_sets(self) -> None:
        payload = build_surface_index_payload()
        records = payload.get("surface_records") or {}
        self.assertIn("feedback.input1", records)
        self.assertIn("feedback.u1", (records.get("feedback.input1") or {}).get("candidate_symbols") or [])
        self.assertIn("source.posPin", records)
        self.assertIn("source.p", (records.get("source.posPin") or {}).get("candidate_symbols") or [])

    def test_interface_discovery_patch_prefers_expected_local_candidate(self) -> None:
        patched, audit = apply_interface_discovery_first_fix(
            current_text="connect(reference.y, feedback.input1);",
            patch_type="replace_local_port_symbol",
            wrong_symbol="feedback.input1",
            canonical_symbol="feedback.u1",
            component_family="local_signal_port_alignment",
            candidate_symbols=["feedback.u1", "feedback.u2", "feedback.y"],
        )
        self.assertTrue(audit.get("applied"))
        self.assertEqual(audit.get("selected_candidate"), "feedback.u1")
        self.assertIn("feedback.u1", patched)

    def test_taskset_and_contract_pass_with_minimum_counts(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = build_v0324_taskset(out_dir=str(root / "taskset"), use_fixture_only=True)
            contract = build_v0324_patch_contract(out_dir=str(root / "contract"))
            summary = taskset.get("summary") or {}
            self.assertEqual(summary.get("status"), "PASS")
            self.assertGreaterEqual(int(summary.get("active_single_task_count") or 0), 6)
            self.assertGreaterEqual(int(summary.get("active_dual_task_count") or 0), 6)
            self.assertEqual(contract.get("selection_mode"), "authoritative_local_interface_surface_only")

    def test_closeout_promotes_ready_with_fixture_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "surface").mkdir(parents=True, exist_ok=True)
            (root / "taskset").mkdir(parents=True, exist_ok=True)
            (root / "contract").mkdir(parents=True, exist_ok=True)
            (root / "first_fix").mkdir(parents=True, exist_ok=True)
            (root / "dual").mkdir(parents=True, exist_ok=True)
            (root / "surface" / "summary.json").write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "source_mode": "source_model_local_surface",
                        "surface_export_success_rate_pct": 100.0,
                        "fixture_fallback_rate_pct": 0.0,
                        "export_failure_count": 0,
                    }
                ),
                encoding="utf-8",
            )
            (root / "taskset" / "summary.json").write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "execution_mode": "promoted",
                        "active_single_task_count": 8,
                        "active_dual_task_count": 6,
                        "export_excluded_count": 0,
                        "export_excluded_task_ids": [],
                    }
                ),
                encoding="utf-8",
            )
            build_v0324_patch_contract(out_dir=str(root / "contract"))
            (root / "first_fix" / "summary.json").write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "target_first_failure_hit_rate_pct": 100.0,
                        "candidate_contains_canonical_rate_pct": 100.0,
                        "candidate_top1_canonical_rate_pct": 90.0,
                        "patch_applied_rate_pct": 90.0,
                        "focal_patch_hit_rate_pct": 90.0,
                        "signature_advance_rate_pct": 90.0,
                        "drift_to_compile_failure_unknown_rate_pct": 0.0,
                        "drift_task_count": 0,
                        "drift_reason_counts": {},
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
                        "second_residual_local_interface_retained_count": 5,
                        "dual_full_resolution_rate_pct": 80.0,
                        "full_dual_resolution_count": 5,
                    }
                ),
                encoding="utf-8",
            )
            closeout = build_v0324_closeout(
                surface_index_path=str(root / "surface" / "summary.json"),
                taskset_path=str(root / "taskset" / "summary.json"),
                patch_contract_path=str(root / "contract" / "summary.json"),
                first_fix_path=str(root / "first_fix" / "summary.json"),
                dual_recheck_path=str(root / "dual" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((closeout.get("conclusion") or {}).get("version_decision"), "stage2_local_interface_discovery_ready")


if __name__ == "__main__":
    unittest.main()
