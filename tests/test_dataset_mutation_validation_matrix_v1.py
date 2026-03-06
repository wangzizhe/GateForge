import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from gateforge import dataset_mutation_validation_matrix_v1 as mtx_v1


class DatasetMutationValidationMatrixV1Tests(unittest.TestCase):
    def test_resolve_model_name_uses_within_namespace(self) -> None:
        text = "within A.B;\nmodel C\n  Real x;\nequation\n  der(x)=-x;\nend C;\n"
        self.assertEqual(mtx_v1._resolve_model_name(text), "A.B.C")

    def test_resolve_model_name_without_within(self) -> None:
        text = "model D\n  Real x;\nequation\n  der(x)=-x;\nend D;\n"
        self.assertEqual(mtx_v1._resolve_model_name(text), "D")

    def test_collect_package_preload_files(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            model_path = root / "AixLib" / "Airflow" / "Multizone" / "Examples" / "ZonalFlow.mo"
            model_path.parent.mkdir(parents=True, exist_ok=True)
            (root / "AixLib" / "package.mo").write_text("package AixLib\nend AixLib;\n", encoding="utf-8")
            (root / "AixLib" / "Airflow" / "package.mo").write_text("within AixLib;\npackage Airflow\nend Airflow;\n", encoding="utf-8")
            (root / "AixLib" / "Airflow" / "Multizone" / "package.mo").write_text(
                "within AixLib.Airflow;\npackage Multizone\nend Multizone;\n", encoding="utf-8"
            )
            model_path.write_text(
                "within AixLib.Airflow.Multizone.Examples;\nmodel ZonalFlow\n  Real x;\nequation\n  der(x)=-x;\nend ZonalFlow;\n",
                encoding="utf-8",
            )
            files = mtx_v1._collect_package_preload_files(model_path, "AixLib.Airflow.Multizone.Examples.ZonalFlow")
            rendered = [str(x) for x in files]
            self.assertIn(str((root / "AixLib" / "package.mo").resolve()), rendered)
            self.assertEqual(len(rendered), 1)

    def test_classify_failure_maps_assert_in_check_log_to_constraint_violation(self) -> None:
        stage, ftype = mtx_v1._classify_failure(
            check_ok=False,
            simulate_ok=False,
            check_log="Error: assert(false, \"x\") triggered",
            simulate_log="",
        )
        self.assertEqual(stage, "check")
        self.assertEqual(ftype, "constraint_violation")

    def test_resolve_backend_prefers_docker_when_omc_missing(self) -> None:
        with mock.patch.object(mtx_v1.shutil, "which", side_effect=lambda name: None if name == "omc" else "/usr/bin/docker"):
            backend, fallback = mtx_v1._resolve_backend("omc")
        self.assertEqual(backend, "openmodelica_docker")
        self.assertFalse(fallback)

    def test_resolve_backend_auto_uses_syntax_when_no_omc_or_docker(self) -> None:
        with mock.patch.object(mtx_v1.shutil, "which", return_value=None):
            backend, fallback = mtx_v1._resolve_backend("auto")
        self.assertEqual(backend, "syntax")
        self.assertTrue(fallback)

    def test_validation_matrix_pass_for_check_stage_match(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source_model = root / "Source.mo"
            source_model.write_text(
                "model Source\n  Real x;\nequation\n  der(x) = -x;\nend Source;\n",
                encoding="utf-8",
            )

            mutant = root / "mutant_bad.mo"
            mutant.write_text(
                "model MutantBad\n  Real x;\nequation\n  der(x) = -x;\n",
                encoding="utf-8",
            )

            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "mutation_manifest_v2_materialized",
                        "mutations": [
                            {
                                "mutation_id": "m1",
                                "expected_failure_type": "model_check_error",
                                "expected_stage": "check",
                                "source_model_path": str(source_model),
                                "mutated_model_path": str(mutant),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            records = root / "records.json"
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_validation_matrix_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--backend",
                    "syntax",
                    "--min-stage-match-rate-pct",
                    "100",
                    "--min-type-match-rate-pct",
                    "100",
                    "--records-out",
                    str(records),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(summary.get("validation_backend_used"), "syntax")
            self.assertEqual(float(summary.get("baseline_check_pass_rate_pct", 0.0)), 100.0)
            self.assertEqual(float(summary.get("stage_match_rate_pct", 0.0)), 100.0)
            self.assertEqual(float(summary.get("type_match_rate_pct", 0.0)), 100.0)

    def test_validation_matrix_fail_when_manifest_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_validation_matrix_v1",
                    "--mutation-manifest",
                    str(root / "missing_manifest.json"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "FAIL")
            self.assertIn("mutation_manifest_missing", summary.get("reasons") or [])

    def test_validation_matrix_marks_semantic_regression_when_check_and_simulate_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source_model = root / "Source.mo"
            source_model.write_text(
                "model Source\n  Real x;\nequation\n  der(x) = -x;\nend Source;\n",
                encoding="utf-8",
            )
            mutant = root / "mutant_semantic.mo"
            mutant.write_text(
                "model MutantSemantic\n  Real x;\nequation\n  der(x) = -x;\nend MutantSemantic;\n",
                encoding="utf-8",
            )
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "mutation_manifest_v2_materialized",
                        "mutations": [
                            {
                                "mutation_id": "m1",
                                "expected_failure_type": "semantic_regression",
                                "expected_stage": "simulate",
                                "source_model_path": str(source_model),
                                "mutated_model_path": str(mutant),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            records = root / "records.json"
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_validation_matrix_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--backend",
                    "syntax",
                    "--min-stage-match-rate-pct",
                    "100",
                    "--min-type-match-rate-pct",
                    "100",
                    "--records-out",
                    str(records),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(float(summary.get("stage_match_rate_pct", 0.0)), 100.0)
            self.assertEqual(float(summary.get("type_match_rate_pct", 0.0)), 100.0)
            records_payload = json.loads(records.read_text(encoding="utf-8"))
            rows = records_payload.get("mutation_records") if isinstance(records_payload.get("mutation_records"), list) else []
            self.assertEqual(len(rows), 1)
            self.assertEqual(str(rows[0].get("observed_failure_type") or ""), "semantic_regression")
            self.assertEqual(str(rows[0].get("observed_stage") or ""), "simulate")


if __name__ == "__main__":
    unittest.main()
