import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_unknown_library_manifest_v1 import (
    SCHEMA_VERSION,
    load_unknown_library_manifest,
    validate_unknown_library_manifest,
)


def _write_model(path: Path, model_name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                f"model {model_name}",
                "  Modelica.Blocks.Sources.Constant src(k=1);",
                "  Modelica.Blocks.Math.Gain gain(k=2);",
                "equation",
                "  connect(src.y, gain.u);",
                f"end {model_name};",
                "",
            ]
        ),
        encoding="utf-8",
    )


class AgentModelicaUnknownLibraryManifestV1Tests(unittest.TestCase):
    def test_validate_manifest_accepts_curated_pool(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            model_a = root / "LibA" / "ModelA.mo"
            model_b = root / "LibA" / "ModelB.mo"
            model_c = root / "LibB" / "ModelC.mo"
            model_d = root / "LibB" / "ModelD.mo"
            _write_model(model_a, "ModelA")
            _write_model(model_b, "ModelB")
            _write_model(model_c, "ModelC")
            _write_model(model_d, "ModelD")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "libraries": [
                            {
                                "library_id": "liba",
                                "package_name": "LibA",
                                "source_library": "LibA",
                                "license_provenance": "MIT",
                                "local_path": str(model_a.parent),
                                "accepted_source_path": str(model_a.parent),
                                "domain": "controls",
                                "allowed_models": [
                                    {"model_id": "ma", "qualified_model_name": "LibA.ModelA", "model_path": str(model_a)},
                                    {"model_id": "mb", "qualified_model_name": "LibA.ModelB", "model_path": str(model_b)},
                                ],
                            },
                            {
                                "library_id": "libb",
                                "package_name": "LibB",
                                "source_library": "LibB",
                                "license_provenance": "MIT",
                                "local_path": str(model_c.parent),
                                "accepted_source_path": str(model_c.parent),
                                "domain": "signals",
                                "allowed_models": [
                                    {"model_id": "mc", "qualified_model_name": "LibB.ModelC", "model_path": str(model_c)},
                                    {"model_id": "md", "qualified_model_name": "LibB.ModelD", "model_path": str(model_d)},
                                ],
                            },
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            payload = load_unknown_library_manifest(str(manifest))
            libraries, reasons = validate_unknown_library_manifest(payload)
            self.assertEqual(reasons, [])
            self.assertEqual(len(libraries), 2)
            self.assertIn("liba", libraries[0].get("library_hints", []))

    def test_validate_manifest_rejects_missing_fields(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "libraries": [
                            {
                                "library_id": "liba",
                                "package_name": "LibA",
                                "source_library": "LibA",
                                "allowed_models": [{"model_id": "ma", "qualified_model_name": "LibA.ModelA", "model_path": "missing.mo"}],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            libraries, reasons = validate_unknown_library_manifest(load_unknown_library_manifest(str(manifest)))
            self.assertEqual(libraries[0].get("library_id"), "liba")
            self.assertIn("library_missing_field:liba:license_provenance", reasons)
            self.assertTrue(any(reason.startswith("library_missing_field:liba:local_path_or_accepted_source_path") for reason in reasons))


if __name__ == "__main__":
    unittest.main()

