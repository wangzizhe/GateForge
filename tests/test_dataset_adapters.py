import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.dataset_adapters import (
    adapt_benchmark_summary,
    adapt_mutation_benchmark_summary,
    adapt_run_summary,
    validate_cases,
)


class DatasetAdaptersTests(unittest.TestCase):
    def test_adapt_benchmark_summary(self) -> None:
        summary = {
            "pack_id": "pack_v0",
            "cases": [
                {
                    "name": "pass_case",
                    "backend": "mock",
                    "script": "examples/openmodelica/minimal_probe.mos",
                    "result": "PASS",
                    "failure_type": "none",
                    "mismatches": [],
                    "json_path": "artifacts/case1.json",
                },
                {
                    "name": "fail_case",
                    "backend": "mock",
                    "script": "examples/openmodelica/failures/simulate_error.mos",
                    "result": "FAIL",
                    "failure_type": "simulate_error",
                    "mismatches": ["failure_type:expected=none,actual=simulate_error"],
                    "json_path": "artifacts/case2.json",
                },
            ],
        }
        cases = adapt_benchmark_summary(summary)
        self.assertEqual(len(cases), 2)
        self.assertEqual(cases[0]["source"], "benchmark")
        self.assertTrue(cases[0]["oracle_match"])
        self.assertEqual(cases[1]["actual_decision"], "FAIL")
        validate_cases(cases)

    def test_adapt_mutation_benchmark_summary(self) -> None:
        summary = {
            "pack_id": "mutation_pack_v1",
            "cases": [
                {
                    "name": "m_case",
                    "backend": "mock",
                    "script": "examples/mutants/v0/case.mos",
                    "result": "PASS",
                    "failure_type": "script_parse_error",
                }
            ],
        }
        cases = adapt_mutation_benchmark_summary(summary)
        self.assertEqual(cases[0]["source"], "mutation")
        self.assertEqual(cases[0]["factors"]["trigger"], "mutation_rule")
        validate_cases(cases)

    def test_adapt_run_summary(self) -> None:
        summary = {
            "proposal_id": "proposal-run-1",
            "backend": "mock",
            "model_script": "examples/openmodelica/minimal_probe.mos",
            "status": "FAIL",
            "policy_decision": "NEEDS_REVIEW",
            "fail_reasons": ["runtime_regression:1.0>0.6"],
            "risk_level": "medium",
            "required_human_checks": ["check A", "check B"],
        }
        case = adapt_run_summary(summary, source="autopilot")
        self.assertEqual(case["source"], "autopilot")
        self.assertEqual(case["actual_decision"], "NEEDS_REVIEW")
        self.assertEqual(case["actual_failure_type"], "runtime_regression")
        self.assertEqual(case["factors"]["trigger"], "llm_plan")
        self.assertEqual(case["factors"]["root_cause"], "performance")
        self.assertEqual(case["factors"]["severity"], "medium")
        validate_cases([case])

    def test_adapt_run_summary_governance_reason_mapping(self) -> None:
        summary = {
            "proposal_id": "run-guard-1",
            "backend": "mock",
            "model_script": "examples/openmodelica/minimal_probe.mos",
            "status": "FAIL",
            "policy_decision": "FAIL",
            "fail_reasons": ["change_apply_failed"],
            "risk_level": "high",
        }
        case = adapt_run_summary(summary, source="run")
        self.assertEqual(case["actual_failure_type"], "change_apply_failed")
        self.assertEqual(case["factors"]["root_cause"], "governance")
        self.assertEqual(case["factors"]["severity"], "high")
        validate_cases([case])

    def test_cli_benchmark_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            inp = root / "summary.json"
            out = root / "dataset_cases.json"
            inp.write_text(
                json.dumps(
                    {
                        "pack_id": "pack_v0",
                        "cases": [
                            {
                                "name": "pass_case",
                                "backend": "mock",
                                "script": "examples/openmodelica/minimal_probe.mos",
                                "result": "PASS",
                                "failure_type": "none",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_adapters",
                    "--kind",
                    "benchmark",
                    "--in",
                    str(inp),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(len(payload), 1)
            self.assertEqual(payload[0]["source"], "benchmark")


if __name__ == "__main__":
    unittest.main()
