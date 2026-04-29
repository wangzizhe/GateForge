from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_repair_strategy_attribution_v0_33_0 import (
    build_repair_strategy_attribution,
    classify_repair_strategy,
)


def _model(*, flow: bool = False) -> str:
    flow_eq = "    p.i = 0;\n" if flow else ""
    return (
        "model X\n"
        "  connector Pin\n"
        "    Real v;\n"
        "    flow Real i;\n"
        "  end Pin;\n"
        "  partial model Base\n"
        "    Pin p[2];\n"
        "    Pin n[2];\n"
        "    output Real y[2];\n"
        "  end Base;\n"
        "  model Actual\n"
        "    extends Base;\n"
        "  equation\n"
        "    y[1] = p[1].v - n[1].v;\n"
        f"{flow_eq}"
        "  end Actual;\n"
        "  replaceable model Probe = Actual constrainedby Base;\n"
        "  Pin rail;\n"
        "  Probe probe;\n"
        "equation\n"
        "  connect(rail, probe.p[1]);\n"
        "end X;\n"
    )


def _write_result(path: Path, *, case_id: str, verdict: str = "FAILED") -> None:
    path.mkdir(parents=True, exist_ok=True)
    row = {
        "case_id": case_id,
        "tool_profile": "base",
        "final_verdict": verdict,
        "submitted": verdict == "PASS",
        "steps": [
            {
                "step": 1,
                "tool_calls": [{"name": "check_model", "arguments": {"model_text": _model()}}],
                "tool_results": [{"name": "check_model", "result": "failed"}],
            },
            {
                "step": 2,
                "tool_calls": [{"name": "check_model", "arguments": {"model_text": _model(flow=True)}}],
                "tool_results": [{"name": "check_model", "result": "failed"}],
            },
        ],
    }
    with (path / "results.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


class RepairStrategyAttributionV0330Tests(unittest.TestCase):
    def test_classify_repair_strategy_detects_arrayed_flow_contract_tags(self) -> None:
        payload = classify_repair_strategy(_model())
        self.assertIn("arrayed_connection_set", payload["strategy_tags"])
        self.assertIn("custom_connector_contract", payload["strategy_tags"])
        self.assertIn("reusable_partial_replaceable_contract", payload["strategy_tags"])
        self.assertIn("potential_only_probe_contract", payload["strategy_tags"])

    def test_build_summary_promotes_external_strategy_source_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_a = root / "run_a"
            run_b = root / "run_b"
            _write_result(run_a, case_id="sem_13_arrayed_connector_bus_refactor")
            _write_result(run_b, case_id="sem_19_arrayed_shared_probe_bus")
            summary = build_repair_strategy_attribution(
                run_dirs={"run_a": run_a, "run_b": run_b},
                out_dir=root / "out",
                target_case_ids={"sem_13_arrayed_connector_bus_refactor", "sem_19_arrayed_shared_probe_bus"},
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["decision"], "repair_strategy_discovery_needs_external_strategy_source")
            self.assertFalse(summary["discipline"]["candidate_selection_added"])


if __name__ == "__main__":
    unittest.main()
