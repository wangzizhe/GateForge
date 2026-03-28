import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_0_release_summary import build_v0_3_0_release_summary


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class AgentModelicaV030ReleaseSummaryTests(unittest.TestCase):
    def test_release_summary_passes_when_all_blocks_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            blocks = []
            for idx in range(3):
                summary_path = root / f"block_{idx}.json"
                _write_json(summary_path, {"status": "PASS"})
                blocks.append({"block_id": f"block_{idx}", "summary_path": str(summary_path)})
            payload = build_v0_3_0_release_summary(out_dir=str(root / "out"), blocks=blocks)
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(int(payload.get("block_count") or 0), 3)


if __name__ == "__main__":
    unittest.main()
