import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaLearningPreflightV1Tests(unittest.TestCase):
    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_preflight_pass_with_minimum_ready_inputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_preflight_") as td:
            root = Path(td)
            profile = root / "profile.json"
            hardpack = root / "hardpack.json"
            memory = root / "memory.json"
            dq = root / "dq.json"
            replay = root / "replay.json"
            promotion = root / "promotion.json"
            fs = root / "failure_signature.schema.json"
            ro = root / "repair_operator.schema.json"
            rm = root / "repair_memory.schema.json"
            out = root / "summary.json"

            self._write_json(
                profile,
                {
                    "taskset": {"hardpack_path": str(hardpack)},
                    "privacy": {"repair_history_path": str(memory)},
                },
            )
            self._write_json(hardpack, {"cases": [{"task_id": "t1"}]})
            self._write_json(
                memory,
                {
                    "rows": [
                        {
                            "fingerprint": "fp1",
                            "task_id": "t1",
                            "failure_type": "simulate_error",
                            "scale": "small",
                            "used_strategy": "s1",
                            "action_trace": ["a1"],
                            "error_signature": "sig1",
                            "gate_break_reason": "none",
                            "success": True,
                            "split": "train",
                        },
                        {
                            "fingerprint": "fp2",
                            "task_id": "t2",
                            "failure_type": "model_check_error",
                            "scale": "small",
                            "used_strategy": "s2",
                            "action_trace": ["a2"],
                            "error_signature": "sig2",
                            "gate_break_reason": "none",
                            "success": True,
                            "split": "holdout",
                        },
                        {
                            "fingerprint": "fp3",
                            "task_id": "t3",
                            "failure_type": "semantic_regression",
                            "scale": "small",
                            "used_strategy": "s3",
                            "action_trace": ["a3"],
                            "error_signature": "sig3",
                            "gate_break_reason": "none",
                            "success": True,
                            "split": "train",
                        },
                    ]
                },
            )
            self._write_json(
                dq,
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
                    "target_failure_types": ["simulate_error", "model_check_error", "semantic_regression"],
                    "min_total_rows": 3,
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
            self._write_json(fs, {"type": "object"})
            self._write_json(ro, {"type": "object"})
            self._write_json(rm, {"type": "object"})

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_learning_preflight_v1",
                    "--profile",
                    str(profile),
                    "--data-quality-policy",
                    str(dq),
                    "--replay-eval-policy",
                    str(replay),
                    "--promotion-policy",
                    str(promotion),
                    "--failure-signature-schema",
                    str(fs),
                    "--repair-operator-schema",
                    str(ro),
                    "--repair-memory-schema",
                    str(rm),
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


if __name__ == "__main__":
    unittest.main()
