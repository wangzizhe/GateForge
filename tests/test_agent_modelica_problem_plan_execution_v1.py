import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class AgentModelicaProblemPlanExecutionV1Tests(unittest.TestCase):
    def _write_stub_plan(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "plan_rows": [
                        {"failure_type": "underconstrained_system", "target_mutant_count": 1},
                    ]
                }
            ),
            encoding="utf-8",
        )

    def _write_stub_runner(self, path: Path, *, validation_backend_used: str, fallback: bool) -> None:
        script = f"""#!/usr/bin/env bash
set -euo pipefail
OUT="${{GATEFORGE_PRIVATE_BATCH_OUT_DIR:?missing_out_dir}}"
mkdir -p "$OUT"
cat > "$OUT/summary.json" <<'JSON'
{{"bundle_status":"PASS","generated_mutations":1,"reproducible_mutations":1,"failure_types_count":1}}
JSON
cat > "$OUT/mutation_pack_summary.json" <<'JSON'
{{"status":"PASS"}}
JSON
cat > "$OUT/mutation_real_runner_summary.json" <<'JSON'
{{"status":"PASS"}}
JSON
cat > "$OUT/mutation_manifest.json" <<'JSON'
{{
  "mutations": [
    {{
      "mutation_id": "m1",
      "target_scale": "small",
      "failure_type": "model_check_error",
      "expected_failure_type": "model_check_error"
    }}
  ]
}}
JSON
cat > "$OUT/mutation_validation_summary.json" <<'JSON'
{{"status":"NEEDS_REVIEW","validation_backend_used":"{validation_backend_used}","backend_fallback_to_syntax": {str(fallback).lower()},"type_match_rate_pct":0.0,"stage_match_rate_pct":0.0}}
JSON
echo "${{GATEFORGE_TARGET_SCALES:-}}" > "$OUT/target_scales.txt"
echo "${{GATEFORGE_PRIVATE_MODEL_ROOTS:-}}" > "$OUT/private_model_roots.txt"
"""
        path.write_text(script, encoding="utf-8")
        path.chmod(0o755)

    def test_plan_execution_fails_when_plan_missing(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_problem_plan_execution_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "GATEFORGE_AGENT_PROBLEM_PLAN_PATH": str(Path(d) / "missing_plan.json"),
                    "GATEFORGE_AGENT_PROBLEM_PLAN_EXEC_OUT_DIR": str(Path(d) / "out"),
                },
                timeout=60,
            )
            self.assertNotEqual(proc.returncode, 0)
            merged = (proc.stdout or "") + (proc.stderr or "")
            self.assertIn("plan_missing", merged)

    def test_plan_execution_builds_mapping_summary_before_phase_runs(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_problem_plan_execution_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan = root / "plan.json"
            plan.write_text(
                json.dumps(
                    {
                        "plan_rows": [
                            {"failure_type": "underconstrained_system", "target_mutant_count": 10},
                            {"failure_type": "semantic_regression", "target_mutant_count": 5},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "GATEFORGE_AGENT_PROBLEM_PLAN_PATH": str(plan),
                    "GATEFORGE_AGENT_PROBLEM_PLAN_EXEC_OUT_DIR": str(root / "out"),
                    "GATEFORGE_AGENT_MUTATION_BATCH_RUNNER": str(root / "missing_runner.sh"),
                },
                timeout=60,
            )
            self.assertNotEqual(proc.returncode, 0)
            merged = (proc.stdout or "") + (proc.stderr or "")
            self.assertIn("runner_missing", merged)

    def test_plan_execution_strict_omc_fails_when_backend_is_not_omc(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_problem_plan_execution_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan = root / "plan.json"
            runner = root / "runner.sh"
            self._write_stub_plan(plan)
            self._write_stub_runner(runner, validation_backend_used="syntax", fallback=True)
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "GATEFORGE_AGENT_PROBLEM_PLAN_PATH": str(plan),
                    "GATEFORGE_AGENT_PROBLEM_PLAN_EXEC_OUT_DIR": str(root / "out"),
                    "GATEFORGE_AGENT_MUTATION_BATCH_RUNNER": str(runner),
                    "GATEFORGE_AGENT_PROBLEM_PLAN_SKIP_OMC_PREFLIGHT": "1",
                },
                timeout=60,
            )
            self.assertNotEqual(proc.returncode, 0)
            summary = json.loads((root / "out" / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "FAIL")
            self.assertIn("validation_backend_not_real_omc", summary.get("reasons") or [])
            self.assertIn("validation_backend_fallback_to_syntax", summary.get("reasons") or [])

    def test_plan_execution_non_strict_allows_non_omc_backend(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_problem_plan_execution_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan = root / "plan.json"
            runner = root / "runner.sh"
            self._write_stub_plan(plan)
            self._write_stub_runner(runner, validation_backend_used="syntax", fallback=True)
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "GATEFORGE_AGENT_PROBLEM_PLAN_PATH": str(plan),
                    "GATEFORGE_AGENT_PROBLEM_PLAN_EXEC_OUT_DIR": str(root / "out"),
                    "GATEFORGE_AGENT_MUTATION_BATCH_RUNNER": str(runner),
                    "GATEFORGE_AGENT_PROBLEM_PLAN_STRICT_OMC": "0",
                    "GATEFORGE_AGENT_PROBLEM_PLAN_SKIP_OMC_PREFLIGHT": "1",
                },
                timeout=60,
            )
            self.assertEqual(proc.returncode, 0)
            summary = json.loads((root / "out" / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")

    def test_plan_execution_strict_fails_when_validation_match_rate_is_below_threshold(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_problem_plan_execution_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan = root / "plan.json"
            runner = root / "runner.sh"
            self._write_stub_plan(plan)
            self._write_stub_runner(runner, validation_backend_used="openmodelica_docker", fallback=False)
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "GATEFORGE_AGENT_PROBLEM_PLAN_PATH": str(plan),
                    "GATEFORGE_AGENT_PROBLEM_PLAN_EXEC_OUT_DIR": str(root / "out"),
                    "GATEFORGE_AGENT_MUTATION_BATCH_RUNNER": str(runner),
                    "GATEFORGE_AGENT_PROBLEM_PLAN_SKIP_OMC_PREFLIGHT": "1",
                },
                timeout=60,
            )
            self.assertNotEqual(proc.returncode, 0)
            summary = json.loads((root / "out" / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "FAIL")
            self.assertIn("validation_type_match_rate_below_strict_threshold", summary.get("reasons") or [])
            self.assertIn("validation_stage_match_rate_below_strict_threshold", summary.get("reasons") or [])

    def test_plan_execution_strict_defaults_to_all_scales(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_problem_plan_execution_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan = root / "plan.json"
            runner = root / "runner.sh"
            self._write_stub_plan(plan)
            self._write_stub_runner(runner, validation_backend_used="openmodelica_docker", fallback=False)
            subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "GATEFORGE_AGENT_PROBLEM_PLAN_PATH": str(plan),
                    "GATEFORGE_AGENT_PROBLEM_PLAN_EXEC_OUT_DIR": str(root / "out"),
                    "GATEFORGE_AGENT_MUTATION_BATCH_RUNNER": str(runner),
                    "GATEFORGE_AGENT_PROBLEM_PLAN_SKIP_OMC_PREFLIGHT": "1",
                },
                timeout=60,
            )
            for phase in ("phase_check", "phase_sim", "phase_semantic"):
                target_scales_path = root / "out" / phase / "target_scales.txt"
                self.assertTrue(target_scales_path.exists())
                self.assertEqual(target_scales_path.read_text(encoding="utf-8").strip(), "small,medium,large")

    def test_plan_execution_strict_quick_sets_curated_private_roots_by_default(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_problem_plan_execution_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan = root / "plan.json"
            runner = root / "runner.sh"
            self._write_stub_plan(plan)
            self._write_stub_runner(runner, validation_backend_used="openmodelica_docker", fallback=False)
            subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "GATEFORGE_AGENT_PROBLEM_PLAN_PATH": str(plan),
                    "GATEFORGE_AGENT_PROBLEM_PLAN_EXEC_OUT_DIR": str(root / "out"),
                    "GATEFORGE_AGENT_MUTATION_BATCH_RUNNER": str(runner),
                    "GATEFORGE_AGENT_PROBLEM_PLAN_STRICT_OMC": "1",
                    "GATEFORGE_AGENT_PROBLEM_PLAN_EXEC_PROFILE": "quick",
                    "GATEFORGE_AGENT_PROBLEM_PLAN_SKIP_OMC_PREFLIGHT": "1",
                },
                timeout=60,
            )
            expected_roots = (
                "artifacts/run_private_model_mutation_scale_batch_v1_demo/private_models:"
                "artifacts/run_modelica_open_source_growth_sprint_v1_demo/exported/demo_repo_shard_base_a"
            )
            for phase in ("phase_check", "phase_sim", "phase_semantic"):
                roots_path = root / "out" / phase / "private_model_roots.txt"
                self.assertTrue(roots_path.exists())
                self.assertEqual(roots_path.read_text(encoding="utf-8").strip(), expected_roots)


if __name__ == "__main__":
    unittest.main()
