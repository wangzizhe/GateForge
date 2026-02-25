import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetOptionalCIContractTests(unittest.TestCase):
    def test_dataset_optional_chain_writes_required_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "artifacts"
            self._write_required_files(root)
            out = root / "contract" / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_optional_ci_contract",
                    "--artifacts-root",
                    str(root),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(payload.get("fail_count"), 0)

    def test_dataset_optional_chain_summary_schema(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "artifacts"
            self._write_required_files(root)
            # Corrupt one summary by deleting required key.
            bad = root / "dataset_artifacts_pipeline_demo" / "summary.json"
            bad_payload = json.loads(bad.read_text(encoding="utf-8"))
            bad_payload.pop("quality_gate_status", None)
            bad.write_text(json.dumps(bad_payload), encoding="utf-8")
            out = root / "contract" / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_optional_ci_contract",
                    "--artifacts-root",
                    str(root),
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
            failed = [x for x in payload.get("checks", []) if x.get("status") == "FAIL"]
            self.assertTrue(failed)
            self.assertIn("quality_gate_status", failed[0].get("missing_keys", []))

    def _write_required_files(self, root: Path) -> None:
        mapping = {
            "dataset_pipeline_demo/summary.json": {"bundle_status": "PASS", "result_flags": {}},
            "dataset_artifacts_pipeline_demo/summary.json": {"bundle_status": "PASS", "quality_gate_status": "PASS"},
            "dataset_history_demo/summary.json": {"bundle_status": "PASS"},
            "dataset_governance_demo/summary.json": {"bundle_status": "PASS"},
            "dataset_policy_lifecycle_demo/summary.json": {"bundle_status": "PASS"},
            "dataset_governance_history_demo/summary.json": {"bundle_status": "PASS"},
            "dataset_strategy_autotune_demo/summary.json": {"bundle_status": "PASS"},
            "dataset_strategy_autotune_apply_demo/summary.json": {"bundle_status": "PASS"},
            "dataset_strategy_autotune_apply_history_demo/summary.json": {"bundle_status": "PASS"},
            "dataset_governance_snapshot_demo/demo_summary.json": {"bundle_status": "PASS"},
            "dataset_governance_snapshot_trend_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "status_transition": "PASS->PASS",
            },
            "dataset_promotion_candidate_demo/summary.json": {
                "bundle_status": "PASS",
                "decision": "HOLD",
            },
            "dataset_promotion_candidate_apply_demo/summary.json": {
                "bundle_status": "PASS",
            },
            "dataset_promotion_candidate_history_demo/summary.json": {
                "bundle_status": "PASS",
            },
            "dataset_policy_autotune_history_demo/summary.json": {"bundle_status": "PASS"},
        }
        for rel, payload in mapping.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
