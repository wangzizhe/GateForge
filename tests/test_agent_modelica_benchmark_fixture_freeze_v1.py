from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_benchmark_fixture_freeze_v1 import freeze_hardpack_fixture


class TestAgentModelicaBenchmarkFixtureFreezeV1(unittest.TestCase):
    def test_freeze_copies_source_and_mutants_and_rewrites_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "artifacts" / "src" / "Model.mo"
            mutant = root / "artifacts" / "mutants" / "broken.mo"
            source.parent.mkdir(parents=True, exist_ok=True)
            mutant.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("model Model\nend Model;\n", encoding="utf-8")
            mutant.write_text("model Model\n  Real x;\nend Model;\n", encoding="utf-8")
            hardpack = root / "benchmarks" / "pack.json"
            hardpack.parent.mkdir(parents=True, exist_ok=True)
            hardpack.write_text(
                json.dumps(
                    {
                        "schema_version": "agent_modelica_hardpack_v1",
                        "cases": [
                            {
                                "mutation_id": "m1",
                                "expected_failure_type": "model_check_error",
                                "source_model_path": str(source),
                                "mutated_model_path": str(mutant),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            out_root = root / "assets_private" / "fixture"
            summary = freeze_hardpack_fixture(
                hardpack_path=str(hardpack),
                out_root=str(out_root),
            )

            self.assertEqual(summary["status"], "PASS")
            frozen = json.loads((out_root / "hardpack_frozen.json").read_text(encoding="utf-8"))
            case = frozen["cases"][0]
            self.assertTrue(Path(case["source_model_path"]).exists())
            self.assertTrue(Path(case["mutated_model_path"]).exists())
            self.assertTrue(str(case["source_model_path"]).startswith(str(out_root / "source_models")))
            self.assertTrue(str(case["mutated_model_path"]).startswith(str(out_root / "mutants")))

    def test_freeze_fails_when_hardpack_has_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hardpack = root / "benchmarks" / "pack.json"
            hardpack.parent.mkdir(parents=True, exist_ok=True)
            hardpack.write_text(
                json.dumps(
                    {
                        "schema_version": "agent_modelica_hardpack_v1",
                        "cases": [
                            {
                                "mutation_id": "m1",
                                "expected_failure_type": "semantic_regression",
                                "source_model_path": str(root / "missing_source.mo"),
                                "mutated_model_path": str(root / "missing_mutant.mo"),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            out_root = root / "assets_private" / "fixture"
            summary = freeze_hardpack_fixture(
                hardpack_path=str(hardpack),
                out_root=str(out_root),
            )

            self.assertEqual(summary["status"], "FAIL")
            manifest = json.loads((out_root / "freeze_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["missing_files"]), 1)
            self.assertEqual(manifest["missing_files"][0]["kind"], "mutated_model_path")

    def test_valid_only_mode_skips_missing_cases_and_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "artifacts" / "src" / "Model.mo"
            mutant = root / "artifacts" / "mutants" / "broken.mo"
            source.parent.mkdir(parents=True, exist_ok=True)
            mutant.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("model Model\nend Model;\n", encoding="utf-8")
            mutant.write_text("model Model\n  Real x;\nend Model;\n", encoding="utf-8")
            hardpack = root / "benchmarks" / "pack.json"
            hardpack.parent.mkdir(parents=True, exist_ok=True)
            hardpack.write_text(
                json.dumps(
                    {
                        "schema_version": "agent_modelica_hardpack_v1",
                        "hardpack_version": "agent_modelica_hardpack_v1",
                        "cases": [
                            {
                                "mutation_id": "ok_case",
                                "expected_failure_type": "model_check_error",
                                "source_model_path": str(source),
                                "mutated_model_path": str(mutant),
                            },
                            {
                                "mutation_id": "missing_case",
                                "expected_failure_type": "semantic_regression",
                                "source_model_path": str(source),
                                "mutated_model_path": str(root / "missing.mo"),
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            out_root = root / "assets_private" / "fixture_valid"
            summary = freeze_hardpack_fixture(
                hardpack_path=str(hardpack),
                out_root=str(out_root),
                valid_only=True,
            )

            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["copied_cases"], 1)
            frozen = json.loads((out_root / "hardpack_frozen.json").read_text(encoding="utf-8"))
            self.assertEqual(frozen["fixture_mode"], "valid_only")
            self.assertEqual(frozen["excluded_missing_cases"], ["missing_case"])
            self.assertEqual(len(frozen["cases"]), 1)


if __name__ == "__main__":
    unittest.main()
