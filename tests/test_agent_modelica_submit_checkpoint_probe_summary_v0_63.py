from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_submit_checkpoint_probe_summary_v0_63_0 import (
    build_submit_checkpoint_probe_summary,
    run_submit_checkpoint_probe_summary,
)


class SubmitCheckpointProbeSummaryV063Tests(unittest.TestCase):
    def test_build_summary_promotes_submit_slice_only(self) -> None:
        summary = build_submit_checkpoint_probe_summary(
            attribution_summary={
                "gateforge_failure_attribution_counts": {
                    "successful_candidate_not_submitted": 2,
                    "zero_flow_pattern_underfit": 3,
                },
                "paired_rows": [
                    {
                        "paired_outcome": "gateforge_fail_external_pass",
                        "gateforge_failure_attribution": "successful_candidate_not_submitted",
                    },
                    {
                        "paired_outcome": "gateforge_fail_external_pass",
                        "gateforge_failure_attribution": "zero_flow_pattern_underfit",
                    },
                ],
            },
            submit_slice={
                "artifact_complete": True,
                "case_count": 2,
                "completed_case_count": 2,
                "pass_count": 2,
                "provider_error_count": 0,
            },
            remaining_slice={
                "artifact_complete": False,
                "case_count": 5,
                "completed_case_count": 2,
                "pass_count": 1,
                "provider_error_count": 0,
            },
        )
        self.assertTrue(summary["submit_failure_slice_recovered"])
        self.assertEqual(
            summary["decision"],
            "promote_transparent_submit_checkpoint_for_submit_failure_slice_only",
        )
        self.assertTrue(summary["remaining_probe_partial"])
        self.assertFalse(summary["discipline"]["wrapper_auto_submit_added"])

    def test_run_summary_writes_output(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            attribution = root / "attr.json"
            attribution.write_text(
                json.dumps(
                    {
                        "gateforge_failure_attribution_counts": {
                            "successful_candidate_not_submitted": 1
                        },
                        "paired_rows": [],
                    }
                ),
                encoding="utf-8",
            )
            submit_dir = root / "submit"
            remaining_dir = root / "remaining"
            out_dir = root / "out"
            submit_dir.mkdir()
            remaining_dir.mkdir()
            (submit_dir / "summary.json").write_text(
                json.dumps({"artifact_complete": True, "case_count": 1, "completed_case_count": 1, "pass_count": 1}),
                encoding="utf-8",
            )
            (remaining_dir / "summary.json").write_text(
                json.dumps({"artifact_complete": False, "case_count": 1, "completed_case_count": 1, "pass_count": 0}),
                encoding="utf-8",
            )
            summary = run_submit_checkpoint_probe_summary(
                attribution_path=attribution,
                submit_slice_dir=submit_dir,
                remaining_slice_dir=remaining_dir,
                out_dir=out_dir,
            )
            self.assertEqual(summary["submit_failure_slice_pass_count"], 1)
            self.assertTrue((out_dir / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
