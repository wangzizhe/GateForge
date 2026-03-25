"""Tests for find_primary_model_name in agent_modelica_text_repair_utils_v1.

Covers:
- Standalone model (Track A compatibility)
- Within + block (AixLib zero-shot pattern)
- Within + model
- Partial model
- No match returns empty string
- Within-only with no class declaration
- Block without within (CDL standalone)
"""

import unittest

from gateforge.agent_modelica_text_repair_utils_v1 import find_primary_model_name


class TestFindPrimaryModelName(unittest.TestCase):

    # --- Standalone model (backward compat) ---

    def test_standalone_model(self):
        src = "model FooBar\n  Real x;\nequation\n  der(x) = -x;\nend FooBar;"
        self.assertEqual(find_primary_model_name(src), "FooBar")

    def test_standalone_model_with_parameter(self):
        src = "model TwoPoint\n  parameter Real k = 1;\nequation\n  y = k;\nend TwoPoint;"
        self.assertEqual(find_primary_model_name(src), "TwoPoint")

    # --- Within + block (AixLib pattern) ---

    def test_within_block(self):
        src = "within AixLib.Utilities.Math;\nblock IntegratorWithReset\n  Real x;\nend IntegratorWithReset;"
        self.assertEqual(
            find_primary_model_name(src),
            "AixLib.Utilities.Math.IntegratorWithReset",
        )

    def test_within_block_cdl(self):
        src = "within AixLib.Controls.OBC.CDL.Reals;\nblock Derivative\n  Real x;\nend Derivative;"
        self.assertEqual(
            find_primary_model_name(src),
            "AixLib.Controls.OBC.CDL.Reals.Derivative",
        )

    def test_within_model(self):
        src = "within AixLib.Controls.HeatPump;\nmodel TwoPointControlledHP\nend TwoPointControlledHP;"
        self.assertEqual(
            find_primary_model_name(src),
            "AixLib.Controls.HeatPump.TwoPointControlledHP",
        )

    # --- Partial model ---

    def test_partial_model(self):
        src = "partial model PartialFoo\n  Real x;\nend PartialFoo;"
        self.assertEqual(find_primary_model_name(src), "PartialFoo")

    def test_within_partial_block(self):
        src = "within A.B;\npartial block PartialCtrl\nend PartialCtrl;"
        self.assertEqual(find_primary_model_name(src), "A.B.PartialCtrl")

    # --- No match ---

    def test_empty_text(self):
        self.assertEqual(find_primary_model_name(""), "")

    def test_no_class_declaration(self):
        src = "within AixLib.Utils;\n// no class here"
        self.assertEqual(find_primary_model_name(src), "")

    # --- Block without within ---

    def test_block_no_within(self):
        src = "block SimplePID\n  parameter Real k;\nend SimplePID;"
        self.assertEqual(find_primary_model_name(src), "SimplePID")

    # --- Single-level within ---

    def test_single_level_within(self):
        src = "within MSL;\nmodel SimpleModel\nend SimpleModel;"
        self.assertEqual(find_primary_model_name(src), "MSL.SimpleModel")

    # --- Connector and record ---

    def test_connector(self):
        src = "connector HeatPort\n  Real T;\nend HeatPort;"
        self.assertEqual(find_primary_model_name(src), "HeatPort")

    def test_record(self):
        src = "within AixLib.DataBase;\nrecord HeatPumpData\nend HeatPumpData;"
        self.assertEqual(find_primary_model_name(src), "AixLib.DataBase.HeatPumpData")


class TestLoadHardpackExtraModelLoads(unittest.TestCase):
    """Tests for load_hardpack_extra_model_loads in generalization benchmark."""

    def test_aix_hardpack_returns_aixlib(self):
        from gateforge.agent_modelica_generalization_benchmark_v1 import (
            load_hardpack_extra_model_loads,
        )
        extras = load_hardpack_extra_model_loads(
            "benchmarks/agent_modelica_hardpack_aix_v1.json"
        )
        self.assertEqual(extras, ["AixLib"])

    def test_msl_hardpack_returns_empty(self):
        from gateforge.agent_modelica_generalization_benchmark_v1 import (
            load_hardpack_extra_model_loads,
        )
        extras = load_hardpack_extra_model_loads(
            "benchmarks/agent_modelica_hardpack_v1.json"
        )
        self.assertEqual(extras, [])

    def test_missing_file_returns_empty(self):
        from gateforge.agent_modelica_generalization_benchmark_v1 import (
            load_hardpack_extra_model_loads,
        )
        self.assertEqual(
            load_hardpack_extra_model_loads("nonexistent_file.json"), []
        )


if __name__ == "__main__":
    unittest.main()
