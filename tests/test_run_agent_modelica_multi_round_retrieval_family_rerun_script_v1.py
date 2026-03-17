import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class RunAgentModelicaMultiRoundRetrievalFamilyRerunScriptV1Tests(unittest.TestCase):
    def test_prepare_only_builds_filtered_family_run_root(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_multi_round_retrieval_family_rerun_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out_dir = root / "out"
            src = out_dir / "runs" / "src_run"
            for name in ("challenge", "curated_retrieval", "baseline_off_live", "deterministic_on_live"):
                (src / name).mkdir(parents=True, exist_ok=True)
            tasks = [
                {"task_id": "a", "failure_type": "coupled_conflict_failure", "multi_round_family": "coupled_conflict", "expected_rounds_min": 2, "cascade_depth": 2, "source_meta": {"library_id": "liba"}},
                {"task_id": "b", "failure_type": "cascading_structural_failure", "multi_round_family": "cascade", "expected_rounds_min": 2, "cascade_depth": 2, "source_meta": {"library_id": "libb"}},
            ]
            (src / "challenge" / "taskset_frozen.json").write_text(json.dumps({"tasks": tasks}, indent=2), encoding="utf-8")
            (src / "challenge" / "summary.json").write_text(json.dumps({"status": "PASS", "taskset_frozen_path": str(src / "challenge" / "taskset_frozen.json")}, indent=2), encoding="utf-8")
            (src / "curated_retrieval" / "summary.json").write_text(json.dumps({"status": "PASS"}, indent=2), encoding="utf-8")
            (src / "curated_retrieval" / "history.json").write_text(json.dumps({"rows": []}, indent=2), encoding="utf-8")
            baseline_results = {"records": [{"task_id": "a", "passed": False}, {"task_id": "b", "passed": True}]}
            det_results = {"records": [{"task_id": "a", "passed": True, "time_to_pass_sec": 12.0}, {"task_id": "b", "passed": True, "time_to_pass_sec": 8.0}]}
            (src / "baseline_off_live" / "results.json").write_text(json.dumps(baseline_results, indent=2), encoding="utf-8")
            (src / "baseline_off_live" / "summary.json").write_text(json.dumps({"status": "NEEDS_REVIEW", "success_count": 1, "total_tasks": 2, "success_at_k_pct": 50.0}, indent=2), encoding="utf-8")
            (src / "deterministic_on_live" / "results.json").write_text(json.dumps(det_results, indent=2), encoding="utf-8")
            (src / "deterministic_on_live" / "summary.json").write_text(json.dumps({"status": "PASS", "success_count": 2, "total_tasks": 2, "success_at_k_pct": 100.0}, indent=2), encoding="utf-8")
            (src / "run_manifest.json").write_text(json.dumps({"manifest_path": "manifest.json"}, indent=2), encoding="utf-8")
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "GATEFORGE_AGENT_MULTI_ROUND_FAILURE_LIVE_EVIDENCE_OUT_DIR": str(out_dir),
                    "GATEFORGE_AGENT_MULTI_ROUND_SOURCE_RUN_ID": "src_run",
                    "GATEFORGE_AGENT_MULTI_ROUND_RETRIEVAL_FAMILY": "coupled_conflict_failure",
                    "GATEFORGE_AGENT_MULTI_ROUND_FAILURE_RUN_ID": "family_rerun",
                    "GATEFORGE_AGENT_MULTI_ROUND_FAMILY_RERUN_PREPARE_ONLY": "1",
                },
                timeout=120,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            rerun_root = out_dir / "runs" / "family_rerun"
            filtered_taskset = json.loads((rerun_root / "challenge" / "taskset_frozen.json").read_text(encoding="utf-8"))
            self.assertEqual(len(filtered_taskset.get("tasks") or []), 1)
            self.assertEqual((filtered_taskset.get("tasks") or [{}])[0].get("failure_type"), "coupled_conflict_failure")
            baseline_filtered = json.loads((rerun_root / "baseline_off_live" / "results.json").read_text(encoding="utf-8"))
            self.assertEqual(len(baseline_filtered.get("records") or []), 1)
            self.assertEqual((baseline_filtered.get("records") or [{}])[0].get("task_id"), "a")
            stage_status = json.loads((rerun_root / "stages" / "deterministic_on_live" / "stage_status.json").read_text(encoding="utf-8"))
            self.assertEqual(stage_status.get("status"), "PASS")


if __name__ == "__main__":
    unittest.main()
