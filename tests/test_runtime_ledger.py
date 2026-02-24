import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.runtime_ledger import build_runtime_record, summarize_runtime_ledger


class RuntimeLedgerTests(unittest.TestCase):
    def test_build_runtime_record_from_run(self) -> None:
        summary = {
            "proposal_id": "p-1",
            "status": "PASS",
            "policy_decision": "PASS",
            "risk_level": "low",
            "policy_profile": "default",
            "policy_version": "0.1.0",
            "fail_reasons": [],
            "policy_reasons": [],
            "required_human_checks": [],
        }
        record = build_runtime_record(summary, source="run")
        self.assertEqual(record["source"], "run")
        self.assertEqual(record["proposal_id"], "p-1")
        self.assertEqual(record["status"], "PASS")
        self.assertEqual(record["required_human_checks_count"], 0)

    def test_summarize_runtime_ledger(self) -> None:
        rows = [
            {"status": "PASS", "source": "run", "policy_decision": "PASS", "fail_reasons": [], "policy_reasons": []},
            {
                "status": "FAIL",
                "source": "autopilot",
                "policy_decision": "FAIL",
                "fail_reasons": ["regression_fail"],
                "policy_reasons": ["regression_fail"],
            },
            {
                "status": "NEEDS_REVIEW",
                "source": "autopilot",
                "policy_decision": "NEEDS_REVIEW",
                "fail_reasons": ["runtime_regression:1.0>0.6"],
                "policy_reasons": ["runtime_regression:1.0>0.6"],
            },
        ]
        summary = summarize_runtime_ledger(rows)
        self.assertEqual(summary["total_records"], 3)
        self.assertEqual(summary["status_counts"].get("PASS"), 1)
        self.assertEqual(summary["status_counts"].get("FAIL"), 1)
        self.assertEqual(summary["status_counts"].get("NEEDS_REVIEW"), 1)
        self.assertEqual(summary["source_counts"].get("autopilot"), 2)

    def test_cli_append_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ledger = root / "ledger.jsonl"
            in_summary = root / "summary.json"
            out_summary = root / "ledger_summary.json"
            in_summary.write_text(
                json.dumps(
                    {
                        "proposal_id": "p-cli-1",
                        "status": "PASS",
                        "policy_decision": "PASS",
                        "risk_level": "low",
                        "policy_profile": "default",
                        "fail_reasons": [],
                        "policy_reasons": [],
                        "required_human_checks": [],
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.runtime_ledger",
                    "--ledger",
                    str(ledger),
                    "--append-summary",
                    str(in_summary),
                    "--source",
                    "run",
                    "--summary-out",
                    str(out_summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out_summary.read_text(encoding="utf-8"))
            self.assertEqual(payload["total_records"], 1)


if __name__ == "__main__":
    unittest.main()
