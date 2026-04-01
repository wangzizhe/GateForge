from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_independent_verifier_v1 import (
    verify_post_restore_evidence_flow,
)


class AgentModelicaIndependentVerifierV1Tests(unittest.TestCase):
    def test_verify_post_restore_evidence_flow_passes_on_aligned_inputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_independent_verifier_v1_") as td:
            root = Path(td)
            lane = root / "lane.json"
            run = root / "run.json"
            promotion = root / "promotion.json"
            classifier = root / "classifier.json"
            lane.write_text(json.dumps({"lane_status": "FREEZE_READY"}), encoding="utf-8")
            run.write_text(
                json.dumps(
                    {
                        "total": 2,
                        "passed": 2,
                        "deterministic_only_pct": 0.0,
                        "results": [
                            {"task_id": "a", "resolution_path": "rule_then_llm"},
                            {"task_id": "b", "resolution_path": "rule_then_llm"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            promotion.write_text(
                json.dumps(
                    {
                        "status": "PROMOTION_READY",
                        "observed_metrics": {
                            "total_cases": 2,
                            "passed_cases": 2,
                            "rule_then_llm_count": 2,
                            "deterministic_only_pct": 0.0,
                        },
                    }
                ),
                encoding="utf-8",
            )
            classifier.write_text(
                json.dumps(
                    {
                        "metrics": {
                            "total_rows": 2,
                            "failure_bucket_counts": {"success_after_restore": 2},
                        }
                    }
                ),
                encoding="utf-8",
            )
            payload = verify_post_restore_evidence_flow(
                lane_summary_path=str(lane),
                run_summary_path=str(run),
                promotion_summary_path=str(promotion),
                classifier_summary_path=str(classifier),
                out_dir=str(root / "out"),
            )
        self.assertEqual(payload.get("status"), "PASS")
        self.assertEqual((payload.get("summary") or {}).get("failed_checks"), [])

    def test_verify_post_restore_evidence_flow_fails_on_misaligned_counts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_independent_verifier_v1_fail_") as td:
            root = Path(td)
            lane = root / "lane.json"
            run = root / "run.json"
            promotion = root / "promotion.json"
            classifier = root / "classifier.json"
            lane.write_text(json.dumps({"lane_status": "FREEZE_READY"}), encoding="utf-8")
            run.write_text(json.dumps({"total": 2, "passed": 1, "results": []}), encoding="utf-8")
            promotion.write_text(json.dumps({"status": "PROMOTION_READY", "observed_metrics": {"total_cases": 3, "passed_cases": 1, "rule_then_llm_count": 0, "deterministic_only_pct": 0.0}}), encoding="utf-8")
            classifier.write_text(json.dumps({"metrics": {"total_rows": 2, "failure_bucket_counts": {"success_after_restore": 1}}}), encoding="utf-8")
            payload = verify_post_restore_evidence_flow(
                lane_summary_path=str(lane),
                run_summary_path=str(run),
                promotion_summary_path=str(promotion),
                classifier_summary_path=str(classifier),
                out_dir=str(root / "out"),
            )
        self.assertEqual(payload.get("status"), "FAIL")
        self.assertIn("counts_align_across_summaries", (payload.get("summary") or {}).get("failed_checks") or [])
