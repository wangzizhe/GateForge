import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_wave2_1_harder_dynamics_manifest_v1 import (
    load_wave2_1_harder_dynamics_manifest,
    validate_wave2_1_harder_dynamics_manifest,
)


class AgentModelicaWave21HarderDynamicsManifestV1Tests(unittest.TestCase):
    def test_validate_manifest_accepts_minimum_valid_payload(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for lib in ("A", "B", "C"):
                for name in ("One", "Two"):
                    path = root / lib / f"{name}.mo"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(f"model {name}\nend {name};\n", encoding="utf-8")
            payload = {
                "schema_version": "agent_modelica_wave2_1_harder_dynamics_pack_manifest_v1",
                "libraries": [
                    {
                        "library_id": "a",
                        "package_name": "A",
                        "source_library": "A",
                        "license_provenance": "MIT",
                        "domain": "controls",
                        "seen_risk_band": "less_likely_seen",
                        "source_type": "public_repo",
                        "selection_reason": "x",
                        "exposure_notes": "x",
                        "allowed_models": [
                            {"model_id": "one", "qualified_model_name": "A.One", "model_path": str(root / "A/One.mo"), "seen_risk_band": "less_likely_seen", "source_type": "public_repo", "selection_reason": "x", "exposure_notes": "x"},
                            {"model_id": "two", "qualified_model_name": "A.Two", "model_path": str(root / "A/Two.mo"), "seen_risk_band": "less_likely_seen", "source_type": "public_repo", "selection_reason": "x", "exposure_notes": "x"},
                        ],
                    },
                    {
                        "library_id": "b",
                        "package_name": "B",
                        "source_library": "B",
                        "license_provenance": "MIT",
                        "domain": "controls",
                        "seen_risk_band": "hard_unseen",
                        "source_type": "internal_mirror",
                        "selection_reason": "y",
                        "exposure_notes": "y",
                        "allowed_models": [
                            {"model_id": "one", "qualified_model_name": "B.One", "model_path": str(root / "B/One.mo"), "seen_risk_band": "hard_unseen", "source_type": "internal_mirror", "selection_reason": "y", "exposure_notes": "y"},
                            {"model_id": "two", "qualified_model_name": "B.Two", "model_path": str(root / "B/Two.mo"), "seen_risk_band": "hard_unseen", "source_type": "internal_mirror", "selection_reason": "y", "exposure_notes": "y"},
                        ],
                    },
                    {
                        "library_id": "c",
                        "package_name": "C",
                        "source_library": "C",
                        "license_provenance": "MIT",
                        "domain": "controls",
                        "seen_risk_band": "less_likely_seen",
                        "source_type": "research_artifact",
                        "selection_reason": "z",
                        "exposure_notes": "z",
                        "allowed_models": [
                            {"model_id": "one", "qualified_model_name": "C.One", "model_path": str(root / "C/One.mo"), "seen_risk_band": "less_likely_seen", "source_type": "research_artifact", "selection_reason": "z", "exposure_notes": "z"},
                            {"model_id": "two", "qualified_model_name": "C.Two", "model_path": str(root / "C/Two.mo"), "seen_risk_band": "less_likely_seen", "source_type": "research_artifact", "selection_reason": "z", "exposure_notes": "z"},
                        ],
                    },
                ],
            }
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            loaded = load_wave2_1_harder_dynamics_manifest(str(manifest))
            libraries, reasons = validate_wave2_1_harder_dynamics_manifest(loaded)
            self.assertEqual(len(libraries), 3)
            self.assertEqual(reasons, [])


if __name__ == "__main__":
    unittest.main()
