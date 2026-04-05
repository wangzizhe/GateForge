from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_4_2_benchmark_lock import build_v042_benchmark_lock
from gateforge.agent_modelica_v0_4_2_closeout import build_v042_closeout
from gateforge.agent_modelica_v0_4_2_dispatch_audit import build_v042_dispatch_audit
from gateforge.agent_modelica_v0_4_2_real_backcheck import build_v042_real_backcheck
from gateforge.agent_modelica_v0_4_2_synthetic_gain_measurement import build_v042_synthetic_gain_measurement
from gateforge.agent_modelica_v0_4_2_v0_4_3_handoff import build_v042_v0_4_3_handoff


class AgentModelicaV042GainFlowTests(unittest.TestCase):
    def _write_benchmark(self, path: Path) -> None:
        tasks = []
        for family_id in (
            "component_api_alignment",
            "local_interface_alignment",
            "medium_redeclare_alignment",
        ):
            for idx in range(10):
                tasks.append(
                    {
                        "benchmark_task_id": f"{family_id}|single|{idx}",
                        "family_id": family_id,
                        "task_role": "single",
                        "complexity_tier": "simple" if idx == 0 else "medium",
                    }
                )
            for idx in range(6):
                tasks.append(
                    {
                        "benchmark_task_id": f"{family_id}|dual|{idx}",
                        "family_id": family_id,
                        "task_role": "dual",
                        "complexity_tier": "medium",
                    }
                )
        payload = {
            "benchmark_freeze_ready": True,
            "benchmark_task_count": len(tasks),
            "tasks": tasks,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_signal_pack(self, path: Path, *, count: int) -> None:
        rows = []
        for idx in range(count):
            rows.append({"signal_id": f"signal_{idx}"})
        payload = {"signal_rows": rows}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_handoff(self, path: Path) -> None:
        payload = {
            "v0_4_2_policy_eval_scope": {
                "policy_mechanism": "stage-gated_with_arbitration",
                "dispatch_priority_rule": [
                    "Prefer the narrowest bounded patch contract first.",
                    "Default precedence: component_api_alignment -> local_interface_alignment -> medium_redeclare_alignment.",
                    "Escalate only if the earlier family does not produce signature advance.",
                ],
            }
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_generation_census(self, path: Path) -> None:
        payload = {"schema_version": "agent_modelica_v0_3_17_generation_census", "status": "PASS"}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_diagnosis(self, path: Path) -> None:
        payload = {
            "schema_version": "agent_modelica_v0_3_18_stage2_diagnosis",
            "records": [
                {
                    "task_id": "real_api_simple",
                    "complexity_tier": "simple",
                    "proposed_action_type": "component_api_alignment",
                    "targeting_recommendation": "target",
                    "first_failure": {
                        "dominant_stage_subtype": "stage_2_structural_balance_reference",
                        "error_subtype": "undefined_symbol",
                    },
                },
                {
                    "task_id": "real_api_medium",
                    "complexity_tier": "medium",
                    "proposed_action_type": "component_api_alignment",
                    "targeting_recommendation": "target",
                    "first_failure": {
                        "dominant_stage_subtype": "stage_2_structural_balance_reference",
                        "error_subtype": "undefined_symbol",
                    },
                },
                {
                    "task_id": "real_medium_redeclare",
                    "complexity_tier": "medium",
                    "proposed_action_type": "medium_redeclare_alignment",
                    "targeting_recommendation": "exclude",
                    "first_failure": {
                        "dominant_stage_subtype": "stage_2_structural_balance_reference",
                        "error_subtype": "undefined_symbol",
                    },
                },
            ],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_v042_reports_synthetic_gain_supported_with_partial_real_backcheck(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            benchmark = root / "benchmark" / "benchmark_pack.json"
            signal_pack = root / "signal" / "signal_pack.json"
            handoff = root / "handoff" / "summary.json"
            generation = root / "generation" / "summary.json"
            diagnosis = root / "diagnosis" / "records.json"
            self._write_benchmark(benchmark)
            self._write_signal_pack(signal_pack, count=48)
            self._write_handoff(handoff)
            self._write_generation_census(generation)
            self._write_diagnosis(diagnosis)

            build_v042_benchmark_lock(
                benchmark_path=str(benchmark),
                signal_pack_path=str(signal_pack),
                v0_4_1_handoff_path=str(handoff),
                out_dir=str(root / "benchmark_lock"),
            )
            build_v042_synthetic_gain_measurement(
                benchmark_lock_path=str(root / "benchmark_lock" / "benchmark_pack.json"),
                out_dir=str(root / "synthetic_gain"),
            )
            build_v042_dispatch_audit(
                benchmark_lock_path=str(root / "benchmark_lock" / "benchmark_pack.json"),
                out_dir=str(root / "dispatch"),
            )
            real_backcheck = build_v042_real_backcheck(
                generation_census_path=str(generation),
                diagnosis_records_path=str(diagnosis),
                out_dir=str(root / "real"),
            )
            self.assertEqual(real_backcheck.get("real_backcheck_status"), "partial_positive")
            build_v042_v0_4_3_handoff(
                synthetic_gain_path=str(root / "synthetic_gain" / "summary.json"),
                dispatch_audit_path=str(root / "dispatch" / "summary.json"),
                real_backcheck_path=str(root / "real" / "summary.json"),
                out_dir=str(root / "handoff_v043"),
            )
            payload = build_v042_closeout(
                benchmark_lock_path=str(root / "benchmark_lock" / "summary.json"),
                synthetic_gain_path=str(root / "synthetic_gain" / "summary.json"),
                dispatch_audit_path=str(root / "dispatch" / "summary.json"),
                real_backcheck_path=str(root / "real" / "summary.json"),
                v0_4_3_handoff_path=str(root / "handoff_v043" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                (payload.get("conclusion") or {}).get("version_decision"),
                "v0_4_2_synthetic_gain_supported_real_backcheck_partial",
            )

    def test_v042_reports_policy_invalid_when_dispatch_audit_fails(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            benchmark_lock = root / "benchmark_lock.json"
            synthetic_gain = root / "synthetic_gain.json"
            dispatch = root / "dispatch.json"
            real_backcheck = root / "real.json"
            handoff = root / "handoff.json"
            benchmark_lock.write_text(
                json.dumps({"synthetic_benchmark_ready": True, "policy_baseline_locked": True}),
                encoding="utf-8",
            )
            synthetic_gain.write_text(
                json.dumps({"conditioning_gain_supported": True, "conditioning_gain_status": "supported"}),
                encoding="utf-8",
            )
            dispatch.write_text(
                json.dumps({"policy_baseline_valid": False, "policy_failure_mode": "overlap_ambiguous"}),
                encoding="utf-8",
            )
            real_backcheck.write_text(
                json.dumps({"real_backcheck_status": "partial_positive"}),
                encoding="utf-8",
            )
            handoff.write_text(
                json.dumps({"v0_4_3_primary_eval_question": "x", "v0_4_3_handoff_mode": "refine_dispatch_policy"}),
                encoding="utf-8",
            )
            payload = build_v042_closeout(
                benchmark_lock_path=str(benchmark_lock),
                synthetic_gain_path=str(synthetic_gain),
                dispatch_audit_path=str(dispatch),
                real_backcheck_path=str(real_backcheck),
                v0_4_3_handoff_path=str(handoff),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                (payload.get("conclusion") or {}).get("version_decision"),
                "v0_4_2_policy_baseline_invalid",
            )


if __name__ == "__main__":
    unittest.main()
