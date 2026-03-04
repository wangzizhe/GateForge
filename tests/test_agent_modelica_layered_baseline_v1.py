import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _evidence(metrics: dict, *, check_ok: bool = True, simulate_ok: bool = True) -> dict:
    return {
        "status": "success" if check_ok and simulate_ok else "failed",
        "gate": "PASS" if check_ok and simulate_ok else "FAIL",
        "check_ok": check_ok,
        "simulate_ok": simulate_ok,
        "metrics": metrics,
    }


class AgentModelicaLayeredBaselineV1Tests(unittest.TestCase):
    def test_layered_baseline_summary_contains_required_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "mutation_manifest.json"
            history = root / "history.json"
            out_dir = root / "out"
            summary = root / "summary.json"

            rows = []
            idx = 0
            for scale in ["small", "medium", "large"]:
                for ftype in ["model_check_error", "simulate_error", "semantic_regression"]:
                    idx += 1
                    rows.append(
                        {
                            "mutation_id": f"m{idx}",
                            "target_scale": scale,
                            "expected_failure_type": ftype,
                            "source_model_path": f"{scale}_{ftype}.mo",
                            "mutated_model_path": f"{scale}_{ftype}_mut.mo",
                        }
                    )

            manifest.write_text(json.dumps({"mutations": rows}), encoding="utf-8")
            history.write_text(json.dumps({"rows": []}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_layered_baseline_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--out-dir",
                    str(out_dir),
                    "--repair-history",
                    str(history),
                    "--max-per-scale",
                    "3",
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(summary.read_text(encoding="utf-8"))
            self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW"})
            self.assertEqual(payload.get("total_tasks"), 9)
            self.assertIn("success_at_k_pct", payload)
            self.assertIn("median_time_to_pass_sec", payload)
            self.assertIn("median_repair_rounds", payload)
            self.assertIn("regression_count", payload)
            self.assertIn("physics_fail_count", payload)
            self.assertEqual(str(((payload.get("sources") or {}).get("repair_history") or "")), str(history))
            layered = payload.get("layered_pass_rate_pct_by_scale") or {}
            self.assertEqual(set(layered.keys()), {"small", "medium", "large"})

    def test_layered_baseline_injection_creates_failed_distribution(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset_evidence.json"
            out_dir = root / "out"
            summary = root / "summary.json"
            run_summary = out_dir / "run_summary.json"
            acceptance = out_dir / "acceptance_summary.json"

            tasks = []
            idx = 0
            for scale in ["small", "medium", "large"]:
                for ftype in ["model_check_error", "simulate_error", "semantic_regression"]:
                    idx += 1
                    runtime = 2.0 if scale == "small" else (3.0 if scale == "medium" else 4.0)
                    tasks.append(
                        {
                            "task_id": f"t_{idx}",
                            "scale": scale,
                            "failure_type": ftype,
                            "expected_stage": "check" if ftype == "model_check_error" else "simulate",
                            "observed_repair_rounds": 2,
                            "observed_elapsed_sec": int(runtime * 20),
                            "baseline_evidence": _evidence({"steady_state_error": 0.01, "runtime_seconds": runtime}),
                            "candidate_evidence": _evidence({"steady_state_error": 0.01, "runtime_seconds": runtime + 0.1}),
                        }
                    )
            taskset.write_text(json.dumps({"schema_version": "agent_modelica_taskset_v1", "mode": "evidence", "tasks": tasks}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_layered_baseline_v1",
                    "--taskset-in",
                    str(taskset),
                    "--run-mode",
                    "evidence",
                    "--inject-hard-fail-count",
                    "3",
                    "--out-dir",
                    str(out_dir),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            s = json.loads(summary.read_text(encoding="utf-8"))
            rs = json.loads(run_summary.read_text(encoding="utf-8"))
            a = json.loads(acceptance.read_text(encoding="utf-8"))
            self.assertEqual(s.get("status"), "FAIL")
            self.assertEqual(s.get("run_mode"), "evidence")
            self.assertGreaterEqual(int(s.get("physics_fail_count", 0) + s.get("regression_count", 0)), 1)
            self.assertEqual(int(rs.get("total_tasks", 0)), 9)
            self.assertGreater(int(a.get("fail_count", 0)), 0)
            self.assertEqual(int(s.get("inject_hard_fail_count", 0)), 3)


if __name__ == "__main__":
    unittest.main()
