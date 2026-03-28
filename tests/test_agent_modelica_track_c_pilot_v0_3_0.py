import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_track_c_pilot_v0_3_0 import build_track_c_pilot


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class AgentModelicaTrackCPilotV030Tests(unittest.TestCase):
    def test_build_track_c_pilot_writes_contract_and_mock_run(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            budget_results = root / "results.json"
            _write_json(
                budget_results,
                {
                    "records": [
                        {"task_id": "t1", "rounds_used": 2, "elapsed_sec": 33.0},
                        {"task_id": "t2", "rounds_used": 4, "elapsed_sec": 72.0},
                        {"task_id": "t3", "rounds_used": 3, "elapsed_sec": 65.0},
                    ]
                },
            )
            out_dir = root / "out"
            payload = build_track_c_pilot(out_dir=str(out_dir), budget_results_paths=[str(budget_results)])
            self.assertEqual(payload.get("status"), "PASS")
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("prompt_smoke_status"), "PASS")
            normalized = json.loads((out_dir / "mock_external_agent_run_normalized.json").read_text(encoding="utf-8"))
            self.assertEqual(int(normalized.get("record_count") or 0), 2)
            budget = json.loads((out_dir / "budget_calibration.json").read_text(encoding="utf-8"))
            self.assertGreaterEqual(int(budget["recommended_budget"]["max_agent_rounds"]), 3)


if __name__ == "__main__":
    unittest.main()
