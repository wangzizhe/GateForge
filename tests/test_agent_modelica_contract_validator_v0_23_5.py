from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_contract_validator_v0_23_5 import (
    build_contract_validation_report,
    validate_seed_registry_row,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


class ContractValidatorV0235Tests(unittest.TestCase):
    def test_validate_seed_registry_row_rejects_routing(self) -> None:
        errors = validate_seed_registry_row(
            {
                "seed_id": "s1",
                "candidate_id": "s1",
                "source_model": "m",
                "mutation_family": "f",
                "omc_admission_status": "admitted",
                "live_screening_status": "screened",
                "repeatability_class": "stable_true_multi",
                "registry_policy": "benchmark_positive_candidate",
                "artifact_references": [],
                "routing_allowed": True,
            }
        )

        self.assertIn("routing_allowed_must_be_false", errors)

    def test_build_contract_validation_report_passes_clean_fixtures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "seed.jsonl"
            trajectories = root / "trajectories.jsonl"
            oracle = root / "oracle.jsonl"
            manifests = root / "manifests.jsonl"
            out_dir = root / "out"
            _write_jsonl(
                seed,
                [
                    {
                        "seed_id": "s1",
                        "candidate_id": "s1",
                        "source_model": "m",
                        "mutation_family": "f",
                        "omc_admission_status": "admitted",
                        "live_screening_status": "screened",
                        "repeatability_class": "stable_true_multi",
                        "registry_policy": "benchmark_positive_candidate",
                        "artifact_references": [],
                        "routing_allowed": False,
                    }
                ],
            )
            _write_jsonl(
                trajectories,
                [
                    {
                        "schema_version": "trajectory_schema_v1",
                        "run_id": "r",
                        "case_id": "s1",
                        "candidate_id": "s1",
                        "repair_round_count": 2,
                        "executor_attempt_count": 3,
                        "validation_round_count": 1,
                        "feedback_sequence": ["model_check_error", "none"],
                        "final_verdict": "PASS",
                        "trajectory_class": "multi_turn_useful",
                        "true_multi_turn": True,
                    }
                ],
            )
            _write_jsonl(
                oracle,
                [
                    {
                        "contract_version": "oracle_contract_v1",
                        "run_id": "r",
                        "case_id": "s1",
                        "oracle_type": "model_check",
                        "round_index": 1,
                        "status": "model_check_error",
                        "raw_feedback": "model_check_error",
                        "repair_hint_allowed": False,
                        "deterministic_repair_allowed": False,
                    }
                ],
            )
            _write_jsonl(
                manifests,
                [
                    {
                        "contract_version": "runner_artifact_contract_v1",
                        "run_version": "v0.test",
                        "artifact_dir": "artifacts/demo",
                        "producer_script": "scripts/demo.py",
                        "expected_files": ["summary.json"],
                        "present_files": ["summary.json"],
                        "missing_files": [],
                        "summary_status": "PASS",
                        "environment_metadata": {},
                        "provider_metadata": {},
                        "budget_metadata": {},
                    }
                ],
            )

            summary = build_contract_validation_report(
                input_paths={
                    "seed_registry": seed,
                    "trajectories": trajectories,
                    "oracle_events": oracle,
                    "artifact_manifests": manifests,
                },
                out_dir=out_dir,
            )

            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["total_validation_error_count"], 0)
            self.assertTrue((out_dir / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
