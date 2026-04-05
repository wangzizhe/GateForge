from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_30_closeout import build_v0330_closeout
from gateforge.agent_modelica_v0_3_30_discovery_evidence import build_v0330_discovery_evidence
from gateforge.agent_modelica_v0_3_30_first_fix_evidence import build_v0330_first_fix_evidence
from gateforge.agent_modelica_v0_3_30_handoff_integrity import build_v0330_handoff_integrity
from gateforge.agent_modelica_v0_3_30_surface_index import build_v0330_surface_index


class AgentModelicaV0330MediumRedeclareFlowTests(unittest.TestCase):
    def _write_v0329_handoff(self, root: Path) -> None:
        (root / "v0329_closeout").mkdir(parents=True, exist_ok=True)
        (root / "v0329_spec").mkdir(parents=True, exist_ok=True)
        (root / "v0329_taskset").mkdir(parents=True, exist_ok=True)
        (root / "v0329_contract").mkdir(parents=True, exist_ok=True)
        (root / "v0329_closeout" / "summary.json").write_text(
            json.dumps(
                {
                    "conclusion": {
                        "v0_3_30_target_family": "medium_redeclare_alignment",
                    }
                }
            ),
            encoding="utf-8",
        )
        (root / "v0329_spec" / "summary.json").write_text(
            json.dumps(
                {
                    "status": "PASS",
                    "selected_family": "medium_redeclare_alignment",
                    "allowed_patch_types": [
                        "insert_redeclare_package_medium",
                        "replace_redeclare_clause",
                        "replace_medium_package_symbol",
                    ],
                    "allowed_patch_scope": "single_component_redeclare_clause_only",
                }
            ),
            encoding="utf-8",
        )
        source_text = "\n".join(
            [
                "model PortPipeTank",
                "  replaceable package Medium = Modelica.Media.Water.ConstantPropertyLiquidWater;",
                "  inner Modelica.Fluid.System system;",
                "  Modelica.Fluid.Sources.Boundary_pT ambient(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
                "  Modelica.Fluid.Pipes.StaticPipe pipe(redeclare package Medium = Medium, length=10, diameter=0.1);",
                "  Modelica.Fluid.Vessels.OpenTank tank(redeclare package Medium = Medium, crossArea=2, height=5, nPorts=1);",
                "equation",
                "end PortPipeTank;",
            ]
        )
        single_tasks = [
            {
                "task_id": f"fixture_single_{idx}",
                "source_id": "medium_port_pipe_tank",
                "complexity_tier": "medium",
                "model_name": "PortPipeTank",
                "source_model_text": source_text,
                "mutated_model_text": source_text.replace(
                    "Modelica.Fluid.Sources.Boundary_pT ambient(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
                    "Modelica.Fluid.Sources.Boundary_pT ambient(p=101325, T=293.15, nPorts=1);",
                ),
                "repair_steps": [
                    {
                        "patch_type": "insert_redeclare_package_medium",
                        "match_text": "Modelica.Fluid.Sources.Boundary_pT ambient(p=101325, T=293.15, nPorts=1);",
                        "replacement_text": "Modelica.Fluid.Sources.Boundary_pT ambient(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
                    }
                ],
                "first_failure_dry_run": {"error_signature": "Error: Fixture Medium.singleState compile_failure_unknown result."},
            }
            for idx in range(6)
        ]
        dual_tasks = [
            {
                "task_id": f"fixture_dual_{idx}",
                "source_id": "medium_port_pipe_tank",
                "complexity_tier": "medium",
                "model_name": "PortPipeTank",
                "source_model_text": source_text,
                "mutated_model_text": source_text.replace(
                    "Modelica.Fluid.Sources.Boundary_pT ambient(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
                    "Modelica.Fluid.Sources.Boundary_pT ambient(p=101325, T=293.15, nPorts=1);",
                ).replace(
                    "Modelica.Fluid.Vessels.OpenTank tank(redeclare package Medium = Medium, crossArea=2, height=5, nPorts=1);",
                    "Modelica.Fluid.Vessels.OpenTank tank(crossArea=2, height=5, nPorts=1);",
                ),
                "repair_steps": [
                    {
                        "patch_type": "insert_redeclare_package_medium",
                        "match_text": "Modelica.Fluid.Sources.Boundary_pT ambient(p=101325, T=293.15, nPorts=1);",
                        "replacement_text": "Modelica.Fluid.Sources.Boundary_pT ambient(redeclare package Medium = Medium, p=101325, T=293.15, nPorts=1);",
                    },
                    {
                        "patch_type": "insert_redeclare_package_medium",
                        "match_text": "Modelica.Fluid.Vessels.OpenTank tank(crossArea=2, height=5, nPorts=1);",
                        "replacement_text": "Modelica.Fluid.Vessels.OpenTank tank(redeclare package Medium = Medium, crossArea=2, height=5, nPorts=1);",
                    },
                ],
            }
            for idx in range(4)
        ]
        (root / "v0329_taskset" / "taskset.json").write_text(
            json.dumps(
                {
                    "summary": {
                        "status": "PASS",
                        "entry_source_count": 3,
                        "entry_single_task_count": 6,
                        "entry_dual_sidecar_count": 4,
                    },
                    "single_tasks": single_tasks,
                    "dual_tasks": dual_tasks,
                }
            ),
            encoding="utf-8",
        )
        (root / "v0329_contract" / "summary.json").write_text(
            json.dumps(
                {
                    "status": "PASS",
                    "selected_family": "medium_redeclare_alignment",
                    "allowed_patch_types": [
                        "insert_redeclare_package_medium",
                        "replace_redeclare_clause",
                        "replace_medium_package_symbol",
                    ],
                    "allowed_patch_scope": "single_component_redeclare_clause_only",
                }
            ),
            encoding="utf-8",
        )

    def test_handoff_integrity_passes_for_frozen_v0329_entry(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v0329_handoff(root)
            payload = build_v0330_handoff_integrity(
                v0329_closeout_path=str(root / "v0329_closeout" / "summary.json"),
                v0329_entry_spec_path=str(root / "v0329_spec" / "summary.json"),
                v0329_entry_taskset_path=str(root / "v0329_taskset" / "taskset.json"),
                v0329_patch_contract_path=str(root / "v0329_contract" / "summary.json"),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload.get("status"), "PASS")
            self.assertTrue(payload.get("handoff_substrate_valid"))

    def test_first_fix_discovery_and_dual_recheck_pass_in_fixture_mode(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v0329_handoff(root)
            build_v0330_handoff_integrity(
                v0329_closeout_path=str(root / "v0329_closeout" / "summary.json"),
                v0329_entry_spec_path=str(root / "v0329_spec" / "summary.json"),
                v0329_entry_taskset_path=str(root / "v0329_taskset" / "taskset.json"),
                v0329_patch_contract_path=str(root / "v0329_contract" / "summary.json"),
                out_dir=str(root / "handoff"),
            )
            first_fix = build_v0330_first_fix_evidence(
                entry_taskset_path=str(root / "v0329_taskset" / "taskset.json"),
                out_dir=str(root / "first_fix"),
                use_fixture_only=True,
            )
            surface = build_v0330_surface_index(
                entry_taskset_path=str(root / "v0329_taskset" / "taskset.json"),
                out_dir=str(root / "surface"),
                use_fixture_only=True,
            )
            discovery = build_v0330_discovery_evidence(
                first_fix_path=str(root / "first_fix" / "summary.json"),
                surface_index_path=str(root / "surface" / "surface_index.json"),
                entry_taskset_path=str(root / "v0329_taskset" / "taskset.json"),
                out_dir=str(root / "discovery"),
                use_fixture_only=True,
            )
            from gateforge.agent_modelica_v0_3_30_dual_recheck import build_v0330_dual_recheck

            dual = build_v0330_dual_recheck(
                discovery_path=str(root / "discovery" / "summary.json"),
                surface_index_path=str(root / "surface" / "surface_index.json"),
                entry_taskset_path=str(root / "v0329_taskset" / "taskset.json"),
                out_dir=str(root / "dual"),
                use_fixture_only=True,
            )
            self.assertEqual(first_fix.get("status"), "PASS")
            self.assertEqual(surface.get("summary", {}).get("status"), "PASS")
            self.assertEqual(discovery.get("status"), "PASS")
            self.assertEqual(discovery.get("execution_status"), "executed")
            self.assertEqual(dual.get("status"), "PASS")
            self.assertEqual(dual.get("execution_status"), "executed")

    def test_closeout_returns_discovery_ready_when_all_blocks_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v0329_handoff(root)
            build_v0330_handoff_integrity(
                v0329_closeout_path=str(root / "v0329_closeout" / "summary.json"),
                v0329_entry_spec_path=str(root / "v0329_spec" / "summary.json"),
                v0329_entry_taskset_path=str(root / "v0329_taskset" / "taskset.json"),
                v0329_patch_contract_path=str(root / "v0329_contract" / "summary.json"),
                out_dir=str(root / "handoff"),
            )
            build_v0330_first_fix_evidence(
                entry_taskset_path=str(root / "v0329_taskset" / "taskset.json"),
                out_dir=str(root / "first_fix"),
                use_fixture_only=True,
            )
            build_v0330_surface_index(
                entry_taskset_path=str(root / "v0329_taskset" / "taskset.json"),
                out_dir=str(root / "surface"),
                use_fixture_only=True,
            )
            build_v0330_discovery_evidence(
                first_fix_path=str(root / "first_fix" / "summary.json"),
                surface_index_path=str(root / "surface" / "surface_index.json"),
                entry_taskset_path=str(root / "v0329_taskset" / "taskset.json"),
                out_dir=str(root / "discovery"),
                use_fixture_only=True,
            )
            from gateforge.agent_modelica_v0_3_30_dual_recheck import build_v0330_dual_recheck

            build_v0330_dual_recheck(
                discovery_path=str(root / "discovery" / "summary.json"),
                surface_index_path=str(root / "surface" / "surface_index.json"),
                entry_taskset_path=str(root / "v0329_taskset" / "taskset.json"),
                out_dir=str(root / "dual"),
                use_fixture_only=True,
            )
            payload = build_v0330_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                surface_index_path=str(root / "surface" / "summary.json"),
                first_fix_path=str(root / "first_fix" / "summary.json"),
                discovery_path=str(root / "discovery" / "summary.json"),
                dual_recheck_path=str(root / "dual" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "stage2_medium_redeclare_discovery_ready")

    def test_closeout_returns_handoff_invalid_when_substrate_fails(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "handoff").mkdir(parents=True, exist_ok=True)
            (root / "surface").mkdir(parents=True, exist_ok=True)
            (root / "first_fix").mkdir(parents=True, exist_ok=True)
            (root / "discovery").mkdir(parents=True, exist_ok=True)
            (root / "dual").mkdir(parents=True, exist_ok=True)
            (root / "handoff" / "summary.json").write_text(json.dumps({"handoff_substrate_valid": False}), encoding="utf-8")
            (root / "surface" / "summary.json").write_text(json.dumps({"status": "EMPTY"}), encoding="utf-8")
            (root / "first_fix" / "summary.json").write_text(json.dumps({"status": "EMPTY"}), encoding="utf-8")
            (root / "discovery" / "summary.json").write_text(json.dumps({"status": "SKIPPED", "execution_status": "not_executed_due_to_first_fix_gate"}), encoding="utf-8")
            (root / "dual" / "summary.json").write_text(json.dumps({"status": "SKIPPED", "execution_status": "not_executed_due_to_discovery_gate"}), encoding="utf-8")
            payload = build_v0330_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                surface_index_path=str(root / "surface" / "summary.json"),
                first_fix_path=str(root / "first_fix" / "summary.json"),
                discovery_path=str(root / "discovery" / "summary.json"),
                dual_recheck_path=str(root / "dual" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "handoff_substrate_invalid")


if __name__ == "__main__":
    unittest.main()
