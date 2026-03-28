import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_0_seal_v1 import build_v0_3_0_seal


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class AgentModelicaV030SealV1Tests(unittest.TestCase):
    def test_build_v0_3_0_seal_passes_when_references_exist(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            summary = root / "summary.json"
            taskset = root / "taskset.json"
            contract = root / "contract.json"
            budget = root / "budget.json"
            _write_json(summary, {"status": "PASS"})
            _write_json(taskset, {"tasks": [{"task_id": "a"}]})
            _write_json(contract, {"tool_count": 4})
            _write_json(budget, {"recommended_budget": {"max_agent_rounds": 3}, "sources_used": ["x"]})
            payload = build_v0_3_0_seal(
                out_dir=str(root / "out"),
                references=[
                    {"artifact_id": "summary", "path": str(summary), "kind": "summary"},
                    {"artifact_id": "taskset", "path": str(taskset), "kind": "taskset"},
                    {"artifact_id": "contract", "path": str(contract), "kind": "contract"},
                    {"artifact_id": "budget", "path": str(budget), "kind": "budget"},
                ],
            )
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(int(payload.get("reference_count") or 0), 4)


if __name__ == "__main__":
    unittest.main()
