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


class V0196ConstraintResidualProfileTests(unittest.TestCase):
    def test_classifies_overdetermined_structural_balance(self) -> None:
        profiler = _load_script("build_constraint_residual_profile_v0_19_6.py")
        attempt = {
            "observed_failure_type": "constraint_violation",
            "log_excerpt": "Error: Too many equations, over-determined system.",
        }

        self.assertEqual(
            profiler._classify_attempt(attempt),
            "overdetermined_structural_balance",
        )

    def test_classifies_legacy_msl_type_injection(self) -> None:
        profiler = _load_script("build_constraint_residual_profile_v0_19_6.py")
        attempt = {
            "observed_failure_type": "constraint_violation",
            "log_excerpt": "Error: Class Modelica.SIunits.Resistance not found in scope.",
        }

        self.assertEqual(
            profiler._classify_attempt(attempt),
            "legacy_msl_type_injection",
        )

    def test_transition_class_detects_constraint_loop(self) -> None:
        profiler = _load_script("build_constraint_residual_profile_v0_19_6.py")

        self.assertEqual(
            profiler._transition_class([
                "model_check_error",
                "constraint_violation",
                "constraint_violation",
            ]),
            "model_check_to_constraint_loop",
        )
        self.assertEqual(
            profiler._transition_class(["constraint_violation"]),
            "starts_at_constraint_violation",
        )

    def test_real_profile_matches_v0195_unresolved_boundary(self) -> None:
        profiler = _load_script("build_constraint_residual_profile_v0_19_6.py")
        profile = profiler.build_profile()

        self.assertEqual(profile["total_unresolved_cases"], 10)
        self.assertEqual(
            profile["by_final_residual_class"],
            {
                "legacy_msl_type_injection": 2,
                "overdetermined_structural_balance": 8,
            },
        )
        self.assertEqual(
            profile["by_recommended_strategy"],
            {
                "constraint_residual_remove_or_relax_extra_binding_equation": 8,
                "reject_legacy_msl_siunits_repair": 2,
            },
        )
        self.assertEqual(
            profile["family_residual_matrix"]["equation_count_extra_constraint"],
            {"overdetermined_structural_balance": 8},
        )
        self.assertEqual(
            profile["family_residual_matrix"]["component_parameter_reference_error"],
            {"legacy_msl_type_injection": 2},
        )


if __name__ == "__main__":
    unittest.main()
