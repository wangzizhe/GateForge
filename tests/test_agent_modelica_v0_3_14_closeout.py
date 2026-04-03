from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_14_closeout import build_v0_3_14_closeout


class AgentModelicaV0314CloseoutTests(unittest.TestCase):
    def test_build_closeout_reflects_replay_decision(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest_summary = root / "manifest_summary.json"
            schema_summary = root / "schema_summary.json"
            trace_summary = root / "trace_summary.json"
            replay_summary = root / "replay_summary.json"
            manifest_summary.write_text(json.dumps({"status": "PASS", "runtime_eval_count": 8, "initialization_eval_count": 4, "trace_availability": {"status": "PASS"}}), encoding="utf-8")
            schema_summary.write_text(json.dumps({"status": "PASS", "compatible_result_count": 22}), encoding="utf-8")
            trace_summary.write_text(json.dumps({"status": "PASS", "step_record_count": 10, "failure_bank_step_count": 41}), encoding="utf-8")
            replay_summary.write_text(
                json.dumps(
                    {
                        "version_decision": "replay_operational_but_no_clear_gain",
                        "retrieval_summary": {"exact_match_ready_rate_pct": 100.0},
                        "injection_summary": {"runtime_replay_hit_rate_pct": 100.0, "initialization_replay_hit_rate_pct": 100.0},
                        "runtime": {"delta": {"success_rate_pct_delta": 0.0}},
                        "initialization": {"delta": {"success_rate_pct_delta": 0.0}},
                    }
                ),
                encoding="utf-8",
            )
            payload = build_v0_3_14_closeout(
                manifest_summary_path=str(manifest_summary),
                schema_summary_path=str(schema_summary),
                trace_summary_path=str(trace_summary),
                replay_evidence_path=str(replay_summary),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload.get("closeout_status"), "REPLAY_EVIDENCE_READY")
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "replay_operational_but_no_clear_gain")
            self.assertEqual((payload.get("conclusion") or {}).get("primary_bottleneck"), "eval_slice_saturation")


if __name__ == "__main__":
    unittest.main()
