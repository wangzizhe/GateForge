import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationSelectionBalanceGuardV1Tests(unittest.TestCase):
    def test_balance_guard_pass_or_review_with_valid_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan = root / "plan_summary.json"
            pack = root / "pack_summary.json"
            out = root / "summary.json"
            plan.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "selected_models": 20,
                        "selected_large_ratio_pct": 45.0,
                        "selected_families": 5,
                        "selected_source_buckets": 3,
                        "max_family_share_pct": 38.0,
                    }
                ),
                encoding="utf-8",
            )
            pack.write_text(json.dumps({"selected_models": 20, "total_mutations": 200}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_selection_balance_guard_v1",
                    "--selection-plan-summary",
                    str(plan),
                    "--mutation-pack-summary",
                    str(pack),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW"})

    def test_balance_guard_fail_when_plan_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_selection_balance_guard_v1",
                    "--selection-plan-summary",
                    str(root / "missing_plan.json"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "FAIL")


if __name__ == "__main__":
    unittest.main()
