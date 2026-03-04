import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _ev(metrics: dict, *, check_ok: bool = True, simulate_ok: bool = True) -> dict:
    return {
        "status": "success" if check_ok and simulate_ok else "failed",
        "gate": "PASS" if check_ok and simulate_ok else "FAIL",
        "check_ok": check_ok,
        "simulate_ok": simulate_ok,
        "metrics": metrics,
    }


class AgentModelicaEvidenceStressInjectorV1Tests(unittest.TestCase):
    def test_injects_hard_fail_and_slow_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            out_taskset = root / "out_taskset.json"
            summary = root / "summary.json"
            taskset.write_text(
                json.dumps(
                    {
                        "schema_version": "agent_modelica_taskset_v1",
                        "mode": "evidence",
                        "tasks": [
                            {
                                "task_id": "t1",
                                "scale": "small",
                                "failure_type": "model_check_error",
                                "baseline_evidence": _ev({"steady_state_error": 0.01, "runtime_seconds": 2.0}),
                                "candidate_evidence": _ev({"steady_state_error": 0.01, "runtime_seconds": 2.2}),
                            },
                            {
                                "task_id": "t2",
                                "scale": "medium",
                                "failure_type": "simulate_error",
                                "baseline_evidence": _ev({"steady_state_error": 0.01, "runtime_seconds": 3.0}),
                                "candidate_evidence": _ev({"steady_state_error": 0.01, "runtime_seconds": 3.1}),
                            },
                            {
                                "task_id": "t3",
                                "scale": "large",
                                "failure_type": "semantic_regression",
                                "baseline_evidence": _ev({"steady_state_error": 0.01, "runtime_seconds": 4.0}),
                                "candidate_evidence": _ev({"steady_state_error": 0.02, "runtime_seconds": 4.0}),
                            },
                            {
                                "task_id": "t4",
                                "scale": "small",
                                "failure_type": "model_check_error",
                                "baseline_evidence": _ev({"steady_state_error": 0.01, "runtime_seconds": 2.0}),
                                "candidate_evidence": _ev({"steady_state_error": 0.01, "runtime_seconds": 2.0}),
                            },
                            {
                                "task_id": "t5",
                                "scale": "medium",
                                "failure_type": "simulate_error",
                                "baseline_evidence": _ev({"steady_state_error": 0.01, "runtime_seconds": 3.0}),
                                "candidate_evidence": _ev({"steady_state_error": 0.01, "runtime_seconds": 3.0}),
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_evidence_stress_injector_v1",
                    "--taskset-in",
                    str(taskset),
                    "--hard-fail-count",
                    "3",
                    "--slow-pass-count",
                    "1",
                    "--out-taskset",
                    str(out_taskset),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            s = json.loads(summary.read_text(encoding="utf-8"))
            self.assertEqual(s.get("status"), "PASS")
            self.assertEqual(int(s.get("hard_fail_injected", 0)), 3)
            self.assertEqual(int(s.get("slow_pass_injected", 0)), 1)

            out = json.loads(out_taskset.read_text(encoding="utf-8"))
            rows = out.get("tasks") if isinstance(out.get("tasks"), list) else []
            self.assertEqual(len(rows), 5)
            classes = [str(x.get("_stress_class") or "") for x in rows]
            self.assertEqual(classes.count("hard_fail"), 3)
            self.assertEqual(classes.count("slow_pass"), 1)

            model_fail = [x for x in rows if x.get("failure_type") == "model_check_error" and x.get("_stress_class") == "hard_fail"]
            self.assertTrue(model_fail)
            m_cand = model_fail[0]["candidate_evidence"]
            self.assertFalse(bool(m_cand.get("check_ok")))
            self.assertFalse(bool(m_cand.get("simulate_ok")))

            semantic_fail = [x for x in rows if x.get("failure_type") == "semantic_regression" and x.get("_stress_class") == "hard_fail"]
            self.assertTrue(semantic_fail)
            self.assertTrue(isinstance(semantic_fail[0].get("physical_invariants"), list))
            self.assertGreater(float(semantic_fail[0]["candidate_evidence"]["metrics"]["steady_state_error"]), 0.05)

    def test_returns_needs_review_on_shortfall(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            out_taskset = root / "out_taskset.json"
            summary = root / "summary.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t1",
                                "scale": "small",
                                "failure_type": "simulate_error",
                                "baseline_evidence": _ev({"runtime_seconds": 2.0}),
                                "candidate_evidence": _ev({"runtime_seconds": 2.0}),
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_evidence_stress_injector_v1",
                    "--taskset-in",
                    str(taskset),
                    "--hard-fail-count",
                    "3",
                    "--out-taskset",
                    str(out_taskset),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            s = json.loads(summary.read_text(encoding="utf-8"))
            self.assertEqual(s.get("status"), "NEEDS_REVIEW")
            self.assertIn("hard_fail_injection_shortfall", s.get("reasons", []))


if __name__ == "__main__":
    unittest.main()
