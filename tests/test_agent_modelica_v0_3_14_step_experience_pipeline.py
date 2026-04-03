from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_14_authority_manifest import build_authority_manifest
from gateforge.agent_modelica_v0_3_14_authority_trace_extraction import build_authority_trace_extraction
from gateforge.agent_modelica_v0_3_14_step_experience_schema import build_schema_summary


class AgentModelicaV0314StepExperiencePipelineTests(unittest.TestCase):
    def test_schema_and_extraction_build_non_empty_authority_store(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest_dir = root / "manifest"
            schema_dir = root / "schema"
            extraction_dir = root / "extraction"
            build_authority_manifest(out_dir=str(manifest_dir))
            manifest_path = manifest_dir / "manifest.json"
            schema = build_schema_summary(manifest_path=str(manifest_path), out_dir=str(schema_dir))
            self.assertEqual(schema.get("status"), "PASS")
            self.assertEqual(schema.get("compatible_result_count"), 22)
            payload = build_authority_trace_extraction(manifest_path=str(manifest_path), out_dir=str(extraction_dir))
            summary = payload.get("summary") or {}
            self.assertEqual(summary.get("status"), "PASS")
            self.assertGreaterEqual(int(summary.get("step_record_count") or 0), 10)
            self.assertGreaterEqual(int(summary.get("failure_bank_step_count") or 0), 40)
            store = json.loads((extraction_dir / "experience_store.json").read_text(encoding="utf-8"))
            first = (store.get("step_records") or [])[0]
            self.assertIn("dominant_stage_subtype", first)
            self.assertIn("residual_signal_cluster", first)
            self.assertIn("action_type", first)
            self.assertIn("step_outcome", first)


if __name__ == "__main__":
    unittest.main()
