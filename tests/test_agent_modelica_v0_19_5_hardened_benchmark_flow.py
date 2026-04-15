from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_script(name: str):
    path = REPO_ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class V0195HardenedBenchmarkFlowTests(unittest.TestCase):
    def test_hardened_specs_cover_expected_size_and_families(self) -> None:
        builder = _load_script("build_hardened_mutations_v0_19_5.py")

        self.assertEqual(len(builder.SOURCE_MODELS), 8)
        self.assertEqual(
            set(builder.MUTATION_FAMILIES),
            {
                "component_parameter_reference_error",
                "component_modifier_name_error",
                "connection_topology_drop",
                "connection_endpoint_typo",
                "equation_count_extra_constraint",
            },
        )
        self.assertEqual(len(builder.SOURCE_MODELS) * len(builder.MUTATION_FAMILIES), 40)

    @unittest.skipUnless(
        (
            REPO_ROOT
            / "artifacts"
            / "agent_modelica_electrical_frozen_taskset_v1_smoke"
            / "source_models"
            / "small_rc_constant_v0.mo"
        ).exists(),
        "source model files not available in this environment",
    )
    def test_mutation_helpers_change_the_intended_surface(self) -> None:
        builder = _load_script("build_hardened_mutations_v0_19_5.py")
        source = builder.SOURCE_MODELS[0]
        source_text = (builder.SOURCE_DIR / source.source_file).read_text(encoding="utf-8")

        param_ref = builder._mutate(source_text, source, "component_parameter_reference_error")
        self.assertIn("gateforge_R1_nominal", param_ref)
        self.assertNotEqual(source_text, param_ref)

        modifier_name = builder._mutate(source_text, source, "component_modifier_name_error")
        self.assertIn("resistance=100.0", modifier_name)

        endpoint_typo = builder._mutate(source_text, source, "connection_endpoint_typo")
        self.assertIn(".pin);", endpoint_typo)

        extra_equation = builder._mutate(source_text, source, "equation_count_extra_constraint")
        self.assertIn("C1.v = 0.0;", extra_equation)

        topology_drop = builder._mutate(source_text, source, "connection_topology_drop")
        self.assertNotIn(source.connect_line, topology_drop)

    def test_benchmark_normalise_preserves_anchor_and_hardened_source(self) -> None:
        benchmark = _load_script("build_benchmark_v0_19_5.py")

        case = {
            "candidate_id": "case_a",
            "benchmark_family": "component_modifier_name_error",
        }
        normalised = benchmark._normalise(case, "v0.19.5_hardened")

        self.assertEqual(normalised["benchmark_version"], "v0.19.5")
        self.assertEqual(normalised["benchmark_source"], "v0.19.5_hardened")
        self.assertEqual(normalised["task_id"], "case_a")
        self.assertEqual(normalised["backend"], "openmodelica_docker")
        self.assertEqual(normalised["planner_backend"], "gemini")

    def test_runner_aggregate_reports_family_and_difficulty_buckets(self) -> None:
        runner = _load_script("run_benchmark_trajectory_v0_19_5.py")
        summaries = [
            {
                "candidate_id": "a",
                "benchmark_family": "type1_intra_layer",
                "executor_status": "PASS",
                "n_turns": 2,
                "termination": "success",
                "saw_layer_transition": False,
            },
            {
                "candidate_id": "b",
                "benchmark_family": "equation_count_extra_constraint",
                "executor_status": "FAILED",
                "n_turns": 1,
                "termination": "cycling_or_early_stop",
                "saw_layer_transition": False,
            },
            {
                "candidate_id": "c",
                "benchmark_family": "component_parameter_reference_error",
                "executor_status": "PASS",
                "n_turns": 5,
                "termination": "success",
                "saw_layer_transition": True,
            },
        ]

        aggregate = runner._aggregate(summaries)

        self.assertEqual(aggregate["total_cases"], 3)
        self.assertEqual(aggregate["pass_count"], 2)
        self.assertAlmostEqual(aggregate["pass_rate"], 2 / 3)
        self.assertEqual(
            aggregate["by_family"]["equation_count_extra_constraint"]["pass_rate"],
            0.0,
        )
        self.assertEqual(
            aggregate["by_family"]["component_parameter_reference_error"]["layer_transition_count"],
            1,
        )
        self.assertEqual(aggregate["by_difficulty_bucket"]["target_difficulty"]["total_cases"], 1)
        self.assertEqual(aggregate["by_difficulty_bucket"]["too_hard_or_unresolved"]["total_cases"], 1)
        self.assertEqual(aggregate["by_difficulty_bucket"]["hard_but_solved"]["total_cases"], 1)


if __name__ == "__main__":
    unittest.main()
