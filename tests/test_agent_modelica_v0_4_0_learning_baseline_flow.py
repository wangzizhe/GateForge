from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_4_0_benchmark_freeze import build_v040_benchmark_freeze
from gateforge.agent_modelica_v0_4_0_closeout import build_v040_closeout
from gateforge.agent_modelica_v0_4_0_conditioning_reactivation_audit import build_v040_conditioning_reactivation_audit
from gateforge.agent_modelica_v0_4_0_synthetic_baseline import build_v040_synthetic_baseline
from gateforge.agent_modelica_v0_4_0_v0_4_1_handoff import build_v040_v0_4_1_handoff


class AgentModelicaV040LearningBaselineFlowTests(unittest.TestCase):
    def _write_family_taskset(self, path: Path, *, prefix: str, dual_key: str) -> None:
        singles = []
        duals = []
        for idx in range(3):
            singles.append(
                {
                    "task_id": f"{prefix}_single_{idx}",
                    "complexity_tier": "simple",
                    "patch_type": "replace_symbol",
                    "allowed_patch_types": ["replace_symbol"],
                    "declared_failure_type": "model_check_error",
                    "wrong_symbol": f"wrong_{idx}",
                    "correct_symbol": f"correct_{idx}",
                }
            )
        for idx in range(2):
            duals.append(
                {
                    "task_id": f"{prefix}_dual_{idx}",
                    "complexity_tier": "medium",
                    "patch_type": "replace_symbol",
                    "allowed_patch_types": ["replace_symbol"],
                    "declared_failure_type": "model_check_error",
                    "wrong_symbol": f"dual_wrong_{idx}",
                    "correct_symbol": f"dual_correct_{idx}",
                }
            )
        payload = {
            "single_tasks": singles,
            dual_key: duals,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_v0334_handoff(self, path: Path) -> None:
        payload = {
            "v0_4_multi_family_policy_requirement": {
                "policy_mechanism": "stage-gated_with_arbitration",
                "dispatch_priority_rule": [
                    "Prefer the narrowest bounded patch contract first.",
                    "Default precedence: component_api_alignment -> local_interface_alignment -> medium_redeclare_alignment.",
                ],
            }
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_v040_reports_partial_when_stage2_conditioning_signal_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            api = root / "v0322" / "active_taskset.json"
            iface = root / "v0328" / "active_taskset.json"
            medium = root / "v0333" / "active_taskset.json"
            self._write_family_taskset(api, prefix="api", dual_key="dual_sidecar_tasks")
            self._write_family_taskset(iface, prefix="iface", dual_key="dual_sidecar_tasks")
            self._write_family_taskset(medium, prefix="medium", dual_key="dual_tasks")
            handoff = root / "v0334" / "summary.json"
            self._write_v0334_handoff(handoff)
            experience = root / "experience_store.json"
            experience.write_text(
                json.dumps(
                    {
                        "step_records": [
                            {
                                "dominant_stage_subtype": "stage_5_runtime_numerical_instability",
                                "residual_signal_cluster": "stage_5_runtime_numerical_instability|division_by_zero",
                                "rule_id": "rule_runtime",
                                "action_key": "repair|runtime|rule_engine_v1",
                                "action_type": "runtime_patch",
                                "step_outcome": "advancing",
                                "replay_eligible": True,
                                "rule_tier": "mutation_contract_rule",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            family_sources = [
                {"family_id": "component_api_alignment", "taskset_path": str(api), "single_key": "single_tasks", "dual_key": "dual_sidecar_tasks", "source_closeout_path": str(api)},
                {"family_id": "local_interface_alignment", "taskset_path": str(iface), "single_key": "single_tasks", "dual_key": "dual_sidecar_tasks", "source_closeout_path": str(iface)},
                {"family_id": "medium_redeclare_alignment", "taskset_path": str(medium), "single_key": "single_tasks", "dual_key": "dual_tasks", "source_closeout_path": str(medium)},
            ]
            freeze = build_v040_benchmark_freeze(
                out_dir=str(root / "freeze"),
                single_tasks_per_family=2,
                dual_tasks_per_family=1,
                family_sources=family_sources,
            )
            audit = build_v040_conditioning_reactivation_audit(
                benchmark_freeze_path=str(root / "freeze" / "benchmark_pack.json"),
                experience_store_path=str(experience),
                out_dir=str(root / "audit"),
            )
            self.assertFalse(audit.get("conditioning_reactivation_ready"))
            self.assertEqual(audit.get("primary_bottleneck"), "stage2_aligned_conditioning_signal_missing")
            build_v040_synthetic_baseline(
                benchmark_freeze_path=str(root / "freeze" / "benchmark_pack.json"),
                conditioning_audit_path=str(root / "audit" / "summary.json"),
                out_dir=str(root / "baseline"),
            )
            build_v040_v0_4_1_handoff(
                conditioning_audit_path=str(root / "audit" / "summary.json"),
                synthetic_baseline_path=str(root / "baseline" / "summary.json"),
                v0334_handoff_path=str(handoff),
                out_dir=str(root / "handoff"),
            )
            payload = build_v040_closeout(
                benchmark_freeze_path=str(root / "freeze" / "summary.json"),
                conditioning_audit_path=str(root / "audit" / "summary.json"),
                synthetic_baseline_path=str(root / "baseline" / "summary.json"),
                v0_4_1_handoff_path=str(root / "handoff" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_4_0_conditioning_substrate_partial")

    def test_v040_can_reach_synthetic_baseline_ready_with_stage2_signal(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            api = root / "v0322" / "active_taskset.json"
            iface = root / "v0328" / "active_taskset.json"
            medium = root / "v0333" / "active_taskset.json"
            self._write_family_taskset(api, prefix="api", dual_key="dual_sidecar_tasks")
            self._write_family_taskset(iface, prefix="iface", dual_key="dual_sidecar_tasks")
            self._write_family_taskset(medium, prefix="medium", dual_key="dual_tasks")
            handoff = root / "v0334" / "summary.json"
            self._write_v0334_handoff(handoff)
            experience = root / "experience_store.json"
            experience.write_text(
                json.dumps(
                    {
                        "step_records": [
                            {
                                "dominant_stage_subtype": "stage_2_structural_balance_reference",
                                "residual_signal_cluster": "stage_2_structural_balance_reference|undefined_symbol",
                                "rule_id": "rule_stage2",
                                "action_key": "repair|stage2_symbol|rule_engine_v1",
                                "action_type": "replace_symbol",
                                "step_outcome": "advancing",
                                "replay_eligible": True,
                                "rule_tier": "mutation_contract_rule",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            family_sources = [
                {"family_id": "component_api_alignment", "taskset_path": str(api), "single_key": "single_tasks", "dual_key": "dual_sidecar_tasks", "source_closeout_path": str(api)},
                {"family_id": "local_interface_alignment", "taskset_path": str(iface), "single_key": "single_tasks", "dual_key": "dual_sidecar_tasks", "source_closeout_path": str(iface)},
                {"family_id": "medium_redeclare_alignment", "taskset_path": str(medium), "single_key": "single_tasks", "dual_key": "dual_tasks", "source_closeout_path": str(medium)},
            ]
            build_v040_benchmark_freeze(
                out_dir=str(root / "freeze"),
                single_tasks_per_family=2,
                dual_tasks_per_family=1,
                family_sources=family_sources,
            )
            audit = build_v040_conditioning_reactivation_audit(
                benchmark_freeze_path=str(root / "freeze" / "benchmark_pack.json"),
                experience_store_path=str(experience),
                out_dir=str(root / "audit"),
            )
            self.assertTrue(audit.get("conditioning_reactivation_ready"))
            build_v040_synthetic_baseline(
                benchmark_freeze_path=str(root / "freeze" / "benchmark_pack.json"),
                conditioning_audit_path=str(root / "audit" / "summary.json"),
                out_dir=str(root / "baseline"),
            )
            build_v040_v0_4_1_handoff(
                conditioning_audit_path=str(root / "audit" / "summary.json"),
                synthetic_baseline_path=str(root / "baseline" / "summary.json"),
                v0334_handoff_path=str(handoff),
                out_dir=str(root / "handoff"),
            )
            payload = build_v040_closeout(
                benchmark_freeze_path=str(root / "freeze" / "summary.json"),
                conditioning_audit_path=str(root / "audit" / "summary.json"),
                synthetic_baseline_path=str(root / "baseline" / "summary.json"),
                v0_4_1_handoff_path=str(root / "handoff" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_4_0_synthetic_learning_baseline_ready")


if __name__ == "__main__":
    unittest.main()
