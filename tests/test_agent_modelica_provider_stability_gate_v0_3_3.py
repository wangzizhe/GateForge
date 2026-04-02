from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_provider_stability_gate_v0_3_3 import summarize_provider_stability


def _bundle(*, success: bool, infra_failure_reason: str = "", tool_calls: int = 1, wall_clock_sec: float = 10.0) -> dict:
    return {
        "provider_name": "claude",
        "records": [
            {
                "task_id": "task_a",
                "success": success,
                "infra_failure": bool(infra_failure_reason),
                "infra_failure_reason": infra_failure_reason,
                "omc_tool_call_count": tool_calls,
                "wall_clock_sec": wall_clock_sec,
                "output_text": "Not logged in · Please run /login" if infra_failure_reason else "ok",
            }
        ],
        "summary": {"success_rate_pct": 100.0 if success else 0.0},
    }


class AgentModelicaProviderStabilityGateV033Tests(unittest.TestCase):
    def test_marks_stable_when_three_clean_runs_exist(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v033_claude_stable_") as td:
            root = Path(td)
            paths = []
            for idx in range(1, 4):
                path = root / f"claude_run{idx}.json"
                path.write_text(json.dumps(_bundle(success=True)), encoding="utf-8")
                paths.append(str(path))
            payload = summarize_provider_stability(bundle_paths=paths, out_dir=str(root / "out"))
            self.assertEqual(payload["classification"], "STABLE")
            self.assertEqual(payload["metrics"]["clean_run_count"], 3)
            self.assertFalse(payload["switch_required"])

    def test_requires_api_direct_after_three_consecutive_auth_failures(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v033_claude_fallback_") as td:
            root = Path(td)
            paths = []
            for idx in range(1, 4):
                path = root / f"claude_run{idx}.json"
                path.write_text(json.dumps(_bundle(success=False, infra_failure_reason="provider_auth_unavailable", tool_calls=0)), encoding="utf-8")
                paths.append(str(path))
            payload = summarize_provider_stability(bundle_paths=paths, out_dir=str(root / "out"))
            self.assertEqual(payload["classification"], "API_DIRECT_SWITCH_REQUIRED")
            self.assertTrue(payload["conditions"]["consecutive_failure_limit_hit"])
            self.assertTrue(payload["switch_required"])


if __name__ == "__main__":
    unittest.main()
