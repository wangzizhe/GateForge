from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_cross_domain_validation_spec_builder_v1 import build_spec


class AgentModelicaCrossDomainValidationSpecBuilderV1Tests(unittest.TestCase):
    def test_build_spec_uses_matrix_summaries_and_expectations(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            matrix = root / "matrix.json"
            track_manifest = root / "tracks.json"
            expectations = root / "expectations.json"
            matrix.write_text(
                json.dumps(
                    {
                        "track_id": "buildings_v1",
                        "library": "Buildings",
                        "layer_sidecar": "layer_metadata.json",
                        "layer_sidecar_summary_path": "layer_summary.json",
                        "configs": [
                            {
                                "config_label": "baseline",
                                "comparison_summary": "cmp.json",
                                "gateforge_results": "gf.json",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            track_manifest.write_text(json.dumps({"tracks": [{"track_id": "buildings_v1", "library": "Buildings"}]}), encoding="utf-8")
            expectations.write_text(json.dumps({"experiment_expectations": {"replay_signal_expectation": "x"}}), encoding="utf-8")
            spec = build_spec(
                matrix_summary_paths=[str(matrix)],
                track_manifest_path=str(track_manifest),
                expectation_template_path=str(expectations),
            )
            self.assertEqual(spec["experiment_expectations"]["replay_signal_expectation"], "x")
            self.assertEqual(spec["tracks"][0]["configs"]["baseline"]["comparison_summary"], "cmp.json")
            self.assertEqual(spec["tracks"][0]["layer_sidecar"], "layer_metadata.json")

    def test_cli_writes_spec(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            matrix = root / "matrix.json"
            track_manifest = root / "tracks.json"
            expectations = root / "expectations.json"
            out = root / "spec.json"
            matrix.write_text(
                json.dumps(
                    {
                        "track_id": "openipsl_v1",
                        "library": "OpenIPSL",
                        "configs": [
                            {
                                "config_label": "planner_only",
                                "comparison_summary": "cmp.json",
                                "gateforge_results": "gf.json",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            track_manifest.write_text(json.dumps({"tracks": [{"track_id": "openipsl_v1", "library": "OpenIPSL"}]}), encoding="utf-8")
            expectations.write_text(json.dumps({"experiment_expectations": {"planner_injection_expectation": "y"}}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_cross_domain_validation_spec_builder_v1",
                    "--matrix-summary",
                    str(matrix),
                    "--track-manifest",
                    str(track_manifest),
                    "--expectation-template",
                    str(expectations),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["tracks"][0]["track_id"], "openipsl_v1")


if __name__ == "__main__":
    unittest.main()
