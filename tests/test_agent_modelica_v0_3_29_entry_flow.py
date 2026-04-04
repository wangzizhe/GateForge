from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_29_closeout import build_v0329_closeout
from gateforge.agent_modelica_v0_3_29_entry_family_spec import build_v0329_entry_family_spec
from gateforge.agent_modelica_v0_3_29_entry_taskset import build_v0329_entry_taskset
from gateforge.agent_modelica_v0_3_29_patch_contract import build_v0329_patch_contract
from gateforge.agent_modelica_v0_3_29_viability_triage import build_v0329_viability_triage


class AgentModelicaV0329EntryFlowTests(unittest.TestCase):
    def test_viability_triage_falls_back_to_medium_entry(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            payload = build_v0329_viability_triage(out_dir=str(root / "triage"), use_fixture_only=True)
            summary = payload.get("summary") or {}
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(summary.get("selected_family"), "medium_redeclare_alignment")
            self.assertTrue(summary.get("fallback_triggered"))
            self.assertLessEqual(int(summary.get("local_connection_accepted_pattern_count") or 0), 1)

    def test_entry_taskset_freezes_medium_entry_slice(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build_v0329_viability_triage(out_dir=str(root / "triage"), use_fixture_only=True)
            build_v0329_entry_family_spec(
                triage_path=str(root / "triage" / "summary.json"),
                triage_records_path=str(root / "triage" / "records.json"),
                out_dir=str(root / "entry_spec"),
            )
            payload = build_v0329_entry_taskset(
                entry_spec_path=str(root / "entry_spec" / "summary.json"),
                out_dir=str(root / "taskset"),
                use_fixture_only=True,
            )
            summary = payload.get("summary") or {}
            self.assertEqual(summary.get("status"), "PASS")
            self.assertGreaterEqual(int(summary.get("entry_source_count") or 0), 3)
            self.assertGreaterEqual(int(summary.get("entry_single_task_count") or 0), 6)
            self.assertGreaterEqual(int(summary.get("entry_dual_sidecar_count") or 0), 4)
            self.assertIn("insert_redeclare_package_medium", summary.get("allowed_patch_types") or [])

    def test_closeout_emits_v030_handoff_spec(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build_v0329_viability_triage(out_dir=str(root / "triage"), use_fixture_only=True)
            build_v0329_entry_family_spec(
                triage_path=str(root / "triage" / "summary.json"),
                triage_records_path=str(root / "triage" / "records.json"),
                out_dir=str(root / "entry_spec"),
            )
            build_v0329_entry_taskset(
                entry_spec_path=str(root / "entry_spec" / "summary.json"),
                out_dir=str(root / "taskset"),
                use_fixture_only=True,
            )
            build_v0329_patch_contract(
                entry_spec_path=str(root / "entry_spec" / "summary.json"),
                out_dir=str(root / "contract"),
            )
            payload = build_v0329_closeout(
                triage_path=str(root / "triage" / "summary.json"),
                entry_spec_path=str(root / "entry_spec" / "summary.json"),
                taskset_path=str(root / "taskset" / "summary.json"),
                patch_contract_path=str(root / "contract" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            conclusion = payload.get("conclusion") or {}
            self.assertEqual(conclusion.get("version_decision"), "stage2_third_family_entry_ready")
            self.assertEqual(conclusion.get("v0_3_30_target_family"), "medium_redeclare_alignment")
            self.assertTrue(str(conclusion.get("v0_3_30_handoff_spec") or "").endswith("summary.json"))

    def test_closeout_boundary_rejected_when_no_family_selected(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "triage").mkdir(parents=True, exist_ok=True)
            (root / "entry_spec").mkdir(parents=True, exist_ok=True)
            (root / "taskset").mkdir(parents=True, exist_ok=True)
            (root / "contract").mkdir(parents=True, exist_ok=True)
            (root / "triage" / "summary.json").write_text(
                json.dumps(
                    {
                        "status": "FAIL",
                        "selected_family": "",
                        "local_connection_accepted_pattern_count": 0,
                        "fallback_triggered": True,
                        "fallback_target_bucket_hit_count": 0,
                    }
                ),
                encoding="utf-8",
            )
            (root / "entry_spec" / "summary.json").write_text(json.dumps({"status": "FAIL", "selected_family": ""}), encoding="utf-8")
            (root / "taskset" / "summary.json").write_text(json.dumps({"status": "FAIL"}), encoding="utf-8")
            (root / "contract" / "summary.json").write_text(json.dumps({"status": "FAIL"}), encoding="utf-8")
            payload = build_v0329_closeout(
                triage_path=str(root / "triage" / "summary.json"),
                entry_spec_path=str(root / "entry_spec" / "summary.json"),
                taskset_path=str(root / "taskset" / "summary.json"),
                patch_contract_path=str(root / "contract" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "stage2_third_family_boundary_rejected")


if __name__ == "__main__":
    unittest.main()
