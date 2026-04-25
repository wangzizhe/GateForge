from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_oracle_contract_v0_23_3 import (
    build_oracle_contract_index,
    map_feedback_to_oracle_status,
    normalize_oracle_events,
    validate_oracle_event,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


class OracleContractV0233Tests(unittest.TestCase):
    def test_map_feedback_to_oracle_status_normalizes_legacy_values(self) -> None:
        self.assertEqual(map_feedback_to_oracle_status("none"), "model_check_pass")
        self.assertEqual(map_feedback_to_oracle_status("model_check_error"), "model_check_error")
        self.assertEqual(map_feedback_to_oracle_status("simulate_error"), "simulation_error")

    def test_normalize_oracle_events_disallows_repair_hints(self) -> None:
        events = normalize_oracle_events(
            {
                "run_id": "run1",
                "case_id": "case1",
                "candidate_id": "case1",
                "feedback_sequence": ["model_check_error", "none"],
                "trajectory_class": "multi_turn_useful",
            }
        )

        self.assertEqual(len(events), 2)
        self.assertFalse(events[0]["repair_hint_allowed"])
        self.assertFalse(events[0]["deterministic_repair_allowed"])
        self.assertEqual(validate_oracle_event(events[0]), [])

    def test_build_oracle_contract_index_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trajectory_path = root / "trajectories.jsonl"
            out_dir = root / "out"
            _write_jsonl(
                trajectory_path,
                [
                    {
                        "run_id": "run1",
                        "case_id": "case1",
                        "candidate_id": "case1",
                        "feedback_sequence": ["model_check_error", "none"],
                        "trajectory_class": "multi_turn_useful",
                    }
                ],
            )

            summary = build_oracle_contract_index(trajectory_path=trajectory_path, out_dir=out_dir)

            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["oracle_event_count"], 2)
            self.assertEqual(summary["oracle_status_counts"]["model_check_pass"], 1)
            self.assertTrue((out_dir / "contract.json").exists())
            self.assertTrue((out_dir / "oracle_events.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
