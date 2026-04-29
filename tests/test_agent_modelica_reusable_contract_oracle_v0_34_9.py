from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_reusable_contract_oracle_v0_34_9 import (
    build_reusable_contract_oracle,
    evaluate_reusable_contract_candidate,
)


def _model(*, nested: bool) -> str:
    nested_eq = "      p[1].i = 0;\n" if nested else ""
    top_eq = "" if nested else "  probe.p[1].i = 0;\n"
    return (
        "model X\n"
        "  connector Pin\n"
        "    Real v;\n"
        "    flow Real i;\n"
        "  end Pin;\n"
        "  model Probe\n"
        "    Pin p[1];\n"
        "  equation\n"
        f"{nested_eq}"
        "  end Probe;\n"
        "  replaceable model ProbeBank = Probe;\n"
        "  ProbeBank probe;\n"
        "equation\n"
        f"{top_eq}"
        "end X;\n"
    )


def _write_run(root: Path, model_text: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    row = {
        "steps": [
            {
                "tool_calls": [{"name": "check_model", "arguments": {"model_text": model_text}}],
                "tool_results": [{"name": "check_model", "result": 'resultFile = "/workspace/X.mat"'}],
            }
        ]
    }
    (root / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class ReusableContractOracleV0349Tests(unittest.TestCase):
    def test_passes_when_flow_ownership_is_nested(self) -> None:
        payload = evaluate_reusable_contract_candidate(_model(nested=True))
        self.assertTrue(payload["contract_oracle_pass"])
        self.assertEqual(payload["top_level_flow_equation_count"], 0)

    def test_fails_when_flow_ownership_is_top_level(self) -> None:
        payload = evaluate_reusable_contract_candidate(_model(nested=False))
        self.assertFalse(payload["contract_oracle_pass"])
        self.assertGreater(payload["top_level_flow_equation_count"], 0)

    def test_build_evaluates_success_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / "run"
            _write_run(run, _model(nested=False))
            summary = build_reusable_contract_oracle(run_dir=run, out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["decision"], "success_candidate_fails_reusable_contract_oracle")
            self.assertTrue(summary["discipline"]["oracle_audit_only"])


if __name__ == "__main__":
    unittest.main()
