from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_4_0_benchmark_freeze import build_v040_benchmark_freeze
from gateforge.agent_modelica_v0_4_1_closeout import build_v041_closeout
from gateforge.agent_modelica_v0_4_1_conditioning_reaudit import build_v041_conditioning_reaudit
from gateforge.agent_modelica_v0_4_1_gain_unlock_gate import build_v041_gain_unlock_gate
from gateforge.agent_modelica_v0_4_1_signal_pack import build_v041_signal_pack
from gateforge.agent_modelica_v0_4_1_signal_source_audit import build_v041_signal_source_audit
from gateforge.agent_modelica_v0_4_1_v0_4_2_handoff import build_v041_v0_4_2_handoff


class AgentModelicaV041SignalRefreshFlowTests(unittest.TestCase):
    def _write_v040_benchmark(self, path: Path, *, per_family: int = 4) -> None:
        tasks = []
        for family_order, family_id in enumerate(
            ["component_api_alignment", "local_interface_alignment", "medium_redeclare_alignment"],
            start=1,
        ):
            for idx in range(per_family):
                tasks.append(
                    {
                        "benchmark_task_id": f"{family_id}|single|{idx}",
                        "family_id": family_id,
                        "family_order": family_order,
                        "task_role": "single",
                        "source_task_id": f"{family_id}_task_{idx}",
                        "patch_type": "replace_symbol",
                        "allowed_patch_types": ["replace_symbol"],
                        "declared_failure_type": "model_check_error",
                        "error_subtype": "undefined_symbol",
                        "dominant_stage_subtype": "stage_2_structural_balance_reference",
                        "residual_signal_cluster": "stage_2_structural_balance_reference|undefined_symbol",
                        "family_target_bucket": "stage_2_structural_balance_reference|undefined_symbol",
                    }
                )
        payload = {
            "benchmark_freeze_ready": True,
            "benchmark_family_count": 3,
            "benchmark_task_count": len(tasks),
            "family_task_breakdown": {
                "component_api_alignment": {"single_task_count": per_family},
                "local_interface_alignment": {"single_task_count": per_family},
                "medium_redeclare_alignment": {"single_task_count": per_family},
            },
            "tasks": tasks,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_v040_audit(self, path: Path) -> None:
        payload = {
            "stage2_conditioning_activation_rate_pct": 0.0,
            "replay_substrate_compatible": True,
            "planner_conditioning_compatible": True,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_v040_handoff(self, path: Path) -> None:
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

    def test_v041_reaches_signal_ready_when_each_family_has_dense_signal(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            benchmark = root / "v040_benchmark" / "benchmark_pack.json"
            legacy_experience = root / "legacy" / "experience_store.json"
            audit = root / "v040_audit" / "summary.json"
            handoff = root / "v040_handoff" / "summary.json"
            self._write_v040_benchmark(benchmark, per_family=4)
            legacy_experience.parent.mkdir(parents=True, exist_ok=True)
            legacy_experience.write_text(json.dumps({"step_records": []}), encoding="utf-8")
            self._write_v040_audit(audit)
            self._write_v040_handoff(handoff)

            source_audit = build_v041_signal_source_audit(
                benchmark_path=str(benchmark),
                legacy_experience_store_path=str(legacy_experience),
                out_dir=str(root / "source_audit"),
            )
            self.assertEqual(source_audit.get("signal_source_mode"), "refreshed_extraction_required")
            signal_pack = build_v041_signal_pack(
                signal_source_audit_path=str(root / "source_audit" / "summary.json"),
                benchmark_path=str(benchmark),
                out_dir=str(root / "signal_pack"),
            )
            self.assertTrue(signal_pack.get("signal_pack_ready"))
            reaudit = build_v041_conditioning_reaudit(
                signal_pack_path=str(root / "signal_pack" / "signal_pack.json"),
                benchmark_path=str(benchmark),
                legacy_audit_path=str(audit),
                out_dir=str(root / "reaudit"),
            )
            self.assertTrue(reaudit.get("conditioning_reactivation_ready"))
            unlock = build_v041_gain_unlock_gate(
                conditioning_reaudit_path=str(root / "reaudit" / "summary.json"),
                out_dir=str(root / "unlock"),
            )
            self.assertTrue(unlock.get("synthetic_gain_measurement_unlocked"))
            build_v041_v0_4_2_handoff(
                gain_unlock_path=str(root / "unlock" / "summary.json"),
                v040_handoff_path=str(handoff),
                out_dir=str(root / "handoff"),
            )
            payload = build_v041_closeout(
                signal_source_audit_path=str(root / "source_audit" / "summary.json"),
                signal_pack_path=str(root / "signal_pack" / "summary.json"),
                conditioning_reaudit_path=str(root / "reaudit" / "summary.json"),
                gain_unlock_path=str(root / "unlock" / "summary.json"),
                v0_4_2_handoff_path=str(root / "handoff" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_4_1_stage2_conditioning_signal_ready")

    def test_v041_stays_partial_when_one_family_has_too_few_signals(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            benchmark = root / "v040_benchmark" / "benchmark_pack.json"
            legacy_experience = root / "legacy" / "experience_store.json"
            audit = root / "v040_audit" / "summary.json"
            handoff = root / "v040_handoff" / "summary.json"
            self._write_v040_benchmark(benchmark, per_family=4)
            payload = json.loads(benchmark.read_text(encoding="utf-8"))
            payload["tasks"] = [row for row in payload["tasks"] if not (row["family_id"] == "medium_redeclare_alignment" and row["source_task_id"].endswith("_3")) and not (row["family_id"] == "medium_redeclare_alignment" and row["source_task_id"].endswith("_2"))]
            payload["benchmark_task_count"] = len(payload["tasks"])
            benchmark.write_text(json.dumps(payload), encoding="utf-8")
            legacy_experience.parent.mkdir(parents=True, exist_ok=True)
            legacy_experience.write_text(json.dumps({"step_records": []}), encoding="utf-8")
            self._write_v040_audit(audit)
            self._write_v040_handoff(handoff)

            build_v041_signal_source_audit(
                benchmark_path=str(benchmark),
                legacy_experience_store_path=str(legacy_experience),
                out_dir=str(root / "source_audit"),
            )
            signal_pack = build_v041_signal_pack(
                signal_source_audit_path=str(root / "source_audit" / "summary.json"),
                benchmark_path=str(benchmark),
                out_dir=str(root / "signal_pack"),
            )
            self.assertFalse(signal_pack.get("signal_pack_ready"))
            build_v041_conditioning_reaudit(
                signal_pack_path=str(root / "signal_pack" / "signal_pack.json"),
                benchmark_path=str(benchmark),
                legacy_audit_path=str(audit),
                out_dir=str(root / "reaudit"),
            )
            build_v041_gain_unlock_gate(
                conditioning_reaudit_path=str(root / "reaudit" / "summary.json"),
                out_dir=str(root / "unlock"),
            )
            build_v041_v0_4_2_handoff(
                gain_unlock_path=str(root / "unlock" / "summary.json"),
                v040_handoff_path=str(handoff),
                out_dir=str(root / "handoff"),
            )
            payload = build_v041_closeout(
                signal_source_audit_path=str(root / "source_audit" / "summary.json"),
                signal_pack_path=str(root / "signal_pack" / "summary.json"),
                conditioning_reaudit_path=str(root / "reaudit" / "summary.json"),
                gain_unlock_path=str(root / "unlock" / "summary.json"),
                v0_4_2_handoff_path=str(root / "handoff" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_4_1_stage2_conditioning_signal_partial")


if __name__ == "__main__":
    unittest.main()
