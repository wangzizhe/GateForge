import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaHoldoutTasksetBuilderV1Tests(unittest.TestCase):
    def test_excludes_used_mutation_ids_and_keeps_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            exclude_taskset = root / "exclude.json"
            out_taskset = root / "taskset.json"
            out_summary = root / "summary.json"

            rows = []
            idx = 0
            for scale in ["small", "medium", "large"]:
                for ftype in ["model_check_error", "simulate_error", "semantic_regression"]:
                    for _ in range(2):
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
            exclude_taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"mutation_id": "m1"},
                            {"mutation_id": "m3"},
                            {"mutation_id": "m5"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_holdout_taskset_builder_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--exclude-taskset",
                    str(exclude_taskset),
                    "--max-per-scale-failure-type",
                    "1",
                    "--taskset-out",
                    str(out_taskset),
                    "--out",
                    str(out_summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out_summary.read_text(encoding="utf-8"))
            self.assertIn(summary.get("status"), {"PASS", "NEEDS_REVIEW"})
            self.assertEqual(int(summary.get("total_tasks", 0)), 9)
            taskset = json.loads(out_taskset.read_text(encoding="utf-8"))
            tasks = taskset.get("tasks") if isinstance(taskset.get("tasks"), list) else []
            mids = {str(x.get("mutation_id") or "") for x in tasks if isinstance(x, dict)}
            self.assertNotIn("m1", mids)
            self.assertNotIn("m3", mids)
            self.assertNotIn("m5", mids)


if __name__ == "__main__":
    unittest.main()
