import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_multi_round_failure_manifest_v1 import (
    load_multi_round_failure_manifest,
    validate_multi_round_failure_manifest,
)


class AgentModelicaMultiRoundFailureManifestV1Tests(unittest.TestCase):
    def test_manifest_validates_minimum_shape(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            model = root / "A.mo"
            model.write_text("model A\nend A;\n", encoding="utf-8")
            payload = {
                "schema_version": "agent_modelica_multi_round_failure_pack_manifest_v1",
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
                        "exposure_notes": "x",
                        "allowed_models": [
                            {
                                "model_id": f"m{i}",
                                "qualified_model_name": f"LibA.M{i}",
                                "model_path": str(model),
                                "seen_risk_band": "less_likely_seen",
                                "source_type": "public_repo",
                                "selection_reason": "x",
                                "exposure_notes": "x",
                            }
                            for i in range(3)
                        ],
                    },
                    {
                        "library_id": "libb",
                        "package_name": "LibB",
                        "source_library": "LibB",
                        "license_provenance": "MIT",
                        "domain": "controls",
                        "seen_risk_band": "hard_unseen",
                        "source_type": "internal_mirror",
                        "selection_reason": "y",
                        "exposure_notes": "y",
                        "allowed_models": [
                            {
                                "model_id": f"n{i}",
                                "qualified_model_name": f"LibB.N{i}",
                                "model_path": str(model),
                                "seen_risk_band": "hard_unseen",
                                "source_type": "internal_mirror",
                                "selection_reason": "y",
                                "exposure_notes": "y",
                            }
                            for i in range(3)
                        ],
                    },
                ],
            }
            path = root / "manifest.json"
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            loaded = load_multi_round_failure_manifest(str(path))
            libs, reasons = validate_multi_round_failure_manifest(loaded)
            self.assertEqual(len(libs), 2)
            self.assertNotIn("library_count_below_minimum", reasons)
            self.assertNotIn("model_count_below_minimum", reasons)


if __name__ == "__main__":
    unittest.main()
