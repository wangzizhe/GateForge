import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaLearningAssetReadinessV1Tests(unittest.TestCase):
    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_readiness_pass_with_non_overlap_and_min_rows(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_learning_ready_") as td:
            root = Path(td)
            memory = root / "memory.json"
            failure_schema = root / "failure_signature_v1.schema.json"
            operator_schema = root / "repair_operator_v1.schema.json"
            memory_schema = root / "repair_memory_v1.schema.json"
            quality = root / "data_quality_gate_v1.json"
            replay = root / "replay_eval_v1.json"
            promotion = root / "promotion_v1.json"
            out = root / "summary.json"

            self._write_json(
                memory,
                {
                    "schema_version": "agent_modelica_repair_memory_v1",
                    "rows": [
                        {
                            "fingerprint": "fp1",
                            "task_id": "t1",
                            "failure_type": "simulate_error",
                            "scale": "small",
                            "used_strategy": "s1",
                            "action_trace": ["a1"],
                            "error_signature": "sig_a",
                            "gate_break_reason": "none",
                            "success": True,
                            "split": "train",
                        },
                        {
                            "fingerprint": "fp2",
                            "task_id": "t2",
                            "failure_type": "simulate_error",
                            "scale": "small",
                            "used_strategy": "s2",
                            "action_trace": ["a2"],
                            "error_signature": "sig_b",
                            "gate_break_reason": "none",
                            "success": True,
                            "split": "holdout",
                        },
                    ],
                },
            )
            self._write_json(failure_schema, {"type": "object"})
            self._write_json(operator_schema, {"type": "object"})
            self._write_json(memory_schema, {"type": "object"})
            self._write_json(
                quality,
                {
                    "required_row_fields": [
                        "fingerprint",
                        "task_id",
                        "failure_type",
                        "scale",
                        "used_strategy",
                        "action_trace",
                        "error_signature",
                        "gate_break_reason",
                        "success",
                    ],
                    "target_failure_types": ["simulate_error"],
                    "min_total_rows": 2,
                    "max_missing_required_ratio": 0.0,
                    "max_duplicate_fingerprint_ratio": 0.0,
                    "min_success_rows_per_failure_type": 1,
                    "require_non_overlap_holdout": True,
                    "split_field": "split",
                    "train_values": ["train"],
                    "holdout_values": ["holdout"],
                },
            )
            self._write_json(
                replay,
                {
                    "frozen_pack_path": "benchmarks/a.json",
                    "holdout_pack_path": "benchmarks/b.json",
                    "primary_metrics": ["success_at_k_pct"],
                    "hard_regression_caps": {"max_regression_count_increase": 0},
                },
            )
            self._write_json(
                promotion,
                {
                    "min_success_count_per_failure_type": 1,
                    "min_success_rate_gain_pct": 0.5,
                    "max_regression_increase": 0,
                    "max_physics_fail_increase": 0,
                },
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_learning_asset_readiness_v1",
                    "--memory",
                    str(memory),
                    "--failure-signature-schema",
                    str(failure_schema),
                    "--repair-operator-schema",
                    str(operator_schema),
                    "--repair-memory-schema",
                    str(memory_schema),
                    "--data-quality-policy",
                    str(quality),
                    "--replay-eval-policy",
                    str(replay),
                    "--promotion-policy",
                    str(promotion),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")

    def test_readiness_fail_on_holdout_overlap(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_learning_fail_") as td:
            root = Path(td)
            memory = root / "memory.json"
            failure_schema = root / "failure_signature_v1.schema.json"
            operator_schema = root / "repair_operator_v1.schema.json"
            memory_schema = root / "repair_memory_v1.schema.json"
            quality = root / "data_quality_gate_v1.json"
            replay = root / "replay_eval_v1.json"
            promotion = root / "promotion_v1.json"
            out = root / "summary.json"

            self._write_json(
                memory,
                {
                    "schema_version": "agent_modelica_repair_memory_v1",
                    "rows": [
                        {
                            "fingerprint": "fp1",
                            "task_id": "t1",
                            "failure_type": "simulate_error",
                            "scale": "small",
                            "used_strategy": "s1",
                            "action_trace": ["a1"],
                            "error_signature": "sig_dup",
                            "gate_break_reason": "none",
                            "success": True,
                            "split": "train",
                        },
                        {
                            "fingerprint": "fp2",
                            "task_id": "t2",
                            "failure_type": "simulate_error",
                            "scale": "small",
                            "used_strategy": "s2",
                            "action_trace": ["a2"],
                            "error_signature": "sig_dup",
                            "gate_break_reason": "none",
                            "success": True,
                            "split": "holdout",
                        },
                    ],
                },
            )
            self._write_json(failure_schema, {"type": "object"})
            self._write_json(operator_schema, {"type": "object"})
            self._write_json(memory_schema, {"type": "object"})
            self._write_json(
                quality,
                {
                    "required_row_fields": [
                        "fingerprint",
                        "task_id",
                        "failure_type",
                        "scale",
                        "used_strategy",
                        "action_trace",
                        "error_signature",
                        "gate_break_reason",
                        "success",
                    ],
                    "target_failure_types": ["simulate_error"],
                    "min_total_rows": 2,
                    "max_missing_required_ratio": 0.0,
                    "max_duplicate_fingerprint_ratio": 0.0,
                    "min_success_rows_per_failure_type": 1,
                    "require_non_overlap_holdout": True,
                    "split_field": "split",
                    "train_values": ["train"],
                    "holdout_values": ["holdout"],
                },
            )
            self._write_json(
                replay,
                {
                    "frozen_pack_path": "benchmarks/a.json",
                    "holdout_pack_path": "benchmarks/b.json",
                    "primary_metrics": ["success_at_k_pct"],
                    "hard_regression_caps": {"max_regression_count_increase": 0},
                },
            )
            self._write_json(
                promotion,
                {
                    "min_success_count_per_failure_type": 1,
                    "min_success_rate_gain_pct": 0.5,
                    "max_regression_increase": 0,
                    "max_physics_fail_increase": 0,
                },
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_learning_asset_readiness_v1",
                    "--memory",
                    str(memory),
                    "--failure-signature-schema",
                    str(failure_schema),
                    "--repair-operator-schema",
                    str(operator_schema),
                    "--repair-memory-schema",
                    str(memory_schema),
                    "--data-quality-policy",
                    str(quality),
                    "--replay-eval-policy",
                    str(replay),
                    "--promotion-policy",
                    str(promotion),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(proc.returncode, 1)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "FAIL")
            self.assertEqual((summary.get("checks") or {}).get("non_overlap_holdout"), "FAIL")


if __name__ == "__main__":
    unittest.main()
