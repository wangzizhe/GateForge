from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_14_authority_manifest import build_authority_manifest


class AgentModelicaV0314AuthorityManifestTests(unittest.TestCase):
    def test_build_authority_manifest_matches_fixed_split(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            payload = build_authority_manifest(out_dir=d)
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(((payload.get("runtime") or {}).get("experience_source_count")), 3)
            self.assertEqual(((payload.get("runtime") or {}).get("eval_count")), 8)
            self.assertEqual(((payload.get("initialization") or {}).get("experience_source_count")), 2)
            self.assertEqual(((payload.get("initialization") or {}).get("eval_count")), 4)
            self.assertEqual((((payload.get("trace_availability") or {}).get("status"))), "PASS")
            manifest_path = Path(d) / "manifest.json"
            self.assertTrue(manifest_path.exists())
            summary = json.loads((Path(d) / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("failure_bank_count"), 5)


if __name__ == "__main__":
    unittest.main()
