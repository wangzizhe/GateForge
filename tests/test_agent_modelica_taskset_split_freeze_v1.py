import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaTasksetSplitFreezeV1Tests(unittest.TestCase):
    def test_split_freeze_assigns_train_and_holdout(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_split_freeze_") as td:
            root = Path(td)
            taskset = root / "taskset.json"
            out_taskset = root / "taskset_out.json"
            out = root / "summary.json"
            tasks = []
            for i in range(20):
                tasks.append(
                    {
                        "task_id": f"t{i}",
                        "failure_type": "simulate_error",
                        "scale": "small",
                        "mutated_model_path": f"m{i}.mo",
                    }
                )
            taskset.write_text(json.dumps({"tasks": tasks}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_taskset_split_freeze_v1",
                    "--taskset-in",
                    str(taskset),
                    "--holdout-ratio",
                    "0.2",
                    "--out-taskset",
                    str(out_taskset),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out_taskset.read_text(encoding="utf-8"))
            rows = [x for x in payload.get("tasks", []) if isinstance(x, dict)]
            self.assertEqual(len(rows), 20)
            holdout = [x for x in rows if str(x.get("split") or "").strip() == "holdout"]
            self.assertGreaterEqual(len(holdout), 1)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")

    def test_split_freeze_keeps_existing_splits_without_force(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_split_freeze_") as td:
            root = Path(td)
            taskset = root / "taskset.json"
            out_taskset = root / "taskset_out.json"
            out = root / "summary.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "t1", "split": "train"},
                            {"task_id": "t2", "split": "holdout"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_taskset_split_freeze_v1",
                    "--taskset-in",
                    str(taskset),
                    "--out-taskset",
                    str(out_taskset),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out_taskset.read_text(encoding="utf-8"))
            rows = [x for x in payload.get("tasks", []) if isinstance(x, dict)]
            self.assertEqual(str(rows[0].get("split")), "train")
            self.assertEqual(str(rows[1].get("split")), "holdout")


if __name__ == "__main__":
    unittest.main()
