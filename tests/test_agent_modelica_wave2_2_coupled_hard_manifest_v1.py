import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_wave2_2_coupled_hard_manifest_v1 import (
    load_wave2_2_coupled_hard_manifest,
    validate_wave2_2_coupled_hard_manifest,
)


class AgentModelicaWave22CoupledHardManifestV1Tests(unittest.TestCase):
    def test_manifest_requires_core_fields(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            model_path = Path(d) / "Lib" / "A.mo"
            model_path.parent.mkdir(parents=True, exist_ok=True)
            model_path.write_text("model A\nend A;\n", encoding="utf-8")
            manifest = Path(d) / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "agent_modelica_wave2_2_coupled_hard_pack_manifest_v1",
                        "libraries": [
                            {
                                "library_id": "liba",
                                "package_name": "LibA",
                                "source_library": "LibA",
                                "license_provenance": "MIT",
                                "domain": "controls",
                                "seen_risk_band": "less_likely_seen",
                                "source_type": "public_repo",
                                "selection_reason": "x",
                                "exposure_notes": "y",
                                "allowed_models": [
                                    {
                                        "model_id": "a",
                                        "qualified_model_name": "LibA.A",
                                        "model_path": str(model_path),
                                        "seen_risk_band": "less_likely_seen",
                                        "source_type": "public_repo",
                                        "selection_reason": "a",
                                        "exposure_notes": "a",
                                    }
                                ],
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            payload = load_wave2_2_coupled_hard_manifest(str(manifest))
            libraries, reasons = validate_wave2_2_coupled_hard_manifest(payload)
            self.assertEqual(len(libraries), 1)
            self.assertIn("library_count_below_minimum", reasons)
            self.assertIn("model_count_below_minimum", reasons)


if __name__ == "__main__":
    unittest.main()
