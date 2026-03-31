from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_track_c_paper_matrix_v0_3_3 import summarize_paper_matrix


def _bundle(
    provider_name: str,
    *,
    success: bool,
    infra_failure_reason: str = "",
    tool_calls: int = 2,
    wall_clock_sec: float = 20.0,
) -> dict:
    return {
        "provider_name": provider_name,
        "arm_id": "arm",
        "model_id": f"{provider_name}-model",
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
        "summary": {
            "success_rate_pct": 100.0 if success else 0.0,
            "avg_wall_clock_sec": wall_clock_sec,
            "avg_omc_tool_call_count": float(tool_calls),
        },
    }


class AgentModelicaTrackCPaperMatrixV033Tests(unittest.TestCase):
    def test_summarize_paper_matrix_builds_provider_rows(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v033_matrix_") as td:
            root = Path(td)
            paths = []
            for name, payload in (
                ("gateforge_run1.json", _bundle("gateforge", success=True, tool_calls=1, wall_clock_sec=10.0)),
                ("claude_run1.json", _bundle("claude", success=True, tool_calls=2, wall_clock_sec=20.0)),
                ("claude_run2.json", _bundle("claude", success=False, infra_failure_reason="provider_auth_unavailable", tool_calls=0, wall_clock_sec=1.0)),
            ):
                path = root / name
                path.write_text(json.dumps(payload), encoding="utf-8")
                paths.append(str(path))
            payload = summarize_paper_matrix(bundle_paths=paths, out_dir=str(root / "out"))
            rows = {row["provider_name"]: row for row in payload["provider_rows"]}
            self.assertEqual(rows["gateforge"]["clean_run_count"], 1)
            self.assertEqual(rows["claude"]["clean_run_count"], 1)
            self.assertEqual(rows["claude"]["auth_session_failure_rate_pct"], 50.0)
            self.assertFalse(rows["claude"]["main_table_eligible"])


if __name__ == "__main__":
    unittest.main()
