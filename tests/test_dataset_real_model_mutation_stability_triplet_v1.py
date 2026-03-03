import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetRealModelMutationStabilityTripletV1Tests(unittest.TestCase):
    def test_stability_triplet_pass_with_low_variance(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            s1 = root / "s1.json"
            s2 = root / "s2.json"
            s3 = root / "s3.json"
            u1 = root / "u1.json"
            u2 = root / "u2.json"
            u3 = root / "u3.json"
            out = root / "summary.json"
            ledger = root / "history.jsonl"

            for p, val in [
                (s1, {"accepted_models": 1000, "accepted_large_models": 250, "generated_mutations": 18000}),
                (s2, {"accepted_models": 995, "accepted_large_models": 248, "generated_mutations": 17920}),
                (s3, {"accepted_models": 1004, "accepted_large_models": 252, "generated_mutations": 18040}),
            ]:
                payload = {
                    "bundle_status": "PASS",
                    "scale_gate_status": "PASS",
                    "accepted_models": val["accepted_models"],
                    "accepted_large_models": val["accepted_large_models"],
                    "generated_mutations": val["generated_mutations"],
                    "reproducible_mutations": val["generated_mutations"],
                    "mutations_per_failure_type": 6,
                }
                p.write_text(json.dumps(payload), encoding="utf-8")
            for p, cnt in [(u1, 1000), (u2, 995), (u3, 1004)]:
                p.write_text(json.dumps({"status": "PASS", "effective_unique_accepted_models": cnt, "duplicate_ratio_pct": 0.0}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_mutation_stability_triplet_v1",
                    "--record-scale-summary",
                    str(s1),
                    "--record-scale-summary",
                    str(s2),
                    "--record-scale-summary",
                    str(s3),
                    "--record-uniqueness-summary",
                    str(u1),
                    "--record-uniqueness-summary",
                    str(u2),
                    "--record-uniqueness-summary",
                    str(u3),
                    "--ledger",
                    str(ledger),
                    "--window-size",
                    "3",
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
            self.assertEqual(int(payload.get("window_size", 0) or 0), 3)

    def test_stability_triplet_needs_review_when_window_not_full(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            s1 = root / "s1.json"
            u1 = root / "u1.json"
            out = root / "summary.json"
            ledger = root / "history.jsonl"

            s1.write_text(
                json.dumps(
                    {
                        "bundle_status": "PASS",
                        "scale_gate_status": "PASS",
                        "accepted_models": 1000,
                        "accepted_large_models": 250,
                        "generated_mutations": 18000,
                        "reproducible_mutations": 18000,
                    }
                ),
                encoding="utf-8",
            )
            u1.write_text(json.dumps({"status": "PASS", "effective_unique_accepted_models": 1000, "duplicate_ratio_pct": 0.0}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_mutation_stability_triplet_v1",
                    "--record-scale-summary",
                    str(s1),
                    "--record-uniqueness-summary",
                    str(u1),
                    "--ledger",
                    str(ledger),
                    "--window-size",
                    "3",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("stability_window_not_full", payload.get("alerts", []))


if __name__ == "__main__":
    unittest.main()
