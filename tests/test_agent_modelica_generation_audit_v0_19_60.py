from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_generation_audit_v0_19_60 import (
    build_gap_list,
    classify_generation_failure,
    distribution_from_buckets,
    extract_model_name,
    extract_modelica_model_text,
    load_mutation_distribution,
    parse_mapping_statuses,
    run_generation_audit,
    total_variation_distance,
)


class GenerationAuditV01960Tests(unittest.TestCase):
    def test_extract_modelica_model_text_from_json_payload(self) -> None:
        response = json.dumps(
            {
                "model_text": (
                    "model Demo\n"
                    "  Real x;\n"
                    "equation\n"
                    "  der(x) = -x;\n"
                    "end Demo;"
                )
            }
        )

        model_text = extract_modelica_model_text(response)

        self.assertIn("model Demo", model_text)
        self.assertEqual(extract_model_name(model_text), "Demo")

    def test_extract_modelica_model_text_from_code_fence(self) -> None:
        response = "```modelica\nmodel Demo2\n Real x;\nequation\n x = 1;\nend Demo2;\n```"

        model_text = extract_modelica_model_text(response)

        self.assertEqual(extract_model_name(model_text), "Demo2")

    def test_classify_generation_failure_prefers_pass_when_simulate_passes(self) -> None:
        result = classify_generation_failure(
            model_text="model Ok end Ok;",
            model_name="Ok",
            check_pass=True,
            simulate_pass=True,
            omc_output="",
        )

        self.assertEqual(result["bucket_id"], "PASS")

    def test_classify_generation_failure_from_omc_output(self) -> None:
        result = classify_generation_failure(
            model_text="model Bad Real x; equation x = y; end Bad;",
            model_name="Bad",
            check_pass=False,
            simulate_pass=False,
            omc_output="Error: Variable y not found in scope Bad.",
        )

        self.assertEqual(result["bucket_id"], "ET03")

    def test_classify_generation_failure_from_equation_variable_count(self) -> None:
        result = classify_generation_failure(
            model_text="model Bad Real x; equation x = 1; x = 2; end Bad;",
            model_name="Bad",
            check_pass=False,
            simulate_pass=False,
            omc_output="Check of Bad completed successfully. Class Bad has 3 equation(s) and 2 variable(s).",
        )

        self.assertEqual(result["bucket_id"], "ET07")

    def test_classify_generation_failure_parse_error_before_class_lookup(self) -> None:
        result = classify_generation_failure(
            model_text="model Bad Real x equation x = 1; end Bad;",
            model_name="Bad",
            check_pass=False,
            simulate_pass=False,
            omc_output="Missing token: ')' Error: Class Bad not found in scope <TOP>.",
        )

        self.assertEqual(result["bucket_id"], "ET01")

    def test_classify_generation_failure_class_lookup_not_variable_lookup(self) -> None:
        result = classify_generation_failure(
            model_text="model Bad Real x; equation x = 1; end Bad;",
            model_name="Bad",
            check_pass=False,
            simulate_pass=False,
            omc_output=(
                "Class Bad has 1 equation(s) and 1 variable(s). "
                "Error: Class MissingPackage not found in scope <TOP>."
            ),
        )

        self.assertEqual(result["bucket_id"], "ET02")

    def test_distribution_and_total_variation_distance(self) -> None:
        p = distribution_from_buckets(["PASS", "ET01", "ET01", "ET06"])
        q = {"ET01": 0.25, "ET06": 0.75}

        self.assertEqual(p, {"ET01": 2 / 3, "ET06": 1 / 3})
        self.assertAlmostEqual(total_variation_distance(p, q), 5 / 12)

    def test_load_mutation_distribution_falls_back_when_artifact_missing(self) -> None:
        dist = load_mutation_distribution(Path("/definitely/missing/summary.json"))

        self.assertAlmostEqual(sum(dist.values()), 1.0)
        self.assertEqual(dist["ET17"], 28 / 70)

    def test_parse_mapping_statuses_falls_back_when_private_file_missing(self) -> None:
        statuses = parse_mapping_statuses(Path("/definitely/missing/mapping.md"))

        self.assertEqual(statuses["ET02"], "gap")
        self.assertEqual(statuses["ET07"], "strong")

    def test_build_gap_list_flags_missing_and_mapping_gap(self) -> None:
        gaps = build_gap_list(
            p_dist={"ET10": 0.4, "ET01": 0.6},
            q_dist={"ET01": 0.6},
            mapping_statuses={"ET10": "gap", "ET01": "strong"},
        )

        gap_types = {(gap["bucket_id"], gap["gap_type"]) for gap in gaps}
        self.assertIn(("ET10", "generated_failure_not_in_mutation_distribution"), gap_types)
        self.assertIn(("ET10", "taxonomy_mapping_gap"), gap_types)

    def test_run_generation_audit_dry_run_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            pool_dir = Path(tmp) / "pool"
            pool_dir.mkdir()
            (pool_dir / "tasks.json").write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "nl_v1_t1_thermal_lumped_wall",
                                "difficulty": "T1",
                                "domain": "thermal",
                                "prompt": "Create a thermal wall model.",
                                "acceptance": ["simulate_pass"],
                            },
                            {
                                "task_id": "nl_v1_t1_electrical_rc_step",
                                "difficulty": "T1",
                                "domain": "electrical",
                                "prompt": "Create an RC model.",
                                "acceptance": ["simulate_pass"],
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            def fake_eval(model_text: str, model_name: str):
                if "thermal_lumped_wall" in model_name:
                    return True, True, "Simulation succeeded"
                return False, False, "Error: Variable missingSymbol not found in scope"

            summary = run_generation_audit(
                planner_backend="rule",
                out_dir=out_dir,
                pool_dir=pool_dir,
                dry_run_fixture=True,
                evaluator_fn=fake_eval,
            )

            self.assertEqual(summary["status"], "DRY_RUN")
            self.assertEqual(summary["task_count"], 2)
            self.assertEqual(summary["pass_count"], 1)
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "REPORT.md").exists())


if __name__ == "__main__":
    unittest.main()
