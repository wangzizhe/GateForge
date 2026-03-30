from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_may_checkpoint_decision_v0_3_2 import build_may_checkpoint_decision


class AgentModelicaMayCheckpointDecisionV032Tests(unittest.TestCase):
    def test_build_may_checkpoint_decision_retains_comparative_path_when_conditions_hold(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_may_decision_") as td:
            root = Path(td)
            matrix = root / "matrix.json"
            matrix.write_text(
                json.dumps(
                    {
                        "grouped_rows": [
                            {
                                "provider_name": "gateforge",
                                "arm_id": "gateforge_authority",
                                "model_id": "gateforge-v0.3.2/authority",
                                "infra_normalized_success_rate_pct": 100.0,
                                "infra_failure_rate_pct": 0.0,
                            },
                            {
                                "provider_name": "claude",
                                "arm_id": "arm2",
                                "model_id": "claude-sonnet-test",
                                "infra_normalized_success_rate_pct": 75.0,
                                "infra_failure_rate_pct": 0.0,
                            },
                        ],
                        "variance_summary": [
                            {"provider_name": "claude", "run_count": 3},
                            {"provider_name": "codex", "run_count": 1},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            claude_probe = root / "claude_probe.json"
            claude_probe.write_text(json.dumps({"shared_tool_plane_reached": True}), encoding="utf-8")
            codex_probe = root / "codex_probe.json"
            codex_probe.write_text(json.dumps({"shared_tool_plane_reached": True}), encoding="utf-8")
            slice_summary = root / "slice.json"
            slice_summary.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            decision = build_may_checkpoint_decision(
                matrix_summary_path=str(matrix),
                claude_probe_summary_path=str(claude_probe),
                codex_probe_summary_path=str(codex_probe),
                slice_summary_path=str(slice_summary),
                out_dir=str(root / "out"),
            )
            self.assertEqual(decision["status"], "PASS")
            self.assertEqual(decision["classification"], "comparative_path_retained")
            self.assertTrue(decision["claim_drafts"]["strong_comparative_claim_candidate"])

    def test_build_may_checkpoint_decision_locks_fallback_when_repeats_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_may_decision_") as td:
            root = Path(td)
            matrix = root / "matrix.json"
            matrix.write_text(
                json.dumps(
                    {
                        "grouped_rows": [
                            {
                                "provider_name": "gateforge",
                                "arm_id": "gateforge_authority",
                                "model_id": "gateforge-v0.3.2/authority",
                                "infra_normalized_success_rate_pct": 100.0,
                                "infra_failure_rate_pct": 0.0,
                            },
                            {
                                "provider_name": "claude",
                                "arm_id": "arm2",
                                "model_id": "claude-sonnet-test",
                                "infra_normalized_success_rate_pct": 50.0,
                                "infra_failure_rate_pct": 0.0,
                            },
                        ],
                        "variance_summary": [
                            {"provider_name": "claude", "run_count": 1},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            claude_probe = root / "claude_probe.json"
            claude_probe.write_text(json.dumps({"shared_tool_plane_reached": True}), encoding="utf-8")
            decision = build_may_checkpoint_decision(
                matrix_summary_path=str(matrix),
                claude_probe_summary_path=str(claude_probe),
                out_dir=str(root / "out"),
            )
            self.assertEqual(decision["classification"], "fallback_path_locked")
            self.assertFalse(decision["conditions"]["primary_external_repeated_runs_met"])

    def test_build_may_checkpoint_decision_marks_provisional_when_slice_not_paper_ready(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_may_decision_") as td:
            root = Path(td)
            matrix = root / "matrix.json"
            matrix.write_text(
                json.dumps(
                    {
                        "grouped_rows": [
                            {
                                "provider_name": "gateforge",
                                "arm_id": "gateforge_authority",
                                "model_id": "gateforge-v0.3.2/authority",
                                "infra_normalized_success_rate_pct": 100.0,
                                "infra_failure_rate_pct": 0.0,
                            },
                            {
                                "provider_name": "claude",
                                "arm_id": "arm2",
                                "model_id": "claude-sonnet-test",
                                "infra_normalized_success_rate_pct": 80.0,
                                "infra_failure_rate_pct": 16.67,
                            },
                        ],
                        "variance_summary": [
                            {"provider_name": "claude", "run_count": 3, "mean_infra_failure_rate_pct": 16.67},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            claude_probe = root / "claude_probe.json"
            claude_probe.write_text(json.dumps({"shared_tool_plane_reached": True}), encoding="utf-8")
            slice_summary = root / "slice.json"
            slice_summary.write_text(json.dumps({"status": "PRELIMINARY_NEEDS_MORE_EVIDENCE"}), encoding="utf-8")
            decision = build_may_checkpoint_decision(
                matrix_summary_path=str(matrix),
                claude_probe_summary_path=str(claude_probe),
                slice_summary_path=str(slice_summary),
                out_dir=str(root / "out"),
            )
            self.assertEqual(decision["classification"], "comparative_path_retained_provisional")
            self.assertTrue(decision["claim_drafts"]["conservative_claim_candidate"])


if __name__ == "__main__":
    unittest.main()
