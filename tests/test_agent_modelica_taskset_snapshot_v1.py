import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaTasksetSnapshotV1Tests(unittest.TestCase):
    def test_snapshot_builds_fixed_counts(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            taskset = root / "taskset.json"
            summary = root / "summary.json"

            rows = []
            idx = 0
            for scale in ["small", "medium", "large"]:
                for ftype in ["model_check_error", "simulate_error", "semantic_regression"]:
                    for _ in range(4):
                        idx += 1
                        rows.append(
                            {
                                "mutation_id": f"m{idx}",
                                "target_scale": scale,
                                "expected_failure_type": ftype,
                            }
                        )
            manifest.write_text(json.dumps({"mutations": rows}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_taskset_snapshot_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--per-scale-total",
                    "6",
                    "--per-scale-failure-targets",
                    "2,2,2",
                    "--taskset-out",
                    str(taskset),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            s = json.loads(summary.read_text(encoding="utf-8"))
            t = json.loads(taskset.read_text(encoding="utf-8"))
            self.assertEqual(s.get("status"), "PASS")
            self.assertEqual(int(s.get("total_tasks", 0)), 18)
            self.assertEqual(len(t.get("tasks", [])), 18)
            self.assertEqual(s.get("quota_mode"), "target")
            self.assertEqual((s.get("counts_by_scale") or {}).get("small"), 6)
            self.assertEqual((s.get("counts_by_scale") or {}).get("medium"), 6)
            self.assertEqual((s.get("counts_by_scale") or {}).get("large"), 6)

    def test_snapshot_adaptive_quota_downshifts_when_supply_is_limited(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            taskset = root / "taskset.json"
            summary = root / "summary.json"

            rows = []
            idx = 0
            for scale in ["small", "medium", "large"]:
                for _ in range(1):
                    idx += 1
                    rows.append({"mutation_id": f"m{idx}", "target_scale": scale, "expected_failure_type": "model_check_error"})
                for _ in range(2):
                    idx += 1
                    rows.append({"mutation_id": f"m{idx}", "target_scale": scale, "expected_failure_type": "simulate_error"})
                for _ in range(1):
                    idx += 1
                    rows.append({"mutation_id": f"m{idx}", "target_scale": scale, "expected_failure_type": "semantic_regression"})
            manifest.write_text(json.dumps({"mutations": rows}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_taskset_snapshot_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--per-scale-total",
                    "6",
                    "--per-scale-failure-targets",
                    "2,2,2",
                    "--adaptive-quota",
                    "--taskset-out",
                    str(taskset),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            s = json.loads(summary.read_text(encoding="utf-8"))
            self.assertEqual(s.get("quota_mode"), "adaptive")
            self.assertEqual(int(s.get("per_scale_total_effective", 0)), 4)
            gap = s.get("coverage_gap") or {}
            self.assertEqual(int(gap.get("shortfall_total_tasks", 0)), 6)


if __name__ == "__main__":
    unittest.main()
