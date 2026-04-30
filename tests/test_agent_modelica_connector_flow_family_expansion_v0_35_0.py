from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_connector_flow_family_expansion_v0_35_0 import (
    build_connector_flow_family_expansion_summary,
)
from tests.test_agent_modelica_hard_family_expansion_v0_32_0 import _task


class ConnectorFlowFamilyExpansionV0350Tests(unittest.TestCase):
    def test_build_summary_relabels_scope_and_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case_ids = (
                "sem_22_arrayed_three_branch_probe_bus",
                "sem_23_nested_probe_contract_bus",
            )
            for case_id in case_ids:
                (root / f"{case_id}.json").write_text(json.dumps(_task(case_id)), encoding="utf-8")
            summary = build_connector_flow_family_expansion_summary(
                task_root=root,
                out_dir=root / "out",
                case_ids=case_ids,
            )
            self.assertEqual(summary["version"], "v0.35.0")
            self.assertEqual(summary["analysis_scope"], "connector_flow_family_expansion")
            self.assertEqual(summary["decision"], "connector_flow_family_ready_for_live_baseline")


if __name__ == "__main__":
    unittest.main()
