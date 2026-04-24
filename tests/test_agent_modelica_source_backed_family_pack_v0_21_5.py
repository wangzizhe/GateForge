from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_source_backed_family_pack_v0_21_5 import (
    build_source_backed_candidates,
    build_source_inventory,
    mutate_source_for_bucket,
    run_source_backed_family_pack,
    summarize_source_backed_pack,
)


def _family_candidate(bucket_id: str = "ET01") -> dict:
    return {
        "family_candidate_id": f"fam_{bucket_id}",
        "bucket_id": bucket_id,
        "family_id": "family",
        "source_task_id": "task",
    }


def _source_row(path: Path) -> dict:
    return {
        "source_model_path": str(path),
        "source_model_name": "A",
        "source_viability_status": "historically_verified_clean_source",
        "source_evidence_artifact": "cases.jsonl",
        "source_evidence_case_id": "case_a",
    }


class SourceBackedFamilyPackV0215Tests(unittest.TestCase):
    def test_mutate_source_for_bucket_builds_parse_failure_candidate(self) -> None:
        self.assertTrue(mutate_source_for_bucket("model A\nend A;", "ET01").startswith("{\nmodel A"))

    def test_mutate_source_for_bucket_builds_missing_reference_candidate(self) -> None:
        text = "model A\n  Modelica.Electrical.Analog.Basic.Resistor R1;\nequation\nend A;"

        mutated = mutate_source_for_bucket(text, "ET02")

        self.assertIn("DoesNotExistResistor", mutated)

    def test_mutate_source_for_bucket_builds_undeclared_identifier_candidate(self) -> None:
        mutated = mutate_source_for_bucket("model A\nequation\nend A;", "ET03")

        self.assertIn("missingIdentifier = time;", mutated)

    def test_build_source_inventory_reads_historically_verified_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "A.mo"
            cases = root / "admitted_cases.jsonl"
            source.write_text("model A\nend A;", encoding="utf-8")
            cases.write_text(
                json.dumps(
                    {
                        "candidate_id": "case_a",
                        "source_model_path": str(source),
                        "source_check_pass": True,
                    }
                ),
                encoding="utf-8",
            )

            inventory = build_source_inventory([cases])

        self.assertEqual(len(inventory), 1)
        self.assertEqual(inventory[0]["source_model_name"], "A")

    def test_build_source_backed_candidates_covers_family_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "A.mo"
            source.write_text("model A\nequation\nend A;", encoding="utf-8")
            rows = build_source_backed_candidates(
                family_candidates=[_family_candidate("ET01"), _family_candidate("ET02")],
                source_inventory=[_source_row(source)],
            )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["benchmark_admission_status"], "isolated_source_backed_candidate_only")

    def test_summarize_source_backed_pack_requires_all_target_buckets(self) -> None:
        summary = summarize_source_backed_pack(
            [
                {"bucket_id": "ET01"},
                {"bucket_id": "ET02"},
                {"bucket_id": "ET03"},
            ],
            [{"source_model_path": "A.mo"}],
        )

        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["next_action"], "run_omc_target_failure_admission")

    def test_run_source_backed_family_pack_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "A.mo"
            cases = root / "admitted_cases.jsonl"
            family_path = root / "family.jsonl"
            out_dir = root / "out"
            source.write_text("model A\n  Modelica.Electrical.Analog.Basic.Resistor R1;\nequation\nend A;", encoding="utf-8")
            cases.write_text(
                json.dumps(
                    {
                        "candidate_id": "case_a",
                        "source_model_path": str(source),
                        "source_check_pass": True,
                    }
                ),
                encoding="utf-8",
            )
            family_path.write_text(
                "\n".join(
                    [
                        json.dumps(_family_candidate("ET01")),
                        json.dumps(_family_candidate("ET02")),
                        json.dumps(_family_candidate("ET03")),
                    ]
                ),
                encoding="utf-8",
            )

            summary = run_source_backed_family_pack(
                family_candidate_path=family_path,
                out_dir=out_dir,
                source_inventory_paths=[cases],
            )

            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "source_backed_candidates.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
