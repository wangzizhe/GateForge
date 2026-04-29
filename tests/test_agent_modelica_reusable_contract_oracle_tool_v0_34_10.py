from __future__ import annotations

import json
import unittest

from gateforge.agent_modelica_reusable_contract_oracle_tool_v0_34_10 import (
    dispatch_reusable_contract_oracle_tool,
    get_reusable_contract_oracle_tool_defs,
)
from gateforge.agent_modelica_tool_use_harness_v0_28_0 import get_tool_defs, get_tool_profile_guidance


class ReusableContractOracleToolV03410Tests(unittest.TestCase):
    def test_tool_reports_diagnostic_only_contract_result(self) -> None:
        model_text = (
            "model X\n"
            "  connector Pin\n"
            "    Real v;\n"
            "    flow Real i;\n"
            "  end Pin;\n"
            "  model Probe\n"
            "    Pin p[1];\n"
            "  equation\n"
            "    p[1].i = 0;\n"
            "  end Probe;\n"
            "  replaceable model ProbeBank = Probe;\n"
            "  ProbeBank probe;\n"
            "equation\n"
            "end X;\n"
        )
        payload = json.loads(
            dispatch_reusable_contract_oracle_tool(
                "reusable_contract_oracle_diagnostic",
                {"model_text": model_text},
            )
        )
        self.assertTrue(payload["contract_oracle_pass"])
        self.assertTrue(payload["discipline"]["oracle_audit_only"])
        self.assertFalse(payload["discipline"]["patch_generated"])

    def test_tool_def_and_harness_profile_are_available(self) -> None:
        self.assertEqual(get_reusable_contract_oracle_tool_defs()[0]["name"], "reusable_contract_oracle_diagnostic")
        names = {tool["name"] for tool in get_tool_defs("reusable_contract_oracle")}
        self.assertIn("reusable_contract_oracle_diagnostic", names)
        self.assertIn("check_model", names)
        self.assertIn("audit-only", get_tool_profile_guidance("reusable_contract_oracle"))


if __name__ == "__main__":
    unittest.main()
