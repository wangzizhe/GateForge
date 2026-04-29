from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_arrayed_connector_family_v0_32_3 import build_arrayed_connector_family_summary
from tests.test_agent_modelica_hard_family_expansion_v0_32_0 import _task


class ArrayedConnectorFamilyV0323Tests(unittest.TestCase):
    def test_build_summary_relabels_scope_and_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case_ids = (
                "sem_19_arrayed_shared_probe_bus",
                "sem_20_arrayed_adapter_cross_node",
            )
            for case_id in case_ids:
                (root / f"{case_id}.json").write_text(json.dumps(_task(case_id)), encoding="utf-8")
            summary = build_arrayed_connector_family_summary(
                task_root=root,
                out_dir=root / "out",
                case_ids=case_ids,
            )
            self.assertEqual(summary["version"], "v0.32.3")
            self.assertEqual(summary["analysis_scope"], "arrayed_connector_family_expansion")
            self.assertEqual(summary["decision"], "arrayed_connector_family_ready_for_live_baseline")


if __name__ == "__main__":
    unittest.main()
