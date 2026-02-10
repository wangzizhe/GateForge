import tempfile
import unittest
from pathlib import Path

from gateforge.regression import compare_evidence, write_json


def _evidence(
    run_id: str,
    schema_version: str = "0.1.0",
    backend: str = "mock",
    model_script: str | None = None,
    status: str = "success",
    gate: str = "PASS",
    check_ok: bool = True,
    simulate_ok: bool = True,
    runtime_seconds: float = 1.0,
) -> dict:
    return {
        "run_id": run_id,
        "schema_version": schema_version,
        "backend": backend,
        "model_script": model_script,
        "status": status,
        "gate": gate,
        "check_ok": check_ok,
        "simulate_ok": simulate_ok,
        "metrics": {"runtime_seconds": runtime_seconds},
    }


class RegressionTests(unittest.TestCase):
    def test_compare_pass(self) -> None:
        baseline = _evidence("base", runtime_seconds=1.0)
        candidate = _evidence("cand", runtime_seconds=1.1)
        result = compare_evidence(baseline, candidate, runtime_regression_threshold=0.2)
        self.assertEqual(result["decision"], "PASS")
        self.assertEqual(result["reasons"], [])
        self.assertFalse(result["strict"])

    def test_compare_fail_runtime(self) -> None:
        baseline = _evidence("base", runtime_seconds=1.0)
        candidate = _evidence("cand", runtime_seconds=1.3)
        result = compare_evidence(baseline, candidate, runtime_regression_threshold=0.2)
        self.assertEqual(result["decision"], "FAIL")
        self.assertTrue(any(r.startswith("runtime_regression:") for r in result["reasons"]))

    def test_compare_fail_status(self) -> None:
        baseline = _evidence("base")
        candidate = _evidence("cand", status="failed", gate="FAIL", simulate_ok=False)
        result = compare_evidence(baseline, candidate, runtime_regression_threshold=0.2)
        self.assertEqual(result["decision"], "FAIL")
        self.assertIn("candidate_status_not_success", result["reasons"])

    def test_compare_fail_strict_backend_mismatch(self) -> None:
        baseline = _evidence("base", backend="mock")
        candidate = _evidence("cand", backend="openmodelica_docker")
        result = compare_evidence(
            baseline,
            candidate,
            runtime_regression_threshold=0.2,
            strict=True,
        )
        self.assertEqual(result["decision"], "FAIL")
        self.assertIn("strict_backend_mismatch", result["reasons"])

    def test_compare_fail_strict_schema_mismatch(self) -> None:
        baseline = _evidence("base", schema_version="0.1.0")
        candidate = _evidence("cand", schema_version="0.2.0")
        result = compare_evidence(
            baseline,
            candidate,
            runtime_regression_threshold=0.2,
            strict=True,
        )
        self.assertEqual(result["decision"], "FAIL")
        self.assertIn("strict_schema_version_mismatch", result["reasons"])

    def test_compare_fail_strict_model_script_mismatch(self) -> None:
        baseline = _evidence("base", model_script="examples/openmodelica/minimal_probe.mos")
        candidate = _evidence("cand", model_script="examples/openmodelica/failures/simulate_error.mos")
        result = compare_evidence(
            baseline,
            candidate,
            runtime_regression_threshold=0.2,
            strict=True,
            strict_model_script=True,
        )
        self.assertEqual(result["decision"], "FAIL")
        self.assertIn("strict_model_script_mismatch", result["reasons"])

    def test_write_json(self) -> None:
        payload = {"decision": "PASS", "reasons": []}
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "regression.json"
            write_json(str(out), payload)
            self.assertTrue(out.exists())


if __name__ == "__main__":
    unittest.main()
