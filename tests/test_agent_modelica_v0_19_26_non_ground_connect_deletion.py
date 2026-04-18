from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_script(name: str):
    path = REPO_ROOT / "scripts" / name
    module_name = name.replace(".py", "")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


builder = _load_script("build_non_ground_connect_deletion_mutations_v0_19_26.py")
qualifier = _load_script("run_non_ground_connect_deletion_qualification_v0_19_26.py")


class TestNonGroundConnectDeletionBuilder(unittest.TestCase):
    def test_classify_connect_kind_distinguishes_ground_and_sensor(self) -> None:
        self.assertEqual(builder._classify_connect_kind("connect(V1.n, G.p);"), "ground")
        self.assertEqual(builder._classify_connect_kind("connect(VS1.p, R2.n);"), "sensor")
        self.assertEqual(builder._classify_connect_kind("connect(CS1.n, R1.p);"), "sensor")
        self.assertEqual(builder._classify_connect_kind("connect(R1.n, R2.p);"), "internal_branch")

    def test_extract_non_ground_connects_excludes_ground(self) -> None:
        model_text = (
            "model Demo\n"
            "equation\n"
            "  connect(V1.p, R1.p);\n"
            "  connect(V1.n, G.p);\n"
            "  connect(VS1.p, R1.n);\n"
            "end Demo;\n"
        )
        rows = builder._extract_non_ground_connects(model_text)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all("G.p" not in row[1] for row in rows))

    def test_sanitize_relation_id_is_stable(self) -> None:
        self.assertEqual(builder._sanitize_relation_id("connect(VS1.p, R2.n);"), "vs1_p__r2_n")


class TestNonGroundConnectDeletionQualification(unittest.TestCase):
    def test_classify_candidate_promotes_multi_turn_core(self) -> None:
        run_summaries = [
            {
                "turn_shape": "multi_turn_repair",
                "n_turns": 3,
                "observed_error_sequence": ["model_check_error", "model_check_error", "none"],
            },
            {
                "turn_shape": "multi_turn_repair",
                "n_turns": 3,
                "observed_error_sequence": ["model_check_error", "model_check_error", "none"],
            },
            {
                "turn_shape": "single_fix_closure",
                "n_turns": 2,
                "observed_error_sequence": ["model_check_error", "none"],
            },
        ]
        result = qualifier.classify_candidate(run_summaries)
        self.assertEqual(result["qualification_label"], "multi_turn_core")

    def test_classify_candidate_promotes_anchor(self) -> None:
        run_summaries = [
            {
                "turn_shape": "single_fix_closure",
                "n_turns": 2,
                "observed_error_sequence": ["simulate_error", "none"],
            },
            {
                "turn_shape": "single_fix_closure",
                "n_turns": 2,
                "observed_error_sequence": ["simulate_error", "none"],
            },
            {
                "turn_shape": "unresolved",
                "n_turns": 6,
                "observed_error_sequence": ["simulate_error"] * 6,
            },
        ]
        result = qualifier.classify_candidate(run_summaries)
        self.assertEqual(result["qualification_label"], "anchor_single_fix")

    def test_classify_candidate_marks_unresolved_hard(self) -> None:
        run_summaries = [
            {
                "turn_shape": "unresolved",
                "n_turns": 6,
                "observed_error_sequence": ["simulate_error"] * 6,
            },
            {
                "turn_shape": "unresolved",
                "n_turns": 5,
                "observed_error_sequence": ["simulate_error", "model_check_error", "simulate_error", "simulate_error", "simulate_error"],
            },
            {
                "turn_shape": "single_fix_closure",
                "n_turns": 2,
                "observed_error_sequence": ["simulate_error", "none"],
            },
        ]
        result = qualifier.classify_candidate(run_summaries)
        self.assertEqual(result["qualification_label"], "unresolved_hard")


if __name__ == "__main__":
    unittest.main()
