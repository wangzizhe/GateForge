from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_budget_policy_v0_24_3 import (
    build_budget_policy_report,
    validate_budget_policy,
    validate_manifest_budget,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class BudgetPolicyV0243Tests(unittest.TestCase):
    def test_validate_budget_policy_requires_positive_values(self) -> None:
        errors = validate_budget_policy(
            {"policies": {"bad": {"repeat_count": 0, "max_rounds": 8, "timeout_sec": 420}}}
        )

        self.assertIn("bad:repeat_count_must_be_positive", errors)

    def test_validate_manifest_budget_requires_fields(self) -> None:
        errors = validate_manifest_budget({"budget_metadata": {"repeat_count": 1}})

        self.assertIn("missing_budget_metadata:max_rounds", errors)
        self.assertIn("missing_budget_metadata:timeout_sec", errors)

    def test_build_budget_policy_report_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "manifest.json"
            out_dir = root / "out"
            _write_json(
                manifest,
                {
                    "run_version": "v0.test",
                    "budget_metadata": {
                        "repeat_count": 1,
                        "max_rounds": 8,
                        "timeout_sec": 420,
                        "live_execution": False,
                    },
                },
            )

            summary = build_budget_policy_report(manifest_paths=[manifest], out_dir=out_dir)

            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["validation_error_count"], 0)
            self.assertTrue((out_dir / "budget_policy.json").exists())


if __name__ == "__main__":
    unittest.main()
