import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetBuildTests(unittest.TestCase):
    def test_dataset_build_from_mixed_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bench = root / "bench.json"
            mut = root / "mut.json"
            run = root / "run.json"
            auto = root / "auto.json"
            out_dir = root / "out"

            bench.write_text(
                json.dumps(
                    {
                        "pack_id": "pack_v0",
                        "cases": [
                            {
                                "name": "bench-pass",
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
            mut.write_text(
                json.dumps(
                    {
                        "pack_id": "mutation_pack_v1",
                        "cases": [
                            {
                                "name": "mut-fail",
                                "backend": "mock",
                                "script": "examples/mutants/v0/case.mos",
                                "result": "PASS",
                                "failure_type": "script_parse_error",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            run.write_text(
                json.dumps(
                    {
                        "proposal_id": "run-1",
                        "backend": "mock",
                        "model_script": "examples/openmodelica/minimal_probe.mos",
                        "status": "PASS",
                        "policy_decision": "PASS",
                        "fail_reasons": [],
                        "risk_level": "low",
                    }
                ),
                encoding="utf-8",
            )
            auto.write_text(
                json.dumps(
                    {
                        "proposal_id": "auto-1",
                        "backend": "mock",
                        "model_script": "examples/openmodelica/minimal_probe.mos",
                        "status": "FAIL",
                        "policy_decision": "NEEDS_REVIEW",
                        "fail_reasons": ["runtime_regression:1.0>0.6"],
                        "risk_level": "medium",
                        "required_human_checks": ["check-a"],
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_build",
                    "--benchmark-summary",
                    str(bench),
                    "--mutation-summary",
                    str(mut),
                    "--run-summary",
                    str(run),
                    "--autopilot-summary",
                    str(auto),
                    "--out-dir",
                    str(out_dir),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            quality = json.loads((out_dir / "quality_report.json").read_text(encoding="utf-8"))
            distribution = json.loads((out_dir / "distribution.json").read_text(encoding="utf-8"))
            lines = [x for x in (out_dir / "dataset_cases.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]

            self.assertEqual(summary.get("total_cases"), 4)
            self.assertEqual(summary.get("deduplicated_cases"), 4)
            self.assertEqual(len(lines), 4)
            self.assertEqual(quality.get("total_cases"), 4)
            self.assertIn("benchmark", distribution.get("source", {}))
            self.assertIn("mutation", distribution.get("source", {}))
            self.assertIn("run", distribution.get("source", {}))
            self.assertIn("autopilot", distribution.get("source", {}))
            self.assertIn("PASS", distribution.get("actual_decision", {}))
            self.assertIn("NEEDS_REVIEW", distribution.get("actual_decision", {}))

    def test_dataset_build_deduplicates_case_id(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bench = root / "bench.json"
            out_dir = root / "out"
            # identical name/backend/script => identical case_id from adapter
            bench.write_text(
                json.dumps(
                    {
                        "pack_id": "pack_v0",
                        "cases": [
                            {
                                "name": "dup-case",
                                "backend": "mock",
                                "script": "examples/openmodelica/minimal_probe.mos",
                                "result": "PASS",
                                "failure_type": "none",
                            },
                            {
                                "name": "dup-case",
                                "backend": "mock",
                                "script": "examples/openmodelica/minimal_probe.mos",
                                "result": "PASS",
                                "failure_type": "none",
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
                    "gateforge.dataset_build",
                    "--benchmark-summary",
                    str(bench),
                    "--out-dir",
                    str(out_dir),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("total_cases"), 2)
            self.assertEqual(summary.get("deduplicated_cases"), 1)
            self.assertEqual(summary.get("dropped_duplicate_cases"), 1)

    def test_dataset_build_accepts_glob_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out_dir = root / "out"
            inputs = root / "inputs"
            inputs.mkdir(parents=True, exist_ok=True)

            (inputs / "bench_a.json").write_text(
                json.dumps(
                    {
                        "pack_id": "pack_v0",
                        "cases": [
                            {
                                "name": "bench-a",
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
            (inputs / "run_a.json").write_text(
                json.dumps(
                    {
                        "proposal_id": "run-glob-1",
                        "backend": "mock",
                        "model_script": "examples/openmodelica/minimal_probe.mos",
                        "status": "PASS",
                        "policy_decision": "PASS",
                        "fail_reasons": [],
                        "risk_level": "low",
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_build",
                    "--benchmark-summary-glob",
                    str(inputs / "bench_*.json"),
                    "--run-summary-glob",
                    str(inputs / "run_*.json"),
                    "--out-dir",
                    str(out_dir),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("total_cases"), 2)
            self.assertEqual(summary.get("inputs", {}).get("benchmark_summary_count"), 1)
            self.assertEqual(summary.get("inputs", {}).get("run_summary_count"), 1)
            self.assertEqual(len(summary.get("inputs", {}).get("benchmark_summary_paths", [])), 1)
            self.assertEqual(len(summary.get("inputs", {}).get("run_summary_paths", [])), 1)


if __name__ == "__main__":
    unittest.main()
